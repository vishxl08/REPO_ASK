import json
import os
import sqlite3

from ingestion.chunker import CodeChunk
from paths import data_dir

DB_PATH = os.path.join(data_dir(), "metadata.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repos (
            repo_id TEXT PRIMARY KEY,
            name TEXT,
            source_url TEXT,
            total_files INTEGER,
            total_chunks INTEGER,
            languages TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            repo_id TEXT,
            file_path TEXT,
            language TEXT,
            symbol_name TEXT,
            start_line INTEGER,
            end_line INTEGER,
            content TEXT,
            FOREIGN KEY(repo_id) REFERENCES repos(repo_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_hashes (
            repo_id TEXT,
            file_path TEXT,
            content_hash TEXT NOT NULL,
            PRIMARY KEY (repo_id, file_path)
        )
    """)
    conn.commit()
    conn.close()


def insert_repo(
    repo_id: str,
    name: str,
    source_url: str,
    total_files: int,
    total_chunks: int,
    languages: list[str],
) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO repos (repo_id, name, source_url, total_files, total_chunks, languages)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (repo_id, name, source_url, total_files, total_chunks, json.dumps(languages)),
    )
    conn.commit()
    conn.close()


def insert_chunks(repo_id: str, chunks: list[CodeChunk]) -> None:
    if not chunks:
        return
    conn = _connect()
    conn.executemany(
        """
        INSERT OR REPLACE INTO chunks
            (chunk_id, repo_id, file_path, language, symbol_name, start_line, end_line, content)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (c.chunk_id, repo_id, c.file_path, c.language, c.symbol_name, c.start_line, c.end_line, c.content)
            for c in chunks
        ],
    )
    conn.commit()
    conn.close()


def list_repos() -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM repos ORDER BY created_at DESC").fetchall()
    conn.close()
    return [
        {
            "repo_id": row["repo_id"],
            "name": row["name"],
            "source_url": row["source_url"],
            "total_files": row["total_files"],
            "total_chunks": row["total_chunks"],
            "languages": json.loads(row["languages"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_repo(repo_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM repos WHERE repo_id = ?", (repo_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "repo_id": row["repo_id"],
        "name": row["name"],
        "source_url": row["source_url"],
        "total_files": row["total_files"],
        "total_chunks": row["total_chunks"],
        "languages": json.loads(row["languages"]),
        "created_at": row["created_at"],
    }


def get_chunks_for_repo(repo_id: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM chunks WHERE repo_id = ?", (repo_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_repo(repo_id: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM chunks WHERE repo_id = ?", (repo_id,))
    conn.execute("DELETE FROM file_hashes WHERE repo_id = ?", (repo_id,))
    conn.execute("DELETE FROM repos WHERE repo_id = ?", (repo_id,))
    conn.commit()
    conn.close()


def get_file_hashes(repo_id: str) -> dict[str, str]:
    conn = _connect()
    rows = conn.execute(
        "SELECT file_path, content_hash FROM file_hashes WHERE repo_id = ?", (repo_id,)
    ).fetchall()
    conn.close()
    return {row["file_path"]: row["content_hash"] for row in rows}


def upsert_file_hashes(repo_id: str, hashes: dict[str, str]) -> None:
    if not hashes:
        return
    conn = _connect()
    conn.executemany(
        "INSERT OR REPLACE INTO file_hashes (repo_id, file_path, content_hash) VALUES (?, ?, ?)",
        [(repo_id, file_path, content_hash) for file_path, content_hash in hashes.items()],
    )
    conn.commit()
    conn.close()


def delete_files(repo_id: str, file_paths: list[str]) -> None:
    """Remove chunks + hash records for files that were changed or deleted, ahead of re-indexing."""
    if not file_paths:
        return
    conn = _connect()
    conn.executemany(
        "DELETE FROM chunks WHERE repo_id = ? AND file_path = ?",
        [(repo_id, fp) for fp in file_paths],
    )
    conn.executemany(
        "DELETE FROM file_hashes WHERE repo_id = ? AND file_path = ?",
        [(repo_id, fp) for fp in file_paths],
    )
    conn.commit()
    conn.close()
