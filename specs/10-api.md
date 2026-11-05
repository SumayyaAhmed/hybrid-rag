# 10 — HTTP API (FastAPI backend)

Status: **implemented** (2026-11-05)

## Goal
Expose the existing RAG (retrieve → rerank → answer) as an HTTP API, so a web or mobile frontend (or `curl`) can use it.
The API is a **thin layer**. It calls the same functions as the CLI and the chat loop (`answer()`, `run()`, `ingest()`),
and no RAG logic moves into it.

Sources: official FastAPI docs, read 2026-11-05 (FastAPI **0.162.0**, Python ≥ 3.10): Bigger Applications, Async,
Lifespan Events, Dependencies (+ with yield), Response Model, Handling Errors, Settings, Testing (+ dependency
overrides), FastAPI CLI, Docker, Metadata, Server-Sent Events.

## Endpoints
| Method | Path | Tag | Request | Response | Calls |
|---|---|---|---|---|---|
| GET | `/health` | system | – | `{status, database, schema_revision}` | `SELECT 1` + `alembic_version` |
| GET | `/stats` | system | – | `{documents, pdf_chunks, products, per_document[]}` | same SQL as `rag stats` |
| POST | `/ask` | chat | `{query, show_context?: bool}` | `{answer, sources[], used_llm, context?}` | `answer(query)` |
| POST | `/search` | retrieval | `{query, explain?: bool}` | `{hits[]}`, plus `{searches, fused, reranked}` when `explain` | `run(query)` |
| GET | `/products` | catalogue | query: `category?, in_stock?, max_price?, limit=20, offset=0` | `Product[]` | plain SQL, no AI |
| GET | `/products/{sku}` | catalogue | – | `Product` or **404** | plain SQL |
| GET | `/documents` | catalogue | – | `Document[]` (filename, pages, chunk count) | plain SQL |
| GET | `/documents/{id}/chunks` | catalogue | – | `Chunk[]` or **404** | plain SQL |
| POST | `/ingest` | admin | `{only?: "pdf" \| "catalogue"}` | `{lines[]}` | `ingest(Path("data"), only)` |

FastAPI also generates interactive docs automatically: **`/docs`** (Swagger UI), `/redoc`, `/openapi.json`.

- `POST` for `/ask` and `/search`: the question goes in a JSON body, not the URL. It can be long, and URLs end up in logs.
- `/search?explain` returns the same per-stage data as `rag search --explain`, so a UI can show every stage side by side.
- `/products` and `/documents` are plain database browsing, useful for a frontend and for checking what's ingested.
- `/ingest` calls Voyage (slow, rate-limited). There is **no auth** in this phase (see Non-goals), so the port is only
  meant to be reachable locally.

## Package structure
Follows the docs' "Bigger Applications" layout (`main.py` + `dependencies.py` + `routers/`), placed inside the existing
`rag` package so it can import `rag.*` directly:
```
src/rag/api/
├── __init__.py
├── main.py            # app = FastAPI(title=…, lifespan=lifespan, openapi_tags=…); include_router(...); exception handlers
├── dependencies.py    # DbConn = Annotated[Connection, Depends(get_conn)]  (yield: borrow from pool, give back after)
├── schemas.py         # request/response Pydantic models (AskRequest, AskResponse, SearchRequest, Product, …)
└── routers/
    ├── __init__.py
    ├── system.py      # /health, /stats
    ├── chat.py        # /ask
    ├── retrieval.py   # /search
    ├── catalogue.py   # /products, /products/{sku}, /documents, /documents/{id}/chunks
    └── admin.py       # /ingest
```
`pyproject.toml`:
```toml
[tool.fastapi]
entrypoint = "rag.api.main:app"     # documented by FastAPI CLI; `fastapi dev` / `fastapi run` find the app from this
```

## Design decisions (each from the docs)
1. **`def`, not `async def`, for every endpoint.** psycopg (sync pool), Voyage and Gemini calls all block.
   The Async page: if a library "doesn't have support for using `await` … declare your path operation functions … with
   just `def`". FastAPI then runs each request in a threadpool, so one slow Gemini call doesn't block other requests.
2. **Lifespan, not `@app.on_event`** (which is deprecated). Startup: wait for the pool to connect and run
   `check_embed_dim()`. If either fails, the API refuses to start. Shutdown: `pool.close()`.
3. **Database connection as a `yield` dependency** (`dependencies.py`):
   ```python
   def get_conn():
       with pool.connection() as conn:   # borrowed from the existing psycopg pool
           yield conn                    # returned to the pool after the response
   DbConn = Annotated[Connection, Depends(get_conn)]
   ```
   Endpoints write `conn: DbConn`, in the `Annotated` style the docs recommend. Tests can replace it with `app.dependency_overrides`.
4. **Pydantic models for every request and response** in `schemas.py`, used as return-type annotations. FastAPI then
   validates input (bad body → **422** automatically), filters the output, and documents everything in `/docs`.
   The existing `Hit` and `Answer` models are reused where they fit.
