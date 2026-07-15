from sentence_transformers import CrossEncoder

# General-purpose, compact cross-encoder (~80MB). A cross-encoder scores
# (query, chunk) pairs jointly instead of comparing independent embeddings,
# which is significantly more accurate than RRF alone but too slow to run
# over an entire corpus — so it only re-scores the RRF-fused shortlist.
MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_model: CrossEncoder | None = None


def get_model() -> CrossEncoder:
    global _model
    if _model is None:
        print(f"Loading re-ranking model '{MODEL_NAME}' (first run downloads ~80MB)...")
        _model = CrossEncoder(MODEL_NAME)
        print("Re-ranking model ready.")
    return _model


def rerank(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    if len(chunks) <= 1:
        return chunks[:top_k]

    model = get_model()
    pairs = [(query, c["content"]) for c in chunks]
    scores = model.predict(pairs)

    ranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)
    return [chunk for chunk, _ in ranked[:top_k]]
