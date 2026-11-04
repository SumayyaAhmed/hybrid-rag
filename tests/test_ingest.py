"""Ingestion end-to-end on data/ with fake embeddings (spec 01)."""

from pathlib import Path

import pytest
from conftest import FakeEmbed, fake_count_tokens

from rag.db import pool
from rag.ingest import pipeline

pytestmark = pytest.mark.db


def counts() -> tuple[int, int, int]:
    with pool.connection() as conn:
        return conn.execute(
            "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM pdf_chunks), (SELECT count(*) FROM products)"
        ).fetchone()


def test_ingest_loads_all_documents_and_products(ingested):
    fake, _ = ingested
    documents, chunks, products = counts()
    assert documents == 4
    assert chunks > 0
    assert products == 15          # catalogue has 16 rows, 1 deliberately invalid
    assert fake.calls > 0


def test_second_ingest_is_a_no_op(ingested, monkeypatch):
    before = counts()
    fake = FakeEmbed()
    monkeypatch.setattr(pipeline, "embed", fake)
    monkeypatch.setattr(pipeline, "count_tokens", fake_count_tokens)
    lines = pipeline.ingest(Path("data"))
    assert counts() == before
    assert fake.calls == 0         # nothing re-embedded -> no Voyage calls in real life
    assert sum("already ingested" in line for line in lines) == 4


def test_chunks_have_valid_pages(ingested):
    with pool.connection() as conn:
        bad = conn.execute("SELECT count(*) FROM pdf_chunks WHERE page_start > page_end OR page_start < 1").fetchone()[0]
    assert bad == 0
