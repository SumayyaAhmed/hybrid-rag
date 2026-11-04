# 03 — Phase 3: Generation

## Goal
`answer(query) -> Answer`: a helpful, grounded reply that uses only retrieved hits, cites them, and admits when it doesn't know.

```python
class Answer(BaseModel):
    text: str
    sources: list[Source]     # what was cited, for display
    used_llm: bool            # False when retrieval returned nothing

class Source(BaseModel):
    tag: str                  # "S1"
    key: str                  # "pdf:123" / "prod:45"
    label: str                # "returns_policy.pdf p.3" / "Trailblaze Running Shoe (SKU 00123)"
```

## Flow
1. `hits = retrieve(query)`
2. **If `hits == []`** → return a fixed fallback (`"I couldn't find that in our catalogue or policies. Could you rephrase or tell me more?"`), `used_llm=False`. No LLM call → no hallucination, no cost.
3. Build context blocks, tag each `[S1]…[Sn]`:
   ```
   [S1] (policy) returns_policy.pdf, pages 3–4, section "Return window"
   Items can be returned within 30 days ...

   [S2] (product) SKU 00123
   Product: Trailblaze Running Shoe
   Price: 89.99 USD | In stock: yes
   ...
   ```
   For products, build the block from **DB columns** (price, stock), not from free text, so the numbers the LLM sees are authoritative.
4. Call the LLM with system prompt + context + question. `temperature` low (0–0.3), `max_output_tokens` ~500.
5. Parse `[Sn]` tags from the reply → `sources` (only the ones actually cited).

## System prompt (`prompts.py`)
```
You are a shopping assistant for <Store>.
Answer ONLY from the sources provided between <sources> tags.
- Cite every factual claim with its tag, e.g. [S2].
- Prices, stock and policies must come from the sources exactly; never estimate them.
- If the sources don't contain the answer, say so plainly and suggest what the customer could ask instead.
- When recommending products, list at most 3 with name, price and one reason each.
- Be concise.
```
User message:
```
<sources>
{context_blocks}
</sources>

Question: {query}
```

## LLM wrapper (`llm.py`)
- One function: `complete(system: str, user: str) -> str`.
- Google Gemini via `google-genai`, model from `LLM_MODEL` (`gemini-2.5-flash`, free tier):
  ```python
  from google import genai
  from google.genai import types

  client = genai.Client(api_key=settings.gemini_api_key)
  resp = client.models.generate_content(
      model=settings.llm_model,
      contents=user,
      config=types.GenerateContentConfig(system_instruction=system, temperature=0.2, max_output_tokens=500),
  )
  return resp.text
  ```
- Set `thinking_config=types.ThinkingConfig(thinking_budget=0)`: Gemini 2.5 thinking tokens count toward `max_output_tokens`, which cut answers off mid-sentence.
- Retry on HTTP 429 with exponential backoff; the free tier has low per-minute and per-day limits.
- Use `google-genai`, not the older deprecated `google-generativeai` package.
- Swapping provider later must not touch `answer.py`.

## CLI
```
rag ask "do you have waterproof running shoes under 100?"
rag ask "..." --show-context     # print exactly what the LLM received
```

## Acceptance
- [ ] Out-of-scope question → fallback text, `used_llm=False`.
- [ ] Every sentence with a price/policy fact carries a `[Sn]` tag.
- [ ] Prices in the answer match the DB exactly (spot check 5 questions).
- [ ] `--show-context` output alone is enough to verify the answer by hand.

## Concepts to notice
- Retrieval decides *what* the model can know; the prompt decides *how* it may use it. Most "hallucinations" in RAG are retrieval failures — check `--explain` before blaming the LLM.
- The empty-hits short-circuit is the payoff of `RERANK_MIN_SCORE`.
