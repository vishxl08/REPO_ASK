import os

import chromadb

from ingestion.chunker import CodeChunk
from paths import data_dir

_client = None
PERSIST_DIR = os.path.join(data_dir(), "chroma_store")


def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=PERSIST_DIR)
    return _client


def get_or_create_collection(repo_id: str):
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=repo_id,
        metadata={"hnsw:space": "cosine"}
    )


def store_chunks(repo_id: str, chunks: list[CodeChunk], embeddings: list[list[float]]) -> None:
    if not chunks:
        return
    collection = get_or_create_collection(repo_id)
    collection.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=embeddings,
        documents=[c.content for c in chunks],
        metadatas=[{
            "file_path": c.file_path,
            "language": c.language,
            "start_line": c.start_line,
            "end_line": c.end_line,
            "chunk_type": c.chunk_type,
            "symbol_name": c.symbol_name,
        } for c in chunks]
    )


def semantic_search(repo_id: str, query_embedding: list[float], top_k: int = 10) -> list[dict]:
    collection = get_or_create_collection(repo_id)
    if collection.count() == 0:
        return []
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count())
    )

    hits = []
    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        hits.append({
            "chunk_id": chunk_id,
            "content": document,
            "distance": distance,
            **metadata,
        })
    return hits


def delete_collection(repo_id: str) -> None:
    client = get_chroma_client()
    try:
        client.delete_collection(name=repo_id)
    except Exception:
        pass


def delete_chunks_for_files(repo_id: str, file_paths: list[str]) -> None:
    if not file_paths:
        return
    collection = get_or_create_collection(repo_id)
    if collection.count() == 0:
        return
    collection.delete(where={"file_path": {"$in": file_paths}})
