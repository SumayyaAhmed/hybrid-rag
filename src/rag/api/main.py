"""The FastAPI app. Run: `uv run fastapi dev` (entrypoint set in pyproject.toml), then open http://127.0.0.1:8000/docs.

See specs/10-api.md. Endpoints are plain `def` (not `async def`): psycopg, Voyage and Gemini all block, so FastAPI
runs each request in its threadpool and one slow LLM call doesn't hold up other requests.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rag.api.routers import admin, catalogue, chat, retrieval, system
from rag.db import check_embed_dim, pool
from rag.errors import UpstreamUnavailable


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: refuse to start if Postgres is unreachable or EMBED_DIM doesn't match the schema
    pool.wait(timeout=10)
    check_embed_dim()
    yield
    # shutdown: close pooled connections cleanly
    pool.close()


DESCRIPTION = """
Hybrid RAG for the fictional store **Stride Sports**: product catalogue + policy PDFs.

`/ask` answers with citations. `/search` shows what retrieval found (add `explain: true` for every stage).
The catalogue endpoints are plain database reads.
"""

TAGS = [
    {"name": "chat", "description": "Grounded answers with citations (retrieval + Gemini)."},
    {"name": "retrieval", "description": "Retrieval only: pgvector + BM25 → RRF → Voyage rerank → min-score filter."},
    {"name": "catalogue", "description": "Browse products and ingested documents (no AI)."},
    {"name": "admin", "description": "Ingestion. No auth yet: keep the API on localhost."},
    {"name": "system", "description": "Health and counts."},
]

app = FastAPI(title="Stride Sports RAG API", version="0.1.0", description=DESCRIPTION, openapi_tags=TAGS, lifespan=lifespan)

for module in (chat, retrieval, catalogue, admin, system):
    app.include_router(module.router)


@app.exception_handler(UpstreamUnavailable)
async def upstream_unavailable(request: Request, exc: UpstreamUnavailable) -> JSONResponse:
    """Voyage/Gemini rate limit, quota or outage: temporary and not our bug -> 503, not 500."""
    return JSONResponse(status_code=503, content={"detail": str(exc)}, headers={"Retry-After": "60"})
