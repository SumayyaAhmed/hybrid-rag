"""Run every question in eval/questions.jsonl through the RAG and report accuracy.

Run:  uv run python eval/run_eval.py            # full: retrieval + Gemini answers
      uv run python eval/run_eval.py --no-llm   # retrieval + refusals only (no Gemini quota used)
      uv run python eval/run_eval.py --fresh    # ignore saved results and start over
Results are saved to eval/results.json after every question, so a crashed run resumes where it stopped.

Each question has:
  expect: sources that must be in the kept hits ("file.pdf#Section" or "sku:00232"). [] = should refuse.
  facts:  strings that must appear in the answer. A list inside means "any of these".

Checks (no LLM judge, just string matching, so the numbers are easy to trust):
  retrieval  all expected sources are among the kept hits          (in-scope questions)
  answer     every fact appears in the answer text                 (in-scope questions)
  cited      the answer cites at least one expected source         (in-scope questions)
  refused    no hits kept and the LLM was not called               (out-of-scope questions)
  pass       retrieval + answer for in-scope, refused for out-of-scope
"""

import json
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from rag.generate.answer import answer_from_hits
from rag.retrieve.models import Hit
from rag.retrieve.pipeline import run

HERE = Path(__file__).parent
console = Console()


def source_id(hit: Hit) -> str:
    """Stable id that doesn't depend on database row ids."""
    if hit.source == "pdf":
        return f"{hit.metadata['filename']}#{hit.metadata['section']}"
    return f"sku:{hit.metadata['sku']}"


def has_fact(text: str, fact: str | list[str]) -> bool:
    alternatives = [fact] if isinstance(fact, str) else fact
    return any(re.search(rf"\b{re.escape(alt)}\b", text, re.IGNORECASE) for alt in alternatives)


def evaluate(item: dict, use_llm: bool) -> dict:
    trace = run(item["q"])
    kept_ids = [source_id(h) for h in trace.kept]
    row = {"q": item["q"], "expect": item["expect"], "kept": kept_ids, "answer": None}

    if not item["expect"]:
        # Out of scope: refused means nothing kept, so the LLM would never be called.
        row["refused"] = row["pass"] = not kept_ids
        return row

    row["retrieval"] = all(e in kept_ids for e in item["expect"])
    row["rank"] = min((kept_ids.index(e) + 1 for e in item["expect"] if e in kept_ids), default=None)
    row["pass"] = row["retrieval"]
    if use_llm:
        result = answer_from_hits(item["q"], trace.kept)
        cited_ids = {source_id(h) for h in trace.kept if h.key in {s.key for s in result.sources}}
        row["answer"] = result.text
        row["answer_ok"] = all(has_fact(result.text, f) for f in item["facts"])
        row["cited"] = bool(cited_ids & set(item["expect"]))
        row["pass"] = row["retrieval"] and row["answer_ok"]
    return row


def pct(rows: list[dict], key: str) -> str:
    return f"{sum(r[key] for r in rows)}/{len(rows)} = {100 * sum(r[key] for r in rows) / len(rows):.0f}%" if rows else "-"


def main() -> None:
    use_llm = "--no-llm" not in sys.argv
    results_path = HERE / "results.json"
    items = [json.loads(line) for line in (HERE / "questions.jsonl").read_text().splitlines() if line.strip()]

    # Resume: reuse saved rows done in the same mode (a --no-llm row has no answer to reuse in a full run).
    saved = {} if "--fresh" in sys.argv or not results_path.exists() else {r["q"]: r for r in json.loads(results_path.read_text())}
    rows: list[dict] = []

    def save() -> None:
        # Rows done so far + saved rows not reached yet, so a crash never throws away earlier work.
        done = {r["q"] for r in rows}
        results_path.write_text(json.dumps(rows + [r for q, r in saved.items() if q not in done], indent=2, ensure_ascii=False))

    for i, item in enumerate(items, start=1):
        old = saved.get(item["q"])
        if old and old["expect"] == item["expect"] and (not use_llm or not item["expect"] or "answer_ok" in old):
            rows.append(old)
            continue
        console.print(f"[{i}/{len(items)}] {item['q']}")
        rows.append(evaluate(item, use_llm))
        save()

    ok = lambda v: "-" if v is None else ("[green]✓[/]" if v else "[red]✗[/]")  # noqa: E731
    table = Table("#", "question", "retrieval", "rank", "answer", "cited", "pass")
    for i, r in enumerate(rows, start=1):
        if r["expect"]:
            table.add_row(str(i), r["q"][:50], ok(r["retrieval"]), str(r["rank"] or "-"), ok(r.get("answer_ok")), ok(r.get("cited")), ok(r["pass"]))
        else:
            table.add_row(str(i), r["q"][:50], "refused " + ok(r["refused"]), "", "", "", ok(r["pass"]))
    console.print(table)

    in_scope = [r for r in rows if r["expect"]]
    out_scope = [r for r in rows if not r["expect"]]
    console.print(f"Retrieval accuracy  (right sources kept):    {pct(in_scope, 'retrieval')}")
    if use_llm:
        console.print(f"Answer accuracy     (expected facts present): {pct(in_scope, 'answer_ok')}")
        console.print(f"Citation accuracy   (cites a right source):   {pct(in_scope, 'cited')}")
    console.print(f"Refusal accuracy    (off-topic refused):      {pct(out_scope, 'refused')}")
    console.print(f"[bold]Overall accuracy    (question passed):        {pct(rows, 'pass')}[/]" + ("" if use_llm else "  (retrieval only)"))

    failures = [r for r in rows if not r["pass"]]
    for r in failures:
        console.rule(f"FAILED: {r['q']}")
        console.print(f"expected: {r['expect']}\nkept:     {r['kept']}")
        if r["answer"]:
            console.print(f"answer:   {r['answer']}", markup=False)


if __name__ == "__main__":
    main()
