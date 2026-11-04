"""Postgres connection pool with the pgvector type registered on every connection."""

from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from rag.config import settings

pool = ConnectionPool(settings.database_url, configure=register_vector, min_size=1, max_size=4, timeout=5, open=True)


def check_embed_dim() -> None:
    """Fail fast if EMBED_DIM in .env doesn't match the vector(N) columns in the schema."""
    with pool.connection() as conn:
        rows = conn.execute(
            """SELECT c.relname, format_type(a.atttypid, a.atttypmod)
               FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
               WHERE c.relname IN ('pdf_chunks', 'products') AND a.attname = 'embedding'"""
        ).fetchall()
    expected = f"vector({settings.embed_dim})"
    for table, col_type in rows:
        if col_type != expected:
            raise RuntimeError(f"{table}.embedding is {col_type} but EMBED_DIM={settings.embed_dim}. Fix .env or the schema.")
