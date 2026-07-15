import os
from collections.abc import Iterator

from groq import Groq

MODEL_NAME = "llama-3.3-70b-versatile"

ANSWER_PROMPT = """You are an expert code assistant helping a developer understand a codebase.

User question: {question}

Relevant code chunks retrieved from the codebase:
{context}

Instructions:
- Answer the question clearly and concisely based on the retrieved code.
- Cite specific files and line numbers inline, e.g. (auth.py, lines 47-63).
- If the retrieved code doesn't fully answer the question, say so honestly.
- Do not make up code or functionality that isn't in the retrieved chunks.
- Format code snippets using markdown code blocks with the correct language.

Answer:"""

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
    return _client


def build_context(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into a readable context string.
    Each chunk: [filename, lines X-Y]\n```language\ncode\n```
    """
    parts = []
    for c in chunks:
        parts.append(
            f"[{c['file_path']}, lines {c['start_line']}-{c['end_line']}]\n"
            f"```{c.get('language', '')}\n{c['content']}\n```"
        )
    return "\n\n".join(parts)


def build_citations(chunks: list[dict]) -> list[dict]:
    return [
        {
            "file_path": c["file_path"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "language": c.get("language", ""),
            "symbol_name": c.get("symbol_name", ""),
            "content": c["content"],
        }
        for c in chunks
    ]


def generate_answer(question: str, chunks: list[dict]) -> dict:
    """
    Call Groq with ANSWER_PROMPT + formatted context.
    Return {
        "answer": str,
        "citations": [{"file_path": str, "start_line": int, "end_line": int, "content": str}]
    }
    """
    context = build_context(chunks) if chunks else "(no relevant code found)"
    completion = _get_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": ANSWER_PROMPT.format(question=question, context=context)}],
        temperature=0.2,
    )
    answer = completion.choices[0].message.content

    return {
        "answer": answer,
        "citations": build_citations(chunks),
    }


def generate_answer_stream(question: str, chunks: list[dict]) -> Iterator[str]:
    """
    Same generation as generate_answer, but yields the answer text incrementally
    as Groq streams it back, instead of waiting for the full completion.
    """
    context = build_context(chunks) if chunks else "(no relevant code found)"
    stream = _get_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": ANSWER_PROMPT.format(question=question, context=context)}],
        temperature=0.2,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
