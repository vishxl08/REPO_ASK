import time
from contextlib import contextmanager


@contextmanager
def timed(store: dict, key: str):
    """Record the wall-clock duration of a block into store[key], in milliseconds."""
    start = time.perf_counter()
    try:
        yield
    finally:
        store[key] = round((time.perf_counter() - start) * 1000, 1)
