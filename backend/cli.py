"""
repomind — terminal-native access to the same ingestion/retrieval/generation
pipeline the web app uses, no browser or running server required.
"""
import shutil
import sys
import time

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Windows consoles often default to a legacy codepage that can't render
# rich's box-drawing/ellipsis characters, producing garbled output — force UTF-8.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from db import sqlite_client
from db.chroma_client import delete_collection
from generation.generator import build_citations, generate_answer_stream
from ingestion.cloner import clone_github_repo, extract_zip
from pipeline import prepare_query, run_ingestion_pipeline, run_sync_pipeline
from timing import timed

load_dotenv()
console = Console()


def _resolve_repo(repo_ref: str) -> dict:
    """Accept either an exact repo_id or a case-insensitive substring of a repo name."""
    repo = sqlite_client.get_repo(repo_ref)
    if repo:
        return repo

    matches = [r for r in sqlite_client.list_repos() if repo_ref.lower() in r["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        console.print(f"[red]'{repo_ref}' matches multiple repos — be more specific, or use the exact repo_id:[/red]")
        for m in matches:
            console.print(f"  {m['repo_id']}  ({m['name']})")
        sys.exit(1)

    console.print(f"[red]No ingested repo matches '{repo_ref}'.[/red] Run [bold]repomind repos[/bold] to list them.")
    sys.exit(1)


@click.group()
def cli():
    """RepoMind: chat with any codebase in natural language, from your terminal."""
    sqlite_client.init_db()


@cli.command()
@click.argument("source")
def ingest(source: str):
    """Ingest a repo from a GitHub URL or a local .zip file path."""
    start = time.time()
    is_zip = source.lower().endswith(".zip")

    with console.status(f"[bold cyan]{'Extracting' if is_zip else 'Cloning'} {source}..."):
        try:
            if is_zip:
                repo_path, repo_id = extract_zip(source)
                repo_name = source.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".zip")
                source_url = ""
            else:
                repo_path, repo_id = clone_github_repo(source)
                repo_name = source.rstrip("/").split("/")[-1].removesuffix(".git")
                source_url = source
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)

    try:
        with console.status("[bold cyan]Chunking, embedding, and indexing..."):
            try:
                result = run_ingestion_pipeline(repo_path, repo_id, repo_name, source_url)
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                sys.exit(1)
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)

    elapsed = round(time.time() - start, 2)
    console.print(f"[bold green]✓[/bold green] Indexed [bold]{result['repo_name']}[/bold] in {elapsed}s")
    console.print(
        f"  {result['total_files']} files -> {result['total_chunks']} chunks "
        f"({', '.join(result['languages']) or 'no languages detected'})"
    )
    console.print(f"  repo_id: [cyan]{result['repo_id']}[/cyan]")


@cli.command(name="repos")
def list_repos_cmd():
    """List all ingested repos."""
    repos = sqlite_client.list_repos()
    if not repos:
        console.print("No repos ingested yet. Run [bold]repomind ingest <url>[/bold] to get started.")
        return

    table = Table()
    table.add_column("Name")
    table.add_column("repo_id", style="cyan", overflow="fold")
    table.add_column("Files", justify="right")
    table.add_column("Chunks", justify="right")
    table.add_column("Languages")
    table.add_column("Ingested")
    for r in repos:
        table.add_row(
            r["name"], r["repo_id"], str(r["total_files"]), str(r["total_chunks"]),
            ", ".join(r["languages"]), r["created_at"],
        )
    console.print(table)


@cli.command()
@click.argument("question")
@click.option("--repo", "repo_ref", required=True, help="repo_id or a substring of the repo name")
def ask(question: str, repo_ref: str):
    """Ask a question about an ingested repo."""
    repo = _resolve_repo(repo_ref)

    with console.status("[bold cyan]Rewriting query, retrieving code, reranking..."):
        chunks, standalone_question, _rewritten, timings = prepare_query(repo["repo_id"], question, [])

    console.print()
    try:
        with timed(timings, "generate_ms"):
            for token in generate_answer_stream(standalone_question, chunks):
                console.print(token, end="")
    except Exception as e:
        console.print(f"\n[red]Answer generation failed: {e}[/red]")
        sys.exit(1)
    console.print("\n")
    timings["total_ms"] = round(sum(timings.values()), 1)

    citations = build_citations(chunks)
    if citations:
        table = Table(title="Citations", show_lines=False)
        table.add_column("File")
        table.add_column("Lines", justify="right")
        table.add_column("Symbol", style="magenta")
        for c in citations:
            table.add_row(c["file_path"], f"{c['start_line']}-{c['end_line']}", c["symbol_name"] or "-")
        console.print(table)

    total_s = timings.get("total_ms", sum(timings.values())) / 1000
    console.print(f"[dim]{total_s:.2f}s — {timings}[/dim]")


@cli.command()
@click.argument("repo_ref")
def sync(repo_ref: str):
    """Re-sync an ingested repo, only re-embedding files that changed since last sync."""
    repo = _resolve_repo(repo_ref)
    if not repo["source_url"]:
        console.print("[red]This repo was ingested from a zip upload and has no source URL to re-sync from.[/red]")
        sys.exit(1)

    start = time.time()
    with console.status(f"[bold cyan]Re-syncing {repo['name']}..."):
        try:
            repo_path, _ = clone_github_repo(repo["source_url"])
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)
        try:
            result = run_sync_pipeline(repo_path, repo["repo_id"])
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    elapsed = round(time.time() - start, 2)
    console.print(
        f"[bold green]✓[/bold green] Synced {repo['name']} in {elapsed}s — "
        f"{result['files_changed']} changed, {result['files_removed']} removed, "
        f"{result['files_unchanged']} unchanged"
    )


@cli.command()
@click.argument("repo_ref")
def delete(repo_ref: str):
    """Delete an ingested repo from the index."""
    repo = _resolve_repo(repo_ref)
    if not click.confirm(f"Delete '{repo['name']}' ({repo['repo_id']}) from the index?"):
        return
    delete_collection(repo["repo_id"])
    sqlite_client.delete_repo(repo["repo_id"])
    console.print(f"[bold green]✓[/bold green] Deleted {repo['name']}")


def main():
    cli()


if __name__ == "__main__":
    main()
