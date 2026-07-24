import os


def data_dir() -> str:
    """
    Base directory for persisted app data (SQLite metadata.db, ChromaDB store).
    Override with REPOMIND_DATA_DIR on read-only deployment filesystems (e.g.
    Vercel, where only /tmp is writable) -- that storage is ephemeral, but at
    least the app starts instead of crashing on every request.
    """
    return os.environ.get("REPOMIND_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
