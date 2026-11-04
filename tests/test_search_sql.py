"""The two SQL searches against real Postgres: BM25 (spec 06) and pgvector (spec 02)."""

import pytest
from conftest import fake_embedding

from rag.db import pool
from rag.retrieve.keyword import keyword_search
from rag.retrieve.vector import vector_search

pytestmark = pytest.mark.db


def sku_of(conn, product_id: int) -> str:
    return conn.execute("SELECT sku FROM products WHERE id = %s", (product_id,)).fetchone()[0]


# Postgres picks the plan: with a tiny table it often prefers Seq Scan + Sort over the bm25 index.
# The two plans behave differently: the index returns only matching rows, the seq scan scores EVERY row
# (0 for non-matching ones). Results must be the same either way, so each BM25 test runs with both.
@pytest.fixture(params=["index scan", "seq scan"])
def conn(request, ingested):
    with pool.connection() as conn, conn.transaction(force_rollback=True):   # SET LOCAL + test rows vanish afterwards
        if request.param == "seq scan":
            conn.execute("SET LOCAL enable_indexscan = off")
        yield conn


def test_bm25_finds_sku_first(conn):
    results = keyword_search(conn, "products", "SKU 00123", k=20)
    assert sku_of(conn, results[0][0]) == "00123"


def test_bm25_nonsense_query_returns_nothing(conn):
    assert keyword_search(conn, "products", "lawnmower xyzzy", k=20) == []
    assert keyword_search(conn, "pdf_chunks", "lawnmower xyzzy", k=20) == []


def test_bm25_matches_words_in_section_title(conn):
    """The indexed expression is section_title || content, so a word only in the title must still match."""
    doc_id = conn.execute("SELECT id FROM documents LIMIT 1").fetchone()[0]
    chunk_id = conn.execute(   # rolled back by the conn fixture, never committed
        """INSERT INTO pdf_chunks (document_id, chunk_index, page_start, page_end, section_title, content, token_count, embedding)
           VALUES (%s, 999, 1, 1, 'Zanzibar Promise', 'Generic text about orders.', 4, %s) RETURNING id""",
        (doc_id, str(fake_embedding("x"))),
    ).fetchone()[0]
    results = keyword_search(conn, "pdf_chunks", "zanzibar", k=5)
    assert [r[0] for r in results] == [chunk_id]


def test_vector_search_nearest_first(ingested):
    with pool.connection() as conn:
        product_id, text = conn.execute("SELECT id, search_text FROM products ORDER BY sku LIMIT 1").fetchone()
        results = vector_search(conn, "products", fake_embedding(text), k=5)
    assert results[0][0] == product_id
    assert results[0][1] == pytest.approx(1.0, abs=1e-3)   # identical vector -> cosine similarity 1
    assert results[1][1] < 0.2                            # other fake vectors are nearly orthogonal
