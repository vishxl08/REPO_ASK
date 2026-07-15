import hashlib
import os

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    "eggs", ".eggs", "htmlcov", ".tox"
}

SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go",
    ".rs", ".cpp", ".c", ".h", ".cs", ".rb", ".php",
    ".swift", ".kt", ".scala", ".r", ".sql", ".sh",
    ".yaml", ".yml", ".toml", ".md"
}

# Never ingest files that commonly hold secrets, even if a supported
# extension is used incidentally (e.g. ".env" has no extension at all,
# but is matched by name below).
SKIP_FILENAMES = {".env"}
SKIP_FILENAME_PREFIXES = (".env.",)

MAX_FILE_SIZE_BYTES = 500_000  # skip files > 500KB


def _is_skipped_filename(filename: str) -> bool:
    if filename in SKIP_FILENAMES:
        return True
    return filename.startswith(SKIP_FILENAME_PREFIXES)


def get_all_files(repo_path: str) -> list[str]:
    result = []
    for root, dirs, files in os.walk(repo_path):
        # prune skip dirs in-place so os.walk doesn't recurse into them
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            if _is_skipped_filename(file):
                continue
            full_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            if os.path.getsize(full_path) > MAX_FILE_SIZE_BYTES:
                continue
            result.append(full_path)
    return result


def hash_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
