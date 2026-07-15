from db import sqlite_client
from ingestion.chunker import CodeChunk


def record_ingestion(
    repo_id: str,
    name: str,
    source_url: str,
    total_files: int,
    chunks: list[CodeChunk],
) -> dict:
    """
    Persist repo + chunk metadata to SQLite and return the ingestion stats
    used in the API response (files indexed, chunks created, languages detected).
    """
    languages = sorted({c.language for c in chunks})
    sqlite_client.insert_repo(
        repo_id=repo_id,
        name=name,
        source_url=source_url,
        total_files=total_files,
        total_chunks=len(chunks),
        languages=languages,
    )
    sqlite_client.insert_chunks(repo_id, chunks)
    return {
        "total_files": total_files,
        "total_chunks": len(chunks),
        "languages": languages,
    }
