import json
import os

from groq import Groq

MODEL_NAME = "llama-3.3-70b-versatile"

REWRITE_PROMPT = """You are a code search assistant.
A developer asked: "{query}"

Rewrite this as 2-3 more specific search queries that would help find relevant code.
Focus on: function names, class names, variable names, patterns, and technical terms.
Return ONLY a JSON array of strings: ["query1", "query2", "query3"]"""

CONTEXTUALIZE_PROMPT = """Given a conversation history and a follow-up question, rewrite the \
follow-up as a standalone question that captures all context needed to understand it on its own \
(e.g. resolve "it", "that function", "the other one" to what they actually refer to).
If the follow-up is already standalone, return it unchanged.
Return ONLY the rewritten question text, nothing else — no quotes, no explanation.

Conversation history:
{history}

Follow-up question: {question}

Standalone question:"""

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
    return _client


def rewrite_query(original_query: str) -> list[str]:
    """
    Call Groq with REWRITE_PROMPT.
    Parse JSON array response.
    Return [original_query] + rewritten queries.
    On any error, return [original_query] alone.
    """
    try:
        completion = _get_client().chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": REWRITE_PROMPT.format(query=original_query)}],
            temperature=0.3,
        )
        content = completion.choices[0].message.content.strip()
        # strip markdown code fences if the model wraps its JSON in one
        if content.startswith("```"):
            content = content.strip("`")
            content = content[content.find("["):content.rfind("]") + 1]
        rewritten = json.loads(content)
        if not isinstance(rewritten, list):
            return [original_query]
        return [original_query] + [str(q) for q in rewritten]
    except Exception:
        return [original_query]


def contextualize_query(question: str, history: list[dict]) -> str:
    """
    If there's prior conversation turns, ask Groq to resolve the follow-up
    question (which may contain pronouns like "it" or "that function") into
    a standalone question, so retrieval isn't run on an ambiguous fragment.
    On any error, or if there's no history, return the question unchanged.
    """
    if not history:
        return question
    try:
        history_text = "\n\n".join(f"Q: {turn['question']}\nA: {turn['answer']}" for turn in history)
        completion = _get_client().chat.completions.create(
            model=MODEL_NAME,
            messages=[{
                "role": "user",
                "content": CONTEXTUALIZE_PROMPT.format(history=history_text, question=question),
            }],
            temperature=0.1,
        )
        standalone = completion.choices[0].message.content.strip().strip('"')
        return standalone or question
    except Exception:
        return question
