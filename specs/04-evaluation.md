# 04 — Phase 4: Evaluation (simple)

## Goal
One number per stage that says whether the RAG works, from a small hand-written question set. No LLM judge: every check is string matching, so a failure is easy to read and trust.

## Files
```
eval/
├── questions.jsonl   # one question per line
├── run_eval.py       # uv run python eval/run_eval.py
└── results.json      # written by run_eval.py: kept sources + full answer per question
```

## Question format
```json
{"q": "How long do I have to send something back?", "expect": ["returns_policy.pdf#Return Window"], "facts": ["30 days"]}
{"q": "Do you have waterproof running shoes under 100?", "expect": ["sku:00232"], "facts": ["94.50"]}
{"q": "Do you sell lawnmowers?", "expect": [], "facts": []}
```
- `expect`: sources that must be kept, as `filename#section_title` or `sku:<sku>` — stable ids that survive re-ingesting (DB row ids don't). `[]` means the question is out of scope and must be refused.
- `facts`: strings that must appear in the answer (case-insensitive, whole words). A nested list means "any of these" (`["5 to 7", "5-7"]`).
- Write questions as a customer would, not copied from the PDFs, so semantic search is actually tested.

## Metrics
| Metric | Over | Passes when |
|---|---|---|
| Retrieval accuracy | in-scope | every `expect` source is among the kept hits |
| Answer accuracy | in-scope | every fact is in the answer |
| Citation accuracy | in-scope | the answer cites at least one expected source |
| Refusal accuracy | out-of-scope | 0 hits kept and the LLM was not called |
| Overall accuracy | all | retrieval + answer (in-scope), or refused (out-of-scope) |

`rank` (position of the first expected source in the kept list) is printed too.

## Notes
- One `run(query)` per question; generation reuses its hits (`answer_from_hits`), so each question costs 2 Voyage calls + at most 1 Gemini call.
- With Voyage's no-payment-method limit (3 requests/min) the 29 questions take ~15–20 min.
- **Gemini free tier allows only 20 requests/day for `gemini-2.5-flash`**, fewer than the 25 in-scope questions. So:
  - `--no-llm` measures retrieval + refusal accuracy with no Gemini calls.
  - Results are saved after every question; re-running resumes and only calls Gemini for questions without an answer yet. Spread a full run over two days, or switch `LLM_MODEL`.
  - `--fresh` ignores saved results.
- Use it to tune knobs: change `RERANK_MIN_SCORE`, `CHUNK_TOKENS` or `K_BM25` in `.env`, re-run, compare the numbers.
