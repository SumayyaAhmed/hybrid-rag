# 00 — Overview: Hybrid RAG for E-commerce (learning project)

## Goal
Answer shopper questions using two knowledge sources:
- **PDFs** (policies, manuals, guides), stored **chunk-wise**
- **Excel catalogue**, stored **1 row = 1 product**

Pipeline:

```
            ┌── pgvector (semantic) ──┐
query ──────┤                         ├── RRF fuse ── Voyage rerank ── min-score filter ── Gemini answer
            └── BM25 (keyword) ───────┘   ← pg_textsearch, see 06
       (each run on pdf_chunks AND products)
```

## Phases
| Phase | Spec | Output |
|---|---|---|
| 0 — Setup | this file | Docker Postgres 18 + pgvector, schema, Python env |
| 1 — Ingestion | [01-ingestion.md](01-ingestion.md) | PDFs + Excel → chunks/rows → embeddings → tables |
| 2 — Retrieval | [02-retrieval.md](02-retrieval.md) | vector + BM25 → RRF → rerank → threshold |
| 3 — Generation | [03-generation.md](03-generation.md) | grounded answer with citations |
| 4 — Eval | [04-evaluation.md](04-evaluation.md) | accuracy per stage from a small question set |
| Migrations | [05-migrations.md](05-migrations.md) | Alembic: versioned schema changes, no re-ingest |
| BM25 | [06-bm25-pg-textsearch.md](06-bm25-pg-textsearch.md) | keyword search: Postgres FTS → pg_textsearch BM25 |
| Makefile | [07-makefile.md](07-makefile.md) | short commands: `make help` |
| App container | [08-app-container.md](08-app-container.md) | run chat / CLI / Alembic in Docker |

## Folder structure
```
hybrid-rag/
├── docker-compose.yml          # db: postgres 18 + pgvector + pg_textsearch; app: the Python app (profile "app", spec 08)
├── Dockerfile                  # app image: python 3.12 + uv sync --frozen (spec 08)
├── .dockerignore               # keeps .env (API keys) out of the image
├── Makefile                    # short commands, `make` lists them (spec 07)
├── alembic.ini                 # Alembic config (spec 05)
├── .env.example                # copy to .env
├── pyproject.toml              # managed by uv
├── app.py                      # interactive chat loop: `uv run python app.py`, type exit to quit
├── specs/                      # these files (source of truth)
├── db/
│   ├── Dockerfile              # pgvector/pgvector:pg18 + pg_textsearch built from source (spec 06)
│   └── migrations/             # Alembic (spec 05)
│       ├── env.py              # reads DATABASE_URL from rag.config
│       └── versions/           # 0001_baseline.py, 0002_bm25_replace_fts.py, …
├── data/                       # sample data for the fictional store "Stride Sports"
│   ├── pdfs/                   # returns, shipping, warranty, privacy policies (2 pages each)
│   └── catalogue.xlsx          # 15 products + 1 deliberately invalid row
├── scripts/
│   └── make_sample_data.py     # regenerates everything in data/
├── src/rag/
│   ├── config.py               # pydantic-settings: reads .env, all tunable knobs
│   ├── db.py                   # psycopg connection pool + pgvector registration
│   ├── clients.py              # lazy Voyage + Gemini clients, embed()/rerank()/count_tokens() helpers
│   ├── ingest/
│   │   ├── pdf_loader.py       # PDF → pages (text + page number)
│   │   ├── chunker.py          # pages → chunks (token-aware, overlap)
│   │   ├── excel_loader.py     # xlsx → validated Product rows
│   │   └── pipeline.py         # orchestration, idempotency, batching
│   ├── retrieve/
│   │   ├── models.py           # Hit
│   │   ├── vector.py           # semantic search on both tables
│   │   ├── keyword.py          # BM25 (pg_textsearch) on both tables
│   │   ├── fusion.py           # RRF (pure function, unit tested)
│   │   ├── rerank.py           # Voyage rerank + min score
│   │   └── pipeline.py         # retrieve(query) -> list[Hit]
│   ├── generate/
│   │   ├── prompts.py          # system prompt + context template
│   │   ├── llm.py              # thin Gemini wrapper: complete(system, user)
│   │   └── answer.py           # answer(query) -> Answer(text, sources)
│   └── cli.py                  # `rag ingest`, `rag stats`, `rag chunks`, `rag search --explain`, `rag ask`
├── eval/
│   ├── questions.jsonl         # 29 hand-written questions → expected sources + facts
│   └── run_eval.py
└── tests/
    ├── test_chunker.py
    ├── test_rrf.py
    └── test_excel_loader.py
```

