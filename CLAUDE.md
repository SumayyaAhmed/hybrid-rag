# Hybrid RAG (e-commerce) — learning project

Spec-driven. `specs/` is the source of truth; read the relevant spec before writing code and update the spec if a decision changes.

- `specs/00-overview.md` — folder structure, tech stack, Phase 0 (Docker pg18 + pgvector, schema)
- `specs/01-ingestion.md` — Phase 1: PDFs → chunks, Excel → 1 row per product, embeddings
- `specs/02-retrieval.md` — Phase 2: pgvector + BM25 → RRF → cross-encoder rerank → min-score filter
- `specs/03-generation.md` — Phase 3: grounded LLM answer with citations
- `specs/04-evaluation.md` — Phase 4: 29-question test set, string-match accuracy (`uv run python eval/run_eval.py`)
- `specs/05-migrations.md` — Alembic migrations in `db/migrations/versions/` (hand-written SQL, no ORM)
- `specs/06-bm25-pg-textsearch.md` — keyword search via pg_textsearch BM25 (replaced Postgres FTS)
- `specs/07-makefile.md` — `make` targets for common commands

Workflow: for every change, write/update the spec in `specs/` first, then implement. Schema changes = new Alembic revision (`make migration M="…"`), never edit an applied one.

## Context
- Goal is understanding the concepts, not production. Prefer clear, readable code over abstractions; explain trade-offs.
- Python 3.12 with `uv` (`pyproject.toml` + `uv.lock`); Postgres runs in Docker (`db/Dockerfile`: `pgvector/pgvector:pg18` + pg_textsearch).
- Embeddings: Voyage AI (`voyage-4-lite`, 1024 dims). Reranker: Voyage AI (`rerank-2.5`). LLM: Google Gemini free tier (`gemini-2.5-flash`) via `google-genai`.
- All three are hosted APIs, so nothing runs a model locally; keys live in `.env`.
- Build `rag search --explain` early — it shows each retrieval stage side by side.

## Status
- [x] Specs written
- [x] Phase 0 — docker-compose.yml, db/init/*.sql, pyproject.toml
- [x] Sample data — `scripts/make_sample_data.py` → `data/` (fictional store "Stride Sports")
- [x] Phase 1 — ingestion (4 PDFs → 27 chunks, 15 products; re-run is a no-op)
- [x] Phase 2 — retrieval (RERANK_MIN_SCORE tuned to 0.50; SKU, paraphrase, out-of-scope checks pass)
- [x] Phase 3 — generation (Gemini thinking disabled to avoid cut-off answers)
- [x] app.py — interactive chat loop over answer()
- [x] Phase 4 — eval (eval/questions.jsonl + eval/run_eval.py)
- [x] Alembic migrations (05), BM25 via pg_textsearch (06), Makefile (07)
- Voyage account has no payment method → 3 requests/min; clients.py waits 20s and retries
