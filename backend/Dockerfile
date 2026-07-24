FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser
WORKDIR /app

# Fixed, explicit cache dir so the model weights baked in at build time (as
# root) are actually found at runtime (as appuser) — otherwise the two users'
# default $HOME/.cache paths differ and the app silently re-downloads anyway.
ENV HF_HOME=/app/.cache/huggingface

# CPU-only torch first — sentence-transformers would otherwise pull the much
# larger CUDA build, which is wasted weight on a CPU-only host.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('microsoft/codebert-base'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

RUN chown -R appuser:appuser /app
USER appuser
ENV HOME=/home/appuser

EXPOSE 7860
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
