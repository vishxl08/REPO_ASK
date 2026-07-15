# Retrieval evaluation — Researchmind

18 hand-labeled questions against a real 76-file repo, run through three retrieval
strategies. Reproduce with:

```
python -m eval.run_eval --repo-id <repo_id> --dataset eval/datasets/researchmind.json
```

| Strategy | Hit@1 | Hit@5 | MRR |
|---|---|---|---|
| semantic-only | 6% | 17% | 0.081 |
| hybrid (BM25 + semantic, no rerank) | 22% | 28% | 0.233 |
| hybrid + rerank + query rewrite (production) | 17% | 56% | 0.298 |

Hybrid retrieval roughly triples Hit@5 over semantic-only, and reranking pushes it
further — from 28% to 56%. The one thing that doesn't move in a straight line:
Hit@1 actually *drops* in the full pipeline (22% → 17%). Looking at the per-question
breakdown, that's query rewriting expanding a literal question ("what does
`backend/manage.py` do?") into paraphrased variants, which pulls the cross-encoder
(trained on general web relevance, not code) toward README prose instead of the
file itself. Net win overall, but not a free one — rewriting trades some precision
on simple lookups for better recall on vague ones.

## semantic-only

| Question | Hit@1 | Hit@5 | Top result |
|---|---|---|---|
| What does backend/manage.py do? |  | ✓ | `backend/config/__init__.py` |
| What does the FastAPI app in fastapi_app.py do? |  |  | `backend/scheduler/models.py` |
| Where is the LangGraph agent orchestration defined? |  |  | `backend/scheduler/__init__.py` |
| Where are the AI tools like search and calculator implemented? |  |  | `backend/config/settings/prod.py` |
| How does the agent manage memory with Qdrant? |  |  | `backend/config/settings/prod.py` |
| What runs or executes the agent? |  |  | `backend/scheduler/__init__.py` |
| Where are the LLM prompts defined? |  |  | `backend/scheduler/__init__.py` |
| What models represent a research job or report? |  |  | `backend/config/settings/prod.py` |
| Where are the research API endpoints defined? |  |  | `backend/scheduler/__init__.py` |
| How does the WebSocket consumer work? |  |  | `backend/scheduler/__init__.py` |
| Where are Celery background tasks defined for research? |  |  | `backend/config/settings/prod.py` |
| Where is email notification logic implemented? |  |  | `backend/scheduler/__init__.py` |
| What does the scheduler app's models look like? |  | ✓ | `backend/config/__init__.py` |
| Where are Django settings configured? |  |  | `frontend/src/App.jsx` |
| Where is the React entry point that renders the app? |  |  | `backend/config/__init__.py` |
| Where is the WebSocket hook used on the frontend? |  |  | `backend/config/settings/prod.py` |
| What does the Dashboard page component do? | ✓ | ✓ | `frontend/src/pages/Dashboard.jsx` |
| How is the Django backend service configured in docker-compose? |  |  | `backend/config/__init__.py` |

## hybrid (BM25 + semantic, no rerank)

| Question | Hit@1 | Hit@5 | Top result |
|---|---|---|---|
| What does backend/manage.py do? | ✓ | ✓ | `backend/manage.py` |
| What does the FastAPI app in fastapi_app.py do? | ✓ | ✓ | `backend/fastapi_app.py` |
| Where is the LangGraph agent orchestration defined? |  |  | `backend/scheduler/__init__.py` |
| Where are the AI tools like search and calculator implemented? |  |  | `backend/config/settings/prod.py` |
| How does the agent manage memory with Qdrant? |  |  | `backend/config/settings/prod.py` |
| What runs or executes the agent? |  |  | `backend/scheduler/__init__.py` |
| Where are the LLM prompts defined? |  | ✓ | `backend/config/settings/prod.py` |
| What models represent a research job or report? |  |  | `backend/config/settings/prod.py` |
| Where are the research API endpoints defined? |  |  | `backend/scheduler/__init__.py` |
| How does the WebSocket consumer work? |  |  | `backend/scheduler/__init__.py` |
| Where are Celery background tasks defined for research? |  |  | `backend/config/celery.py` |
| Where is email notification logic implemented? |  |  | `backend/scheduler/__init__.py` |
| What does the scheduler app's models look like? | ✓ | ✓ | `backend/scheduler/models.py` |
| Where are Django settings configured? |  |  | `backend/config/settings/prod.py` |
| Where is the React entry point that renders the app? |  |  | `backend/config/__init__.py` |
| Where is the WebSocket hook used on the frontend? |  |  | `backend/config/settings/prod.py` |
| What does the Dashboard page component do? | ✓ | ✓ | `frontend/src/pages/Dashboard.jsx` |
| How is the Django backend service configured in docker-compose? |  |  | `backend/config/__init__.py` |

## hybrid + rerank + query rewrite (production)

| Question | Hit@1 | Hit@5 | Top result |
|---|---|---|---|
| What does backend/manage.py do? |  |  | `README.md` |
| What does the FastAPI app in fastapi_app.py do? | ✓ | ✓ | `backend/fastapi_app.py` |
| Where is the LangGraph agent orchestration defined? |  |  | `COMPLETION_SUMMARY.md` |
| Where are the AI tools like search and calculator implemented? |  | ✓ | `backend/agent/prompts.py` |
| How does the agent manage memory with Qdrant? |  |  | `backend/tests/test_agent_memory.py` |
| What runs or executes the agent? |  | ✓ | `backend/research/tasks.py` |
| Where are the LLM prompts defined? |  | ✓ | `backend/agent/graph.py` |
| What models represent a research job or report? | ✓ | ✓ | `backend/research/models.py` |
| Where are the research API endpoints defined? |  |  | `README.md` |
| How does the WebSocket consumer work? |  |  | `backend/tests/test_consumers.py` |
| Where are Celery background tasks defined for research? |  | ✓ | `README.md` |
| Where is email notification logic implemented? |  | ✓ | `README.md` |
| What does the scheduler app's models look like? |  |  | `backend/tests/test_scheduler.py` |
| Where are Django settings configured? |  |  | `backend/tests/conftest.py` |
| Where is the React entry point that renders the app? | ✓ | ✓ | `frontend/src/main.jsx` |
| Where is the WebSocket hook used on the frontend? |  |  | `README.md` |
| What does the Dashboard page component do? |  | ✓ | `COMPLETION_SUMMARY.md` |
| How is the Django backend service configured in docker-compose? |  | ✓ | `README.md` |
