# 06 — Replace Postgres FTS with BM25 (pg_textsearch by Tiger Data)

Status: **implemented** (2026-11-04). Depends on [05-migrations](05-migrations.md).

## Why
The keyword half of hybrid search currently uses built-in FTS ranking (`ts_rank_cd`). It only counts how often and how close
query words appear. BM25 (what Elasticsearch/Lucene use) adds two things:
- **IDF**: rare words count more. A match on "Trailblaze" or "warranty" outweighs a match on "shoe", which is in every product.
- **Length normalisation + saturation**: a long chunk doesn't win just by repeating a word many times (`k1`, `b`).

`pg_textsearch` (github.com/timescale/pg_textsearch) adds a `bm25` index type and a `<@>` scoring operator to Postgres.
It supports PG 17 and 18. Tokenising/stemming still uses a Postgres text search config (`english`), so "running" still
matches "run".

## What changes
| Area | Before | After |
|---|---|---|
| Docker image | `pgvector/pgvector:pg18` | own `db/Dockerfile`: same base + pg_textsearch built from source |
| Server config | none | `shared_preload_libraries=pg_textsearch` (required by the extension) |
| Schema | `tsv tsvector GENERATED … STORED` + GIN index on both tables | `tsv` columns dropped; `bm25` index per table |
| Query | `ts_rank_cd(tsv, q)` with `FTS_MODE` and/or | `ORDER BY <expr> <@> to_bm25query(query, index)` |
| Config | `K_FTS`, `FTS_MODE` | `K_BM25` (`FTS_MODE` removed: BM25 scores any matching word, so it behaves like OR mode) |
| `--explain` / `Hit.ranks` keys | `fts_pdf`, `fts_prod` | `bm25_pdf`, `bm25_prod` |

## 1. Docker image (`db/Dockerfile`)
```dockerfile
FROM pgvector/pgvector:pg18
ARG PG_TEXTSEARCH_VERSION=v1.5.1          # pinned release tag (verified with git ls-remote)
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential git ca-certificates postgresql-server-dev-18 \
 && git clone --depth 1 --branch ${PG_TEXTSEARCH_VERSION} https://github.com/timescale/pg_textsearch /tmp/pg_textsearch \
 && make -C /tmp/pg_textsearch && make -C /tmp/pg_textsearch install \
 && rm -rf /tmp/pg_textsearch \
 && apt-get purge -y build-essential git postgresql-server-dev-18 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*
```
Building from source inside the image works on both amd64 and arm64 Macs. Prebuilt release binaries exist for Linux but
would need per-architecture download logic.

`docker-compose.yml`:
```yaml
services:
  db:
    build: ./db
    image: hybrid-rag-db:pg18-bm25
    command: ["postgres", "-c", "shared_preload_libraries=pg_textsearch"]
    # volumes: pgdata only; the ./db/init mount is removed (see 05)
```
The `pgdata` volume is reused: same Postgres major version (18), so existing data stays.

## 2. Migration `db/migrations/versions/0002_bm25_replace_fts.py` (Alembic)
`upgrade()` runs this SQL via `op.execute`:
```sql
CREATE EXTENSION IF NOT EXISTS pg_textsearch;

-- drop built-in FTS (dropping the column also drops its GIN index)
ALTER TABLE pdf_chunks DROP COLUMN tsv;
ALTER TABLE products   DROP COLUMN tsv;

CREATE INDEX pdf_chunks_bm25_idx ON pdf_chunks
  USING bm25 ((coalesce(section_title, '') || ' ' || content)) WITH (text_config = 'english');

CREATE INDEX products_bm25_idx ON products
  USING bm25 (search_text) WITH (text_config = 'english');
```
`downgrade()` drops both bm25 indexes and re-adds the `tsv` generated columns + GIN indexes exactly as in 0001.
Generated columns are recomputed from existing rows, so nothing needs re-ingesting. The extension stays installed.
- **pdf_chunks** indexes title + content as one expression. Queries must repeat the **same expression** in `ORDER BY`.
- **products** indexes `search_text`, the rendered text already used for embedding and reranking (name, SKU, brand,
  category, price, attributes, description). All three retrieval signals then "see" the same text.
- `k1`/`b` stay at defaults (1.2 / 0.75). They are index options, so changing them means a new migration.