## Tech stack
| Concern | Choice | Why |
|---|---|---|
| Python | 3.12 | stable, all libs support it |
| Env / deps | `uv` (`uv init`, `uv add …`, `uv run …`) | fast, one lockfile |
| DB | own image `db/Dockerfile` = `pgvector/pgvector:pg18` + pg_textsearch | Postgres 18 with pgvector; BM25 added (spec 06) |
| Keyword search | `pg_textsearch` (Tiger Data) `bm25` index + `<@>` | BM25 ranking (IDF, length normalisation) inside Postgres |
| Migrations | `alembic` (+ `sqlalchemy`, only as Alembic's connection layer) | versioned schema changes; app code stays psycopg + SQL |
| DB driver | `psycopg[binary,pool]` v3 + `pgvector` (python pkg) | native vector type adaptation |
| PDF parsing | `pymupdf` | fast, gives per-page text |
| Excel | `pandas` + `openpyxl` | read xlsx |
| Validation / config | `pydantic`, `pydantic-settings` | typed rows, `.env` config |
| Embeddings | Voyage AI `voyage-4-lite` via `voyageai` SDK (1024 dims, `input_type` = `document` / `query`) | hosted, strong retrieval quality, free token allowance; no local model download |
| Reranker | Voyage AI `rerank-2.5` via `voyageai` SDK (`vo.rerank`) | hosted cross-encoder, same key as embeddings; `rerank-2.5-lite` if you want faster/cheaper |
| Tokenizer for chunking | Voyage's tokenizer (`vo.count_tokens(texts, model=EMBED_MODEL)`) | chunk sizes measured in the model's real tokens |
| LLM | Google Gemini `gemini-2.5-flash` via `google-genai` SDK (free tier) | free for learning; swap behind `llm.py` |
| CLI | `typer` + `rich` | readable `--explain` tables |
| Tests | `pytest` | |

Install:
```bash
uv init --python 3.12
uv add "psycopg[binary,pool]" pgvector pymupdf pandas openpyxl pydantic pydantic-settings \
       voyageai google-genai typer rich alembic "sqlalchemy>=2"
uv add --dev pytest
```
> **Intel Mac:** newer `onnxruntime`, `cryptography` and `pymupdf` releases ship no x86_64 macOS wheels, so `pyproject.toml` sets
> `[tool.uv] required-environments = ["sys_platform == 'darwin' and platform_machine == 'x86_64'"]` and `no-build = true`.
> uv then picks the newest versions with prebuilt wheels instead of compiling from source.

## Phase 0 — Setup

### docker-compose.yml
See [docker-compose.yml](../docker-compose.yml). It builds `db/Dockerfile` and starts Postgres with
`shared_preload_libraries=pg_textsearch`. The `pgdata` volume is mounted at `/var/lib/postgresql`, because PG18 images moved the data dir there.
There are no init scripts: the schema comes from Alembic.

### First start
```bash
make up        # docker compose up -d --build --wait
make migrate   # alembic upgrade head
make ingest
```

### .env.example
```
DATABASE_URL=postgresql://rag:rag@localhost:5432/rag
VOYAGE_API_KEY=
EMBED_MODEL=voyage-4-lite
EMBED_DIM=1024
RERANK_MODEL=rerank-2.5
GEMINI_API_KEY=
LLM_MODEL=gemini-2.5-flash
```
> `EMBED_DIM` must match `vector(1024)` in the schema. Voyage's `output_dimension` also allows 256/512/2048; changing it means changing the schema and re-embedding everything.
> **Voyage free tier:** new accounts get free tokens (check voyageai.com pricing), but without a payment method on file the rate limits are very low (a few requests/min). Add a card to lift the limits; the free tokens still apply first.
> **Gemini free tier:** get a key at aistudio.google.com. Limits are per project and per model (low requests/min and /day) and change often; expect HTTP 429 and retry with backoff. Free-tier prompts may be used by Google to improve its products, so don't send real customer data.

### Schema
Defined by the Alembic migrations in `db/migrations/versions/` (history in [05](05-migrations.md#changelog)). Current shape:
- `documents(id, filename, sha256 UNIQUE, page_count, ingested_at)`
- `pdf_chunks(id, document_id → documents, chunk_index, page_start, page_end, section_title, content, token_count, embedding vector(1024))`
  with an HNSW index on `embedding` and a `bm25` index on `section_title || ' ' || content`
- `products(id, sku UNIQUE, name, brand, category, price, currency, in_stock, attributes jsonb, description, search_text, content_hash, embedding vector(1024), updated_at)`
  with HNSW on `embedding`, `bm25` on `search_text`, and b-tree indexes on `category` and `price`

### Phase 0 acceptance
- [x] `make up` → `make psql` → `\dx` shows `vector` and `pg_textsearch`
- [x] `\d pdf_chunks` and `\d products` show `embedding vector(1024)` and a `*_bm25_idx` index
- [x] `uv run python -c "from rag.db import pool"` connects without error
- [x] Embedding dim in `.env` == dim in schema (assert this at startup)
