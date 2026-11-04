"""Orchestrates ingestion: load -> chunk -> embed -> write. Safe to run twice."""

import hashlib
from pathlib import Path

import numpy as np
from psycopg.types.json import Jsonb

from rag.clients import count_tokens, embed
from rag.config import settings
from rag.db import pool
from rag.ingest.chunker import chunk_pages
from rag.ingest.excel_loader import content_hash, load_catalogue, render_search_text
from rag.ingest.pdf_loader import load_pdf


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ingest_pdf(path: Path) -> str:
    sha = file_sha256(path)
    with pool.connection() as conn:
        if conn.execute("SELECT 1 FROM documents WHERE sha256 = %s", (sha,)).fetchone():
            return f"{path.name}: already ingested, skipped"

        pages = load_pdf(path)
        chunks = chunk_pages(pages, count_tokens, settings.chunk_tokens, settings.chunk_overlap)
        if not chunks:
            return f"{path.name}: no text found (scanned PDF?), skipped"
        # Embed title + content so each chunk carries its section context.
        vectors = embed([f"{c.section_title or ''}\n{c.content}".strip() for c in chunks], input_type="document")

        with conn.transaction():  # all or nothing
            doc_id = conn.execute(
                "INSERT INTO documents (filename, sha256, page_count) VALUES (%s, %s, %s) RETURNING id",
                (path.name, sha, len(pages)),
            ).fetchone()[0]
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO pdf_chunks (document_id, chunk_index, page_start, page_end, section_title, content, token_count, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    [(doc_id, c.chunk_index, c.page_start, c.page_end, c.section_title, c.content, c.token_count, np.array(v))
                     for c, v in zip(chunks, vectors)],
                )
    tokens = [c.token_count for c in chunks]
    return f"{path.name}: {len(pages)} pages -> {len(chunks)} chunks (tokens min/avg/max {min(tokens)}/{sum(tokens) // len(tokens)}/{max(tokens)})"


def ingest_catalogue(path: Path) -> str:
    products, errors = load_catalogue(path)
    for err in errors:
        print(f"  skipped {err}")

    rows = [(p, render_search_text(p)) for p in products]
    with pool.connection() as conn:
        existing = dict(conn.execute("SELECT sku, content_hash FROM products").fetchall())
        changed = [(p, text) for p, text in rows if existing.get(p.sku) != content_hash(text)]
        if changed:
            vectors = embed([text for _, text in changed], input_type="document")
            with conn.transaction(), conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO products (sku, name, brand, category, price, currency, in_stock, attributes, description,
                                             search_text, content_hash, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (sku) DO UPDATE SET
                         name = EXCLUDED.name, brand = EXCLUDED.brand, category = EXCLUDED.category,
                         price = EXCLUDED.price, currency = EXCLUDED.currency, in_stock = EXCLUDED.in_stock,
                         attributes = EXCLUDED.attributes, description = EXCLUDED.description,
                         search_text = EXCLUDED.search_text, content_hash = EXCLUDED.content_hash,
                         embedding = EXCLUDED.embedding, updated_at = now()""",
                    [(p.sku, p.name, p.brand, p.category, p.price, p.currency, p.in_stock, Jsonb(p.attributes), p.description,
                      text, content_hash(text), np.array(v)) for (p, text), v in zip(changed, vectors)],
                )
    return f"{path.name}: {len(products)} ok, {len(errors)} skipped, {len(changed)} embedded/updated, {len(products) - len(changed)} unchanged"


def ingest(path: Path, only: str | None = None) -> list[str]:
    """`path` can be a folder (data/), a PDF folder, a single PDF, or the .xlsx file."""
    if path.is_dir():
        pdfs = sorted(path.rglob("*.pdf"))
        sheets = sorted(path.rglob("*.xlsx"))
    else:
        pdfs = [path] if path.suffix == ".pdf" else []
        sheets = [path] if path.suffix == ".xlsx" else []

    results = []
    if only in (None, "pdf"):
        results += [ingest_pdf(p) for p in pdfs]
    if only in (None, "catalogue"):
        results += [ingest_catalogue(s) for s in sheets]
    return results
