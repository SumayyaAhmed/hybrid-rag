"""Alembic migrations (spec 05) and the resulting schema (spec 06)."""

import psycopg
import pytest
from conftest import ADMIN_URL, TEST_URL, alembic, recreate_database

pytestmark = pytest.mark.db


def test_upgrade_downgrade_upgrade():
    """Every downgrade must work too, on a scratch database of its own (rag_test stays at head)."""
    name = "rag_test_migrations"
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{name}"
    recreate_database(name)
    try:
        alembic("upgrade", "head", url)
        alembic("downgrade", "base", url)
        alembic("upgrade", "head", url)
    finally:
        with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


def test_schema_at_head():
    with psycopg.connect(TEST_URL) as conn:
        extensions = {r[0] for r in conn.execute("SELECT extname FROM pg_extension")}
        indexes = {r[0] for r in conn.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")}
        tsv_columns = conn.execute("SELECT count(*) FROM information_schema.columns WHERE column_name = 'tsv'").fetchone()[0]
    assert {"vector", "pg_textsearch"} <= extensions
    assert {"pdf_chunks_bm25_idx", "products_bm25_idx", "pdf_chunks_embedding_idx", "products_embedding_idx"} <= indexes
    assert tsv_columns == 0   # built-in FTS columns were dropped in 0002
