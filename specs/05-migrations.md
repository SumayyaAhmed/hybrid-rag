# 05 — Schema migrations (Alembic)

Status: **implemented** (2026-11-04)

## Problem
Today the schema lives in `db/init/*.sql`, mounted into `/docker-entrypoint-initdb.d`. Postgres runs those files **only when the
data volume is empty**. Consequences:
- Any schema change (e.g. [06](06-bm25-pg-textsearch.md)) means either `docker compose down -v` + full re-ingest
  (slow: Voyage is limited to 3 requests/min) or hand-typed SQL in psql that nobody records.
- There is no record of *which* schema version a database is on → no traceability.

## Decision: Alembic, with hand-written SQL
[Alembic](https://alembic.sqlalchemy.org) is the standard migration tool for Python + SQLAlchemy. Each schema change is a
Python file with `upgrade()` and `downgrade()`. Alembic stores the database's current revision in an `alembic_version` table
and runs whatever files are newer.

How we use it:
- **No ORM, no autogenerate.** The app keeps using psycopg + plain SQL. Migrations call `op.execute("""…SQL…""")`, so
  the SQL stays readable, including pgvector and bm25 DDL that autogenerate doesn't understand anyway.
- **SQLAlchemy is added as a dependency**, but only because Alembic needs it to connect. App code never imports it.
  The URL uses the psycopg 3 driver: `postgresql+psycopg://…`.
- **Readable revision ids**: `--rev-id 0001`, `0002`, … instead of random hashes, so order is obvious.

Trade-offs vs. a hand-rolled runner: +downgrades, +standard tool you'll meet at work, +`current`/`history` commands;
−two more dependencies (`alembic`, `sqlalchemy`), −`alembic_version` only stores the *current* revision (history =
the files in git + the changelog below).

## Layout
```
alembic.ini                         # script_location = db/migrations
db/
└── migrations/
    ├── env.py                      # reads DATABASE_URL from rag.config.settings; target_metadata = None
    ├── script.py.mako              # template for new revisions
    └── versions/
        ├── 0001_baseline.py        # vector extension + documents, pdf_chunks, products (= today's db/init SQL)
        └── 0002_bm25_replace_fts.py  # spec 06
```
`db/init/` is deleted and its mount removed from `docker-compose.yml`. The container starts with an empty database and
Alembic builds the schema.

## Rules
1. New change: `uv run alembic revision -m "short description" --rev-id NNNN`, then write `upgrade()` **and** `downgrade()`.
2. **Never edit a migration that has been applied anywhere.** Add a new one.
3. Each migration runs in a transaction (Postgres supports transactional DDL). If it fails, nothing is applied.
   So no `CREATE INDEX CONCURRENTLY`, which can't run in a transaction. Not needed at this data size.
4. Every revision's docstring names the spec that motivated it, and gets a line in the changelog below.

## Commands
```bash
uv run alembic upgrade head      # apply everything pending
uv run alembic current           # which revision is this DB on?
uv run alembic history           # list all revisions
uv run alembic downgrade -1      # undo the last one
uv run alembic stamp 0001        # mark as applied WITHOUT running (adopting an existing DB)
```

## Adopting Alembic on the existing database (no re-ingest)
The current DB already has the baseline tables, so we don't run 0001 on it:
```bash
uv run alembic stamp 0001        # "this DB is already at the baseline"
uv run alembic upgrade head      # runs 0002 only → data and embeddings are kept
```

## Fresh setup (replaces Phase 0 steps in 00)
```bash
docker compose up -d --build
uv run alembic upgrade head
uv run rag ingest
```

## Install
```bash
uv add alembic "sqlalchemy>=2"
```
This Mac is Intel with `no-build = true`, so check that both resolve to prebuilt wheels.

## Acceptance
- [x] `stamp 0001` + `upgrade head` on the current DB → `alembic current` shows `0002 (head)`, and `rag stats` still shows 27 chunks and 15 products.
- [x] `alembic upgrade head` again does nothing.
- [x] `alembic downgrade -1` restores the `tsv` columns + GIN indexes; `upgrade head` re-applies BM25.
- [x] `alembic upgrade head` on an empty database creates the full schema (tested on a scratch DB; full `make reset` incl. ingest not run yet).
- [x] No `import sqlalchemy` anywhere under `src/`.

## Changelog
| Revision | Spec | Change |
|---|---|---|
| 0001 | 00 | baseline: `vector` extension, documents, pdf_chunks, products |
| 0002 | 06 | install `pg_textsearch`, drop `tsv` columns/GIN indexes, add BM25 indexes |
