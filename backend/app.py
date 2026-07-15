"""
HF Spaces entry point. The Gradio SDK is free (unlike Docker, which needs a
paid account), so we mount a tiny informational Gradio page and hand the
actual serving over to our real FastAPI app underneath it — the REST API
(/ingest, /query, /query/stream, etc.) is untouched and works exactly the
same as running `uvicorn main:app` directly.
"""
import gradio as gr

from main import app as fastapi_app

with gr.Blocks(title="RepoMind API") as demo:
    gr.Markdown(
        """
        # RepoMind API

        This Space hosts the RepoMind backend (FastAPI) — it's a REST API,
        not a chat UI. Talk to it from the RepoMind frontend or directly:

        - `POST /ingest/url` `{"github_url": "..."}`
        - `POST /query` `{"question": "...", "repo_id": "..."}`
        - `POST /query/stream` — same, but Server-Sent Events
        - `GET /repos`

        Interactive API docs: [`/docs`](/docs)
        Source + writeup: [github.com/vishxl08/REPO_ASK](https://github.com/vishxl08/REPO_ASK)
        """
    )

app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7860)
