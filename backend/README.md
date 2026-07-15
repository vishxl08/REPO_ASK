---
title: RepoMind
emoji: 🧠
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
---

# RepoMind backend

Hybrid-retrieval RAG API for chatting with a codebase in natural language —
tree-sitter chunking, BM25 + semantic search fused with RRF, cross-encoder
reranking, Groq for query rewriting and generation.

Set `GROQ_API_KEY` as a Space secret before use (Settings → Variables and
secrets).

Full project, frontend, and retrieval-quality writeup:
[github.com/vishxl08/REPO_ASK](https://github.com/vishxl08/REPO_ASK)
