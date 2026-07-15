from sentence_transformers import SentenceTransformer

from ingestion.chunker import CodeChunk

MODEL_NAME = "microsoft/codebert-base"
# codebert-base is specifically trained on code — much better than
# all-MiniLM-L6-v2 for retrieving code by natural language queries

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"Loading embedding model '{MODEL_NAME}' (first run downloads ~500MB)...")
        _model = SentenceTransformer(MODEL_NAME)
        print("Embedding model ready.")
    return _model


def _embedding_text(chunk: CodeChunk) -> str:
    # prefix with file path (+ symbol name) so filename/symbol mentions in a
    # query can match chunks whose code body doesn't literally contain them
    header = chunk.file_path if not chunk.symbol_name else f"{chunk.file_path} :: {chunk.symbol_name}"
    return f"{header}\n{chunk.content}"


def embed_chunks(chunks: list[CodeChunk]) -> list[list[float]]:
    model = get_model()
    texts = [_embedding_text(c) for c in chunks]
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=True)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    model = get_model()
    return model.encode([query])[0].tolist()
