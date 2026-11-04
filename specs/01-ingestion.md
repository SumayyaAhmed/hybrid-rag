# 01 — Phase 1: Ingestion

## Goal
`rag ingest data/` turns PDFs into chunks and the Excel catalogue into product rows, embeds them, and writes them to Postgres. Running it twice changes nothing.

## 1A. PDFs → `pdf_chunks`

### Steps
1. **Hash** the file (sha256). If `documents.sha256` exists → skip.
2. **Extract** with PyMuPDF page by page → `Page(number, text)`.
   - Clean: collapse whitespace, de-hyphenate line breaks (`exam-\nple` → `example`), normalise ligatures with NFKC (`ﬀ` → `ff`), merge a block that starts lowercase into the previous one (PyMuPDF sometimes splits a paragraph), drop repeated headers/footers (a line that appears on >50% of pages, digits ignored so `Page 1 of 2` matches `Page 2 of 2`; only for docs with ≥ 2 pages).
3. **Chunk** (`chunker.py`):
   - Measure length with the **embedder's tokenizer** (`vo.count_tokens`), not characters.
   - `CHUNK_TOKENS = 350`, `CHUNK_OVERLAP = 50`. Voyage accepts far longer inputs (32k tokens), but smaller chunks give sharper vectors and tighter citations.
   - Split recursively: headings → blank lines (paragraphs) → sentences → words. Only drop to a smaller separator when a piece is still too big.
   - Keep `page_start`/`page_end` for each chunk, and the nearest preceding heading as `section_title` (heuristic: ≤ 70 chars, ≤ 10 words, starts with a capital or digit, no ending punctuation, or larger font via PyMuPDF `get_text("dict")` if you want to go further).
4. **Embed** with `vo.embed(texts, model=EMBED_MODEL, input_type="document", output_dimension=EMBED_DIM)` in batches (`batch_size=128`).
   - `input_type="document"` here, `"query"` at search time (see 02). Voyage adds the right instruction internally, so no manual prefix.
   - Voyage vectors come back already normalised to length 1, so cosine distance works directly.
   - Retry on HTTP 429 with backoff (free-tier rate limits are low).
   - Embed `section_title + "\n" + content` so the chunk carries its context.
5. **Write** in one transaction: insert `documents` row, then all `pdf_chunks` (`executemany` / `COPY`). Failure → rollback, nothing half-ingested.

### Chunk data contract
```python
class Chunk(BaseModel):
    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None
    content: str
    token_count: int
```

## 1B. Excel → `products` (1 row = 1 product)

### Steps
1. **Read** with `pandas.read_excel(path, sheet_name=0, dtype=str)` (read as strings, parse yourself → no surprise floats for SKUs like `00123`).
2. **Map columns** via a config dict so the sheet's header names don't leak into code:
   ```python
   COLUMN_MAP = {"SKU": "sku", "Product Name": "name", "Brand": "brand",
                 "Category": "category", "Price": "price", "Stock": "in_stock",
                 "Description": "description"}
   # every unmapped column → attributes JSONB
   ```
3. **Validate** each row with a pydantic `Product` model. Bad rows → log `row number + reason`, skip, continue. Print a summary at the end (`412 ok, 3 skipped`).
4. **Render `search_text`** — the text the embedder and the reranker will see:
   ```
   Product: Trailblaze Running Shoe
   SKU: 00123                      ← needed so the reranker can match SKU queries
   Brand: Stride | Category: Footwear > Running
   Price: 89.99 USD | In stock: yes
   Attributes: color=blue, size=42, material=mesh
   Description: Lightweight shoe with ...
   ```
   One product = one vector. Don't chunk products (descriptions are short). If a description is huge, truncate to the token limit.
5. **Hash** `search_text` → `content_hash`. **Upsert** on `sku`:
   - hash unchanged → skip (no re-embedding)
   - hash changed / new → embed and `INSERT … ON CONFLICT (sku) DO UPDATE`
6. (Optional) delete products whose SKU disappeared from the sheet.

## CLI
```
rag ingest data/            # both
rag ingest data/pdfs --only pdf
rag ingest data/catalogue.xlsx --only catalogue
rag stats                   # counts per table, avg tokens per chunk
rag chunks data/pdfs/returns_policy.pdf   # preview chunking only (no DB, no API key)
```

## Acceptance
- [ ] Re-running ingest on the same inputs inserts 0 rows and makes 0 embedding calls.
- [ ] No chunk has `token_count > 512`; print min/avg/max per document.
- [ ] Every chunk has a valid `page_start ≤ page_end`.
- [ ] `products` count == valid rows in the sheet; skipped rows are logged with reasons.
- [ ] Spot check: `SELECT content FROM pdf_chunks ORDER BY random() LIMIT 3` reads like coherent text (not mid-word cuts, no header/footer junk).
- [ ] Unit tests: chunker respects size/overlap; excel loader handles empty price, `"Yes"/"no"/"0"` stock values, SKUs with leading zeros.

## Concepts to notice
- **Chunk size is a trade-off**: small chunks = precise vectors but lose context; big chunks = more context but a blurrier vector. Try 200 vs 350 vs 500 later and compare results with `rag search --explain`.
- **Overlap** keeps a sentence that straddles a boundary findable from both sides.
- **The product's `search_text` is a design decision**: whatever you put in it is what semantic search, FTS weighting and the reranker can "see".
