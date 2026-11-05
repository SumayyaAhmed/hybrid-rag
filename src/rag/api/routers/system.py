"""/health and /stats."""

import psycopg
from fastapi import APIRouter, HTTPException

from rag.api.dependencies import DbConn
from rag.api.schemas import Health, Stats
from rag.db import pool

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> Health:
    """Is the API up and can it reach Postgres? Uses the pool directly so a dead DB gives 503, not a 500."""
    try:
        with pool.connection(timeout=2) as conn:
            revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    except (psycopg.Error, psycopg.pool.PoolTimeout) as e:
        raise HTTPException(status_code=503, detail=f"database unreachable: {e}") from e
    return Health(status="ok", database="ok", schema_revision=revision[0] if revision else None)


@router.get("/stats")
def stats(conn: DbConn) -> Stats:
    documents, pdf_chunks, products = conn.execute(
        "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM pdf_chunks), (SELECT count(*) FROM products)"
    ).fetchone()
    return Stats(documents=documents, pdf_chunks=pdf_chunks, products=products)
