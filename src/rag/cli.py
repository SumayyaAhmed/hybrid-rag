"""Command line: rag ingest | stats | chunks | search | ask"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def ingest(path: Path = typer.Argument(Path("data")), only: str = typer.Option(None, help="pdf | catalogue")):
    """Load PDFs and the Excel catalogue into Postgres (safe to re-run)."""
    from rag.db import check_embed_dim
    from rag.ingest.pipeline import ingest as run_ingest

    check_embed_dim()
    for line in run_ingest(path, only):
        console.print(line)


@app.command()
def stats():
    """Row counts and token stats per document."""
    from rag.db import pool

    with pool.connection() as conn:
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM pdf_chunks), (SELECT count(*) FROM products)"
        ).fetchone()
        per_doc = conn.execute(
            """SELECT d.filename, d.page_count, count(c.id), min(c.token_count), round(avg(c.token_count)), max(c.token_count)
               FROM documents d LEFT JOIN pdf_chunks c ON c.document_id = d.id
               GROUP BY d.id ORDER BY d.filename"""
        ).fetchall()
    console.print(f"documents: {counts[0]}  pdf_chunks: {counts[1]}  products: {counts[2]}")
    table = Table("file", "pages", "chunks", "min tok", "avg tok", "max tok")
    for row in per_doc:
        table.add_row(*[str(v) for v in row])
    console.print(table)


@app.command()
def chunks(pdf: Path):
    """Preview how a PDF gets chunked (no database, no API key needed)."""
    from rag.clients import count_tokens
    from rag.config import settings
    from rag.ingest.chunker import chunk_pages
    from rag.ingest.pdf_loader import load_pdf

    for c in chunk_pages(load_pdf(pdf), count_tokens, settings.chunk_tokens, settings.chunk_overlap):
        pages = f"p.{c.page_start}" if c.page_start == c.page_end else f"pp.{c.page_start}-{c.page_end}"
        console.rule(f"chunk {c.chunk_index} | {pages} | {c.token_count} tokens | {c.section_title}")
        console.print(c.content)


@app.command()
def search(query: str, explain: bool = typer.Option(False, "--explain", help="show every retrieval stage")):
    """Run retrieval only (no LLM)."""
    from rag.retrieve.pipeline import run

    trace = run(query)
    if explain:
        for name, results in trace.searches.items():
            table = Table("rank", "key", "score", title=f"{name} ({len(results)} hits)")
            for rank, (key, score) in enumerate(results[:10], start=1):
                table.add_row(str(rank), key, f"{score:.4f}")
            console.print(table)

        table = Table("key", "ranks", "rrf", "rerank", "kept", "text", title="RRF -> rerank -> min-score filter")
        kept = {h.key for h in trace.kept}
        for hit in trace.reranked:
            ranks = " ".join(f"{n}#{r}" for n, r in hit.ranks.items())
            mark = "[green]yes[/]" if hit.key in kept else "[red]no[/]"
            table.add_row(hit.key, ranks, f"{hit.rrf_score:.4f}", f"{hit.rerank_score:.3f}", mark, hit.text[:60].replace("\n", " "))
        console.print(table)

    console.rule(f"{len(trace.kept)} kept")
    for hit in trace.kept:
        console.print(f"[bold]{hit.key}[/] rerank={hit.rerank_score:.3f}  {hit.text[:100].replace(chr(10), ' ')}")


@app.command()
def ask(query: str, show_context: bool = typer.Option(False, "--show-context", help="print exactly what the LLM received")):
    """Answer a question with citations."""
    from rag.generate.answer import answer

    result = answer(query)
    if show_context and result.used_llm:
        console.rule("context sent to the LLM")
        console.print(result.context, markup=False)
        console.rule()
    console.print(result.text, markup=False)
    if result.sources:
        console.print()
        for s in result.sources:
            console.print(f"[{s.tag}] {s.label}", markup=False)
    if not result.used_llm:
        console.print("[dim](no relevant sources found, LLM not called)[/]")
