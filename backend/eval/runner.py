from collections.abc import Callable
from dataclasses import dataclass, field

from db.chroma_client import semantic_search
from ingestion.embedder import embed_query
from retrieval.hybrid_search import hybrid_search, hybrid_search_multi
from retrieval.query_rewriter import rewrite_query


@dataclass
class EvalCase:
    question: str
    expected_files: list[str]


@dataclass
class CaseResult:
    question: str
    hit_at_1: bool
    hit_at_5: bool
    reciprocal_rank: float
    top_file: str | None


@dataclass
class StrategyReport:
    name: str
    case_results: list[CaseResult] = field(default_factory=list)

    @property
    def hit_rate_at_1(self) -> float:
        return _mean(r.hit_at_1 for r in self.case_results)

    @property
    def hit_rate_at_5(self) -> float:
        return _mean(r.hit_at_5 for r in self.case_results)

    @property
    def mrr(self) -> float:
        return _mean(r.reciprocal_rank for r in self.case_results)


def _mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _matches(file_path: str, expected_files: list[str]) -> bool:
    fp = file_path.lower()
    return any(exp.lower() in fp or fp in exp.lower() for exp in expected_files)


def _score(chunks: list[dict], expected_files: list[str]) -> tuple[bool, bool, float, str | None]:
    hit_at_1 = bool(chunks) and _matches(chunks[0]["file_path"], expected_files)
    hit_at_5 = False
    reciprocal_rank = 0.0
    for rank, chunk in enumerate(chunks[:5], start=1):
        if _matches(chunk["file_path"], expected_files):
            hit_at_5 = True
            reciprocal_rank = 1 / rank
            break
    top_file = chunks[0]["file_path"] if chunks else None
    return hit_at_1, hit_at_5, reciprocal_rank, top_file


# --- Retrieval strategies under comparison ---

def semantic_only(repo_id: str, question: str) -> list[dict]:
    return semantic_search(repo_id, embed_query(question), top_k=5)


def hybrid_no_rerank(repo_id: str, question: str) -> list[dict]:
    """BM25 + semantic + RRF, single query variant, no cross-encoder rerank."""
    return hybrid_search(repo_id, question, embed_query(question), top_k=5)


def hybrid_full_pipeline(repo_id: str, question: str) -> list[dict]:
    """The actual production pipeline: Groq query rewriting + hybrid retrieval + cross-encoder rerank."""
    rewritten = rewrite_query(question)
    return hybrid_search_multi(repo_id, rewritten, top_k=5)


STRATEGIES: dict[str, Callable[[str, str], list[dict]]] = {
    "semantic-only": semantic_only,
    "hybrid (BM25 + semantic, no rerank)": hybrid_no_rerank,
    "hybrid + rerank + query rewrite (production)": hybrid_full_pipeline,
}


def run_evaluation(repo_id: str, cases: list[EvalCase], on_progress: Callable[[str, str], None] | None = None) -> list[StrategyReport]:
    reports = []
    for name, strategy_fn in STRATEGIES.items():
        report = StrategyReport(name=name)
        for case in cases:
            if on_progress:
                on_progress(name, case.question)
            chunks = strategy_fn(repo_id, case.question)
            hit_at_1, hit_at_5, rr, top_file = _score(chunks, case.expected_files)
            report.case_results.append(CaseResult(
                question=case.question,
                hit_at_1=hit_at_1,
                hit_at_5=hit_at_5,
                reciprocal_rank=rr,
                top_file=top_file,
            ))
        reports.append(report)
    return reports


def format_report_markdown(repo_name: str, reports: list[StrategyReport]) -> str:
    lines = [f"# Retrieval evaluation — {repo_name}", ""]
    lines.append("| Strategy | Hit@1 | Hit@5 | MRR |")
    lines.append("|---|---|---|---|")
    for r in reports:
        lines.append(f"| {r.name} | {r.hit_rate_at_1:.0%} | {r.hit_rate_at_5:.0%} | {r.mrr:.3f} |")
    lines.append("")

    for r in reports:
        lines.append(f"## {r.name}")
        lines.append("")
        lines.append("| Question | Hit@1 | Hit@5 | Top result |")
        lines.append("|---|---|---|---|")
        for c in r.case_results:
            lines.append(
                f"| {c.question} | {'✓' if c.hit_at_1 else ''} | {'✓' if c.hit_at_5 else ''} | `{c.top_file or '—'}` |"
            )
        lines.append("")

    return "\n".join(lines)
