"""
Core ingestion/sync/query orchestration, decoupled from the HTTP layer so it's
reusable by main.py (FastAPI), cli.py, and the eval harness alike.
"""
import os

from db import sqlite_client
from db.chroma_client import delete_chunks_for_files, store_chunks
from generation.generator import generate_answer
from ingestion.chunker import chunk_file
from ingestion.embedder import embed_chunks
from ingestion.file_filter import get_all_files, hash_file
from retrieval.hybrid_search import hybrid_search_multi
from retrieval.query_rewriter import contextualize_query, rewrite_query
from timing import timed

# Files per embed+store batch during ingestion. Chunking/embedding/storing in
# batches instead of all-at-once bounds peak memory to roughly one batch's
# worth of chunks regardless of total repo size -- otherwise a large repo
# accumulates every chunk and embedding in memory before writing anything,
# which is what was crashing ingestion of real-sized repos on RAM-constrained
# hosts even after the model itself was made lighter.
INGEST_BATCH_SIZE = 20


def to_posix_relpath(path: str, start: str) -> str:
    return os.path.relpath(path, start).replace(os.sep, "/")


def run_ingestion_pipeline(repo_path: str, repo_id: str, repo_name: str, source_url: str) -> dict:
    """clone/extract already done by caller. filter -> chunk -> embed -> store, in batches."""
    files = get_all_files(repo_path)
    if not files:
        raise ValueError("No supported code files found in this repository.")

    total_chunks = 0
    languages: set[str] = set()
    file_hashes: dict[str, str] = {}

    for i in range(0, len(files), INGEST_BATCH_SIZE):
        batch_files = files[i : i + INGEST_BATCH_SIZE]
        batch_chunks = []
        for file_path in batch_files:
            batch_chunks.extend(chunk_file(file_path, repo_path, repo_id))

        if batch_chunks:
            embeddings = embed_chunks(batch_chunks)
            store_chunks(repo_id, batch_chunks, embeddings)
            sqlite_client.insert_chunks(repo_id, batch_chunks)
            total_chunks += len(batch_chunks)
            languages.update(c.language for c in batch_chunks)

        for f in batch_files:
            file_hashes[to_posix_relpath(f, repo_path)] = hash_file(f)

    sorted_languages = sorted(languages)
    sqlite_client.insert_repo(repo_id, repo_name, source_url, len(files), total_chunks, sorted_languages)
    sqlite_client.upsert_file_hashes(repo_id, file_hashes)

    return {
        "repo_id": repo_id,
        "repo_name": repo_name,
        "total_files": len(files),
        "total_chunks": total_chunks,
        "languages": sorted_languages,
    }


def run_sync_pipeline(repo_path: str, repo_id: str) -> dict:
    """Re-scan a repo already backing repo_id; only re-chunk/re-embed files whose content hash changed."""
    files = get_all_files(repo_path)
    file_map = {to_posix_relpath(f, repo_path): f for f in files}  # rel path -> abs path
    new_hashes = {rel: hash_file(abs_path) for rel, abs_path in file_map.items()}
    old_hashes = sqlite_client.get_file_hashes(repo_id)

    changed_or_new = [rel for rel, h in new_hashes.items() if old_hashes.get(rel) != h]
    removed = [rel for rel in old_hashes if rel not in new_hashes]
    unchanged_count = len(new_hashes) - len(changed_or_new)

    stale = changed_or_new + removed
    if stale:
        sqlite_client.delete_files(repo_id, stale)
        delete_chunks_for_files(repo_id, stale)

    new_chunks = []
    for rel in changed_or_new:
        new_chunks.extend(chunk_file(file_map[rel], repo_path, repo_id))

    embeddings = embed_chunks(new_chunks) if new_chunks else []
    store_chunks(repo_id, new_chunks, embeddings)
    sqlite_client.insert_chunks(repo_id, new_chunks)
    sqlite_client.upsert_file_hashes(repo_id, {rel: new_hashes[rel] for rel in changed_or_new})

    all_chunks = sqlite_client.get_chunks_for_repo(repo_id)
    languages = sorted({c["language"] for c in all_chunks})
    repo = sqlite_client.get_repo(repo_id)
    sqlite_client.insert_repo(repo_id, repo["name"], repo["source_url"], len(files), len(all_chunks), languages)

    return {
        "repo_id": repo_id,
        "repo_name": repo["name"],
        "total_files": len(files),
        "total_chunks": len(all_chunks),
        "languages": languages,
        "files_changed": len(changed_or_new),
        "files_removed": len(removed),
        "files_unchanged": unchanged_count,
    }


def prepare_query(repo_id: str, question: str, history: list[dict]) -> tuple[list[dict], str, list[str], dict]:
    """Contextualize -> rewrite -> hybrid retrieve -> rerank. Shared by /query, /query/stream, and the CLI."""
    timings: dict = {}

    with timed(timings, "contextualize_ms"):
        standalone_question = contextualize_query(question, history) if history else question

    with timed(timings, "rewrite_ms"):
        rewritten_queries = rewrite_query(standalone_question)

    chunks = hybrid_search_multi(repo_id, rewritten_queries, top_k=5, timings=timings)

    return chunks, standalone_question, rewritten_queries, timings


def run_query(repo_id: str, question: str, history: list[dict]) -> dict:
    """Non-streaming end-to-end query: prepare_query + generate_answer, with timings attached."""
    chunks, standalone_question, rewritten_queries, timings = prepare_query(repo_id, question, history)

    with timed(timings, "generate_ms"):
        result = generate_answer(standalone_question, chunks)

    timings["total_ms"] = round(sum(timings.values()), 1)
    result["rewritten_queries"] = rewritten_queries
    result["standalone_question"] = standalone_question
    result["timings"] = timings
    return result