### What we lose (trade-offs)
- **Field weights.** FTS used `setweight` (title A over content B; SKU/name A, brand/category B, description C).
  A bm25 index scores one text with no weights. Alternative if needed later: a second bm25 index on `name` alone,
  run as an extra ranked list in RRF.
- **`simple` config for SKUs.** SKUs are now tokenised with `english`. Pure digit codes like `00123` survive unchanged,
  and the SKU acceptance check below verifies this.

## 3. Code
`src/rag/retrieve/keyword.py`: rewrite, keeping the same signature apart from the removed `mode`:
```python
# BM25_INDEX[table] = (indexed expression, index name); expression must match the migration exactly
BM25_INDEX = {
    "pdf_chunks": ("coalesce(section_title, '') || ' ' || content", "pdf_chunks_bm25_idx"),
    "products":   ("search_text",                                     "products_bm25_idx"),
}
```
```sql
SELECT id, -((<expr>) <@> to_bm25query(%(query)s, '<index>')) AS score   -- <@> is negative; flip so higher = better
FROM <table>
ORDER BY (<expr>) <@> to_bm25query(%(query)s, '<index>'), id
LIMIT %(k)s
```
- Keep only rows with `score > 0`, so rows matching no query word never enter RRF.
- `config.py`: `k_fts` → `k_bm25`, delete `fts_mode`.
- `retrieve/pipeline.py`, `cli.py`: rename rank keys and column labels `fts_*` → `bm25_*`.
- RRF needs no change: it only uses rank positions, so the new score scale doesn't matter.

## 4. Spec/doc updates when implemented
- `00-overview.md`: pipeline diagram, folder structure (`db/Dockerfile`, `alembic.ini`, `db/migrations/`), tech stack rows (Alembic, pg_textsearch), schema section → point to migrations.
- `02-retrieval.md`: replace section 2B and the `K_FTS`/`FTS_MODE` knobs.
- `04-evaluation.md`: remove the `FTS_MODE` tuning hint.
- `CLAUDE.md`: list specs 05 and 06, add status line.

## Rollout
1. Record a baseline: the retrieval-only eval from before the switch is saved as `eval/results_fts_baseline.json`.
2. `docker compose up -d --build` (new image, same volume).
3. `uv run alembic stamp 0001 && uv run alembic upgrade head` (applies 0002).
4. Code changes, then re-run the 02 acceptance checks and the eval.

Expect the eval to take several minutes because of the Voyage 3 requests/min limit.

## Acceptance
- [x] `\dx` shows `pg_textsearch` and `vector`; `SHOW shared_preload_libraries` includes `pg_textsearch`.
- [x] `\d pdf_chunks` / `\d products`: no `tsv` column, `*_bm25_idx` present.
- [x] `EXPLAIN` of the keyword query uses the bm25 index (Index Scan on `*_bm25_idx`).
- [x] SKU query (`"SKU 00123"`) still finds the product via `bm25_prod`.
- [x] Out-of-scope query still returns `[]`; paraphrase query still works (via vectors).
- [x] `rag search --explain` shows `bm25_pdf` / `bm25_prod` columns.
- [x] Eval accuracy is not worse than the baseline; if it is, write down why in Results.

## Results
Retrieval-only eval (`run_eval.py --no-llm`), 29 questions:

| | FTS (`ts_rank_cd`) | BM25 (pg_textsearch) |
|---|---|---|
| Retrieval (right sources kept) | 23/25 = 92% | 23/25 = 92% |
| Refusal (off-topic refused) | 4/4 = 100% | 4/4 = 100% |
| Overall | 27/29 = 93% | 27/29 = 93% |

- Every question has the same pass/fail and the same rank for the first expected source. The same 2 questions fail
  (PacerPro warranty, Trailblaze size swap). Both miss the **product** row because the 4 kept PDF chunks crowd it out,
  so the issue is in rerank/top-N, not in keyword search.
- Why no difference: with 27 chunks + 15 products, vector search already returns every product (`K_VEC=20 > 15`),
  and the reranker decides the final order. BM25's advantages (IDF, length normalisation) show up in the
  keyword-stage ranks (`--explain`), and would matter more with a larger corpus.
- Visible in `--explain`: `"SKU 00123"` → vector rank #8, BM25 rank #1, final rerank 0.799 (kept first).
- Observed: the bm25 index returns non-matching rows with score 0 (filtered in code); product label words ("SKU", "Price")
  give every product a ~0.03 score.