5. **Errors** (Handling Errors page):
   - unknown SKU / document → `HTTPException(404)`
   - empty `query` → 422 via a Pydantic constraint (`min_length=1`, `max_length=1000`)
   - Gemini quota used up / Gemini 503 / Voyage rate limit after retries → a new `UpstreamUnavailable` exception
     (raised in `llm.py` / `clients.py` instead of the current plain `RuntimeError`), mapped by one
     `@app.exception_handler` to **503** `{"detail": "…try again later"}`.
   - "nothing relevant found" is **not** an error: `/ask` returns 200 with the fallback text and `used_llm: false`.
6. **Settings**: reuse the existing `rag.config.settings` (pydantic-settings already reads `.env`).
   The docs' `@lru_cache get_settings()` dependency pattern exists so settings can be overridden in tests. Our tests
   already set env vars before import (conftest), so a second settings mechanism isn't added.
7. **Metadata**: `title="Stride Sports RAG API"`, `version="0.1.0"`, a Markdown `description`, and `openapi_tags` for
   system / chat / retrieval / catalogue / admin, so `/docs` is grouped and readable.

## Running it
- Install: `uv add "fastapi[standard]"` (the docs' install command; includes uvicorn, the `fastapi` CLI, and httpx for TestClient).
- Local dev: `uv run fastapi dev` → http://127.0.0.1:8000/docs, auto-reload on code change.
- Container (spec 08): a new compose service **`api`**, same image as `app`, exec-form command
  `["fastapi", "run", "--port", "8000"]` (the docs require exec form so lifespan shutdown runs), port `8000:8000`,
  `DATABASE_URL` pointing at `db`. It has **no profile**, so `make up` starts db + api. The interactive `app` service stays as it is.
  `--proxy-headers` isn't needed: there is no reverse proxy.
- Makefile: `api` (= `uv run fastapi dev`), `api-logs`.

## Tests (added to CI, spec 09)
FastAPI's `TestClient` (needs httpx, included in `fastapi[standard]`); test functions are normal `def`.
| File | Marker | Tests |
|---|---|---|
| `test_api.py` | unit | `/ask` with fake `answer` → 200 + sources; no hits → `used_llm: false`; empty query → 422; `UpstreamUnavailable` → 503; `/docs` and `/openapi.json` respond |
| `test_api_db.py` | `db` | `/health` ok + revision `0002`; `/products/00123` → 200, `/products/99999` → 404; `/products?category=…` filters; `/search` with fake embed/rerank → SKU first, `explain` has 4 lists; `/stats` counts |

## Non-goals (this phase)
- **Auth / API keys.** Needed before exposing beyond localhost, especially `/ingest`. That would be its own spec.
- **Streaming answers (SSE).** FastAPI has built-in `EventSourceResponse` (since 0.135.0). It needs Gemini streaming
  in `llm.py` first, so it's a good follow-up spec.
- **CORS.** Only needed when a browser frontend on another origin calls the API. Add it together with the frontend.
- **Conversation memory.** Each `/ask` is independent, the same as the chat loop today.

## Acceptance
- [x] `/docs` lists all endpoints grouped by tag (checked via the docker `api` service and `/openapi.json`).
- [x] `curl -X POST localhost:8000/ask -d '{"query":"what is the return window?"}' -H 'content-type: application/json'` → answer with sources. (2026-11-05: 200 in 2.8 s, "30 days … Stride Club 60 days [S1]", cited returns_policy.pdf p.1.)
- [x] Off-topic `/ask` → 200, fallback text, `used_llm: false`.
- [x] `/products/99999` → 404; `{"query": ""}` → 422; Gemini unavailable → 503 (seen live: real Gemini outage → 503 + Retry-After).
- [x] `make up` starts db + api; `curl localhost:8000/health` → ok.
- [x] `make ci` passes with the new tests (30 unit + 21 integration).

## Implementation notes
- FastAPI 0.162: `app.routes` holds included routers, not flat routes, so use `app.openapi()["paths"]` to list endpoints.
- `UpstreamUnavailable(RuntimeError)` lives in `src/rag/errors.py`. `llm.py` raises it for Gemini quota/503 and `clients.py` for a
  Voyage rate limit after all retries. It subclasses `RuntimeError`, so the chat loop and CLI behave as before.
- Tests use `TestClient(app)` **without** `with`, so the lifespan doesn't run. Otherwise its `pool.close()` would close the
  shared pool for the tests that follow.
- Compose `api` publishes `127.0.0.1:8000` (localhost only, no auth). Its healthcheck uses Python's `urllib`, because the slim image has no curl.

## Known issue: no timeout on hosted calls
Observed 2026-11-05: with Gemini overloaded, one `/ask` took **6+ minutes** before returning 503. That was 3 retries with backoff,
then a final attempt that hung, because `google-genai` calls have no timeout set. Voyage retries can add up to ~2 min more.
Fine for a CLI, bad for an HTTP API. **Still open**: the successful retest only means Gemini was healthy again; nothing limits a hung call yet. Follow-up spec: a per-call timeout (`genai` `http_options`), fewer retries in API
mode, or an overall request deadline.
