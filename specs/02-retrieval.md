# 02 — Phase 2: Retrieval

## Goal
`retrieve(query) -> list[Hit]`: the few most relevant PDF chunks and/or products, or **an empty list** when nothing is truly relevant.

```python
class Hit(BaseModel):
    key: str              # "pdf:123" or "prod:45" — one id space across both tables
    source: Literal["pdf", "product"]
    text: str             # pdf content, or product search_text
    metadata: dict        # filename/pages/section, or sku/price/in_stock…
    ranks: dict           # {"vec_pdf": 3, "bm25_pdf": 1, …} for --explain
    rrf_score: float
    rerank_score: float | None
```

## Pipeline
```
query
 ├─ embed(query, input_type="query") # Voyage, see below
 ├─ vector search  pdf_chunks   top K_VEC
 ├─ vector search  products     top K_VEC
 ├─ BM25           pdf_chunks   top K_BM25
 ├─ BM25           products     top K_BM25
 ▼
RRF over the 4 ranked lists  → top RERANK_CANDIDATES
 ▼
vo.rerank(query, [hit.text ...], model=RERANK_MODEL)   # one API call
 ▼
drop rerank_score < RERANK_MIN_SCORE → sort desc → top FINAL_TOP_N
```

## Knobs (`config.py`)
| Name | Start value | Meaning |
|---|---|---|
| `K_VEC` | 20 | candidates per vector search |
| `K_BM25` | 20 | candidates per BM25 keyword search |
| `RRF_K` | 60 | RRF smoothing constant (standard value) |
| `RERANK_CANDIDATES` | 30 | how many fused hits go to the reranker |
| `RERANK_MIN_SCORE` | 0.50 | absolute floor (0–1). With `rerank-2.5` off-topic hits scored up to ~0.45, relevant ones 0.50+. **Tune by hand with `--explain`.** |
| `FINAL_TOP_N` | 6 | max hits passed to the LLM |

## 2A. Semantic search (pgvector)
```sql
SELECT id, 1 - (embedding <=> %(q)s) AS similarity
FROM pdf_chunks
ORDER BY embedding <=> %(q)s
LIMIT %(k)s;
```
- `<=>` = cosine distance (matches `vector_cosine_ops` in the HNSW index, so the index is used).
- Same query on `products`. Only the **order** matters downstream; similarity is kept for `--explain`.
- Optional: `SET hnsw.ef_search = 100;` for better recall at the cost of speed.

## 2B. Keyword search (BM25 via pg_textsearch)
Replaced Postgres FTS (`tsvector` + `ts_rank_cd`) in [06](06-bm25-pg-textsearch.md).
```sql
SELECT id, -((coalesce(section_title, '') || ' ' || content) <@> to_bm25query(%(query)s, 'pdf_chunks_bm25_idx')) AS score
FROM pdf_chunks
ORDER BY (coalesce(section_title, '') || ' ' || content) <@> to_bm25query(%(query)s, 'pdf_chunks_bm25_idx'), id
LIMIT %(k)s;
```
- Products: the same query on `search_text` with `products_bm25_idx`.
- `<@>` returns the BM25 score **negated**, so ascending `ORDER BY` puts the best rows first. We flip the sign so higher = better in `--explain`.
- The `ORDER BY` expression must match the indexed expression exactly, or the index isn't used.
- Rows that match **no** query word can come back with score 0. That happens when Postgres picks Seq Scan + Sort
  instead of the bm25 index, which it does for tiny tables with statistics. `keyword.py` drops them (`score > 0`), and the tests run both plans (spec 09).
- BM25 scores any matching word, which is like the old `FTS_MODE=or`, but rare words (IDF) weigh more. There is no AND mode.
- Keyword search shines on exact terms: SKUs, brand names, "warranty", model numbers, all things embeddings blur.
- Known noise: product `search_text` has labels ("SKU:", "Price:", "Product:"), so a query containing those words gives
  *every* product a tiny score (~0.03, vs ~2.4 for a real match). Harmless with 15 products (RRF + rerank sort it out).

## 2C. RRF (`fusion.py`, pure function)
```python
def rrf(ranked_lists: dict[str, list[str]], k: int = 60) -> dict[str, float]:
    scores = defaultdict(float)
    for name, keys in ranked_lists.items():
        for rank, key in enumerate(keys, start=1):
            scores[key] += 1.0 / (k + rank)
    return dict(sorted(scores.items(), key=lambda x: -x[1]))
```
- Why RRF: cosine similarity and BM25 scores live on different, incomparable scales. RRF uses only **rank position**, so no normalisation is needed and products vs PDF chunks can be fused fairly.
- An item found by both vector and BM25 gets two contributions → floats to the top.
- Keys are `"pdf:<id>"` / `"prod:<id>"` so the same id number in two tables never collides.
- After fusion, fetch full rows for the top `RERANK_CANDIDATES` keys (one `WHERE id = ANY(%s)` per table).

## 2D. Rerank with Voyage (`rerank.py`)
```python
res = vo.rerank(query, [h.text for h in candidates], model=RERANK_MODEL)
for r in res.results:                      # sorted best-first
    candidates[r.index].rerank_score = r.relevance_score   # 0–1
```
- A bi-encoder (embedding) compares two independent vectors; a cross-encoder reads **query and text together**, so it is much more accurate — but too slow to run over the whole DB. That's why it only sees ~30 candidates.
- Voyage rerankers are cross-encoders run as a hosted API: one request scores all ~30 candidates. `relevance_score` is already 0–1, so no sigmoid needed.
- Scores from `rerank-2.5` and `rerank-2.5-lite` are not on the same scale; re-tune `RERANK_MIN_SCORE` if you switch.
- Products are reranked on `search_text` (that's why it's rendered as readable text in phase 1).

## 2E. Min-score filter — handling "nothing relevant"
RRF and reranking always produce an ordering, even for "do you sell lawnmowers?" in a shoe shop — the top hit is then just the least-bad garden-related item. The filter makes "no answer" possible:
```python
kept = [h for h in reranked if h.rerank_score >= RERANK_MIN_SCORE]
```
- Empty `kept` → return `[]` → generation skips the LLM and says it couldn't find it (see 03).
- Optional second rule (relative cutoff): also drop hits `< 0.5 * top_score` so one strong hit isn't diluted by weak ones.
- Choose the threshold by hand: run a few in-scope and ~5 out-of-scope questions through `rag search --explain`, compare rerank scores of correct vs. wrong hits, pick the value that separates them.

## CLI
```
rag search "waterproof running shoes under 100" --explain
```
`--explain` prints one table per stage: vector ranks, BM25 ranks, RRF score, rerank score, kept/dropped. **This is the most useful learning tool in the project** — build it early.

## Acceptance
- [ ] `test_rrf.py`: item ranked #1 in two lists beats item #1 in one list; ties are deterministic.
- [x] A SKU query (`"SKU 00123"`) finds the product via BM25 even though vector search ranks it only #8.
- [ ] A paraphrase query ("can I send it back" → returns policy) finds the chunk via vectors even if BM25 misses it.
- [ ] An out-of-scope query returns `[]`.
- [ ] `--explain` shows all four lists and the final kept set.
