"""System prompt and the context blocks the LLM sees."""

from rag.retrieve.models import Hit

STORE = "Stride Sports"

SYSTEM_PROMPT = f"""You are a shopping assistant for {STORE}.
Answer ONLY from the sources provided between <sources> tags.
- Cite every factual claim with its tag, e.g. [S2].
- Prices, stock and policies must come from the sources exactly; never estimate them.
- If the sources don't contain the answer, say so plainly and suggest what the customer could ask instead.
- When recommending products, list at most 3 with name, price and one reason each.
- Be concise."""

USER_TEMPLATE = """<sources>
{context_blocks}
</sources>

Question: {query}"""


def pages_label(meta: dict) -> str:
    start, end = meta["page_start"], meta["page_end"]
    return f"p.{start}" if start == end else f"pp.{start}-{end}"


def source_label(hit: Hit) -> str:
    """Short human label shown next to citations."""
    m = hit.metadata
    if hit.source == "pdf":
        return f"{m['filename']} {pages_label(m)}"
    return f"{m['name']} (SKU {m['sku']})"


def context_block(tag: str, hit: Hit) -> str:
    m = hit.metadata
    if hit.source == "pdf":
        section = f', section "{m["section"]}"' if m["section"] else ""
        return f"[{tag}] (policy) {m['filename']}, {pages_label(m)}{section}\n{m['content']}"
    # Products: built from DB columns, so the price/stock the LLM sees is authoritative.
    stock = {True: "yes", False: "no", None: "unknown"}[m["in_stock"]]
    price = f"{m['price']} {m['currency']}" if m["price"] is not None else "unknown"
    lines = [
        f"[{tag}] (product) SKU {m['sku']}",
        f"Product: {m['name']}",
        f"Brand: {m['brand'] or '-'} | Category: {m['category'] or '-'}",
        f"Price: {price} | In stock: {stock}",
    ]
    if m["attributes"]:
        lines.append("Attributes: " + ", ".join(f"{k}={v}" for k, v in m["attributes"].items()))
    if m["description"]:
        lines.append(f"Description: {m['description']}")
    return "\n".join(lines)


def build_user_message(query: str, hits: list[Hit]) -> str:
    blocks = [context_block(f"S{i}", hit) for i, hit in enumerate(hits, start=1)]
    return USER_TEMPLATE.format(context_blocks="\n\n".join(blocks), query=query)
