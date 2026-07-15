import re

from rank_bm25 import BM25Okapi

from db import sqlite_client
from db.chroma_client import semantic_search
from ingestion.embedder import embed_query
from retrieval.reranker import rerank
from timing import timed

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _bm25_document(chunk: dict) -> str:
    # include file path + symbol name so filename/symbol mentions in a query
    # can match chunks whose code body doesn't literally contain them
    return f"{chunk['file_path']} {chunk.get('symbol_name', '')} {chunk['content']}"


def _bm25_search(all_chunks: list[dict], query: str, top_k: int = 20) -> list[dict]:
    if not all_chunks:
        return []
    tokenized_corpus = [_tokenize(_bm25_document(c)) for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(_tokenize(query))
    ranked_idx = sorted(range(len(all_chunks)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [all_chunks[i] for i in ranked_idx if scores[i] > 0]


def reciprocal_rank_fusion(semantic_results: list, bm25_results: list, k: int = 60) -> list:
    """
    RRF score = 1/(k + rank_semantic) + 1/(k + rank_bm25)
    Merge and re-rank both result lists.
    """
    scores = {}
    for rank, result in enumerate(semantic_results):
        chunk_id = result["chunk_id"]
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank + 1)
    for rank, result in enumerate(bm25_results):
        chunk_id = result["chunk_id"]
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)


def hybrid_search(repo_id: str, query: str, query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """
    Step 1: Get top-20 from ChromaDB semantic search
    Step 2: Get top-20 from BM25 keyword search (over all chunks in this repo from SQLite)
    Step 3: Combine scores using Reciprocal Rank Fusion (RRF)
    Step 4: Return top_k unique chunks ranked by combined RRF score
    """
    semantic_hits = semantic_search(repo_id, query_embedding, top_k=20)
    all_chunks = sqlite_client.get_chunks_for_repo(repo_id)
    bm25_hits = _bm25_search(all_chunks, query, top_k=20)

    ranked_ids = reciprocal_rank_fusion(semantic_hits, bm25_hits)

    chunk_lookup = {c["chunk_id"]: c for c in all_chunks}
    for hit in semantic_hits:
        chunk_lookup.setdefault(hit["chunk_id"], hit)

    return [chunk_lookup[cid] for cid in ranked_ids[:top_k] if cid in chunk_lookup]


def hybrid_search_multi(
    repo_id: str, queries: list[str], top_k: int = 5, rerank_pool_size: int = 20, timings: dict | None = None
) -> list[dict]:
    """
    Run hybrid_search once per query variant (original query + Groq rewrites),
    fuse all per-query rankings together with a second RRF pass so query
    rewriting actually improves recall, then re-rank the fused shortlist with
    a cross-encoder scored against the original question — RRF is good at
    recall (casting a wide net across query variants) but a poor judge of
    fine-grained relevance, which is what the cross-encoder is for.

    If `timings` is passed, "retrieve_ms" and "rerank_ms" are recorded into it.
    """
    if timings is None:
        timings = {}
    original_query = queries[0]

    with timed(timings, "retrieve_ms"):
        per_query_results = [
            hybrid_search(repo_id, q, embed_query(q), top_k=rerank_pool_size) for q in queries
        ]

        if len(per_query_results) == 1:
            candidates = per_query_results[0]
        else:
            scores: dict[str, float] = {}
            lookup: dict[str, dict] = {}
            k = 60
            for results in per_query_results:
                for rank, chunk in enumerate(results):
                    cid = chunk["chunk_id"]
                    scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
                    lookup.setdefault(cid, chunk)

            ranked_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
            candidates = [lookup[cid] for cid in ranked_ids[:rerank_pool_size]]

    with timed(timings, "rerank_ms"):
        results = rerank(original_query, candidates, top_k)

    return results
