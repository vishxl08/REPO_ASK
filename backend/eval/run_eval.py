"""
Retrieval evaluation harness.

Measures retrieval quality (Hit@1, Hit@5, MRR) against a labeled question set,
comparing semantic-only search, hybrid search, and the full production
pipeline (hybrid + Groq query rewriting + cross-encoder reranking).

Usage (from backend/, with the venv active):
    python -m eval.run_eval --repo-id <repo_id> --dataset eval/datasets/researchmind.json
"""
import argparse
import json
import sys
from pathlib import Path

from db import sqlite_client
from eval.runner import EvalCase, format_report_markdown, run_evaluation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", required=True, help="repo_id of an already-ingested repo")
    parser.add_argument("--dataset", required=True, help="path to a JSON eval dataset (see eval/datasets/)")
    parser.add_argument("--out", default=None, help="write markdown report here (default: eval/results_<repo_id>.md)")
    args = parser.parse_args()

    sqlite_client.init_db()
    if sqlite_client.get_repo(args.repo_id) is None:
        print(f"Unknown repo_id: {args.repo_id}. Ingest it first.", file=sys.stderr)
        sys.exit(1)

    dataset_path = Path(args.dataset)
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = [EvalCase(question=c["question"], expected_files=c["expected_files"]) for c in data["cases"]]
    repo_name = data.get("repo_name", args.repo_id)

    total_runs = len(cases) * 3
    completed = 0

    def on_progress(strategy_name: str, question: str):
        nonlocal completed
        completed += 1
        print(f"  [{completed}/{total_runs}] {strategy_name}: {question[:60]}")

    print(f"Running {len(cases)} eval cases x 3 strategies against {repo_name} ({args.repo_id})...")
    reports = run_evaluation(args.repo_id, cases, on_progress=on_progress)

    report_md = format_report_markdown(repo_name, reports)
    out_path = Path(args.out) if args.out else Path(__file__).parent / f"results_{args.repo_id}.md"
    out_path.write_text(report_md, encoding="utf-8")

    print("\n--- Summary ---")
    for r in reports:
        print(f"{r.name:50s} Hit@1={r.hit_rate_at_1:.0%}  Hit@5={r.hit_rate_at_5:.0%}  MRR={r.mrr:.3f}")
    print(f"\nFull report written to {out_path}")


if __name__ == "__main__":
    main()
