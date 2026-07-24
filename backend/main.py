import json
import os
import shutil
import tempfile
import time

import groq
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db import sqlite_client
from db.chroma_client import delete_collection
from generation.generator import build_citations, generate_answer_stream
from ingestion.cloner import clone_github_repo, extract_zip
from pipeline import prepare_query, run_ingestion_pipeline, run_query, run_sync_pipeline

load_dotenv()
sqlite_client.init_db()

app = FastAPI(title="Codebase RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestUrlRequest(BaseModel):
    github_url: str


class ChatTurn(BaseModel):
    question: str
    answer: str


class QueryRequest(BaseModel):
    question: str
    repo_id: str
    history: list[ChatTurn] = []


@app.post("/ingest/url")
def ingest_url(req: IngestUrlRequest):
    start = time.time()
    try:
        repo_path, repo_id = clone_github_repo(req.github_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    repo_name = req.github_url.rstrip("/").split("/")[-1].replace(".git", "")
    try:
        result = run_ingestion_pipeline(repo_path, repo_id, repo_name, req.github_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)

    result["time_taken_seconds"] = round(time.time() - start, 2)
    return result


@app.post("/ingest/upload")
async def ingest_upload(file: UploadFile):
    start = time.time()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        shutil.copyfileobj(file.file, tmp)
        zip_path = tmp.name

    try:
        try:
            repo_path, repo_id = extract_zip(zip_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        repo_name = os.path.splitext(file.filename or "upload")[0]
        try:
            result = run_ingestion_pipeline(repo_path, repo_id, repo_name, "")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)
    finally:
        os.remove(zip_path)

    result["time_taken_seconds"] = round(time.time() - start, 2)
    return result


@app.post("/repos/{repo_id}/sync")
def sync_repo(repo_id: str):
    repo = sqlite_client.get_repo(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail=f"Unknown repo_id: {repo_id}")
    if not repo["source_url"]:
        raise HTTPException(
            status_code=400,
            detail="This repo was ingested from a zip upload and has no source URL to re-sync from. Re-upload it instead.",
        )

    start = time.time()
    try:
        repo_path, _ = clone_github_repo(repo["source_url"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = run_sync_pipeline(repo_path, repo_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)

    result["time_taken_seconds"] = round(time.time() - start, 2)
    return result


@app.post("/query")
def query(req: QueryRequest):
    if sqlite_client.get_repo(req.repo_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown repo_id: {req.repo_id}")

    history = [turn.model_dump() for turn in req.history]
    try:
        return run_query(req.repo_id, req.question, history)
    except groq.RateLimitError:
        raise HTTPException(status_code=429, detail="Groq API rate limit reached. Please try again shortly.")
    except groq.AuthenticationError:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is missing or invalid. Check backend/.env.")
    except groq.GroqError as e:
        raise HTTPException(status_code=502, detail=f"Answer generation failed: {e}")


@app.post("/query/stream")
def query_stream(req: QueryRequest):
    if sqlite_client.get_repo(req.repo_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown repo_id: {req.repo_id}")

    history = [turn.model_dump() for turn in req.history]
    chunks, standalone_question, rewritten_queries, timings = prepare_query(req.repo_id, req.question, history)

    def sse(event_type: str, data: dict) -> str:
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"

    def event_stream():
        gen_start = time.perf_counter()
        try:
            for token in generate_answer_stream(standalone_question, chunks):
                yield sse("token", {"text": token})
        except groq.RateLimitError:
            yield sse("error", {"message": "Groq API rate limit reached. Please try again shortly."})
            return
        except groq.AuthenticationError:
            yield sse("error", {"message": "GROQ_API_KEY is missing or invalid. Check backend/.env."})
            return
        except groq.GroqError as e:
            yield sse("error", {"message": f"Answer generation failed: {e}"})
            return

        timings["generate_ms"] = round((time.perf_counter() - gen_start) * 1000, 1)
        timings["total_ms"] = round(sum(timings.values()), 1)
        yield sse("done", {
            "citations": build_citations(chunks),
            "rewritten_queries": rewritten_queries,
            "standalone_question": standalone_question,
            "timings": timings,
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/repos")
def list_repos():
    return sqlite_client.list_repos()


@app.delete("/repos/{repo_id}")
def delete_repo(repo_id: str):
    if sqlite_client.get_repo(repo_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown repo_id: {repo_id}")
    delete_collection(repo_id)
    sqlite_client.delete_repo(repo_id)
    return {"deleted": repo_id}
