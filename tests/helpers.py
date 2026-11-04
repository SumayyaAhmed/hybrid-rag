"""Small builders shared by the tests."""

from decimal import Decimal

from rag.retrieve.models import Hit


def pdf_hit(id_: int = 1, *, page_start: int = 1, page_end: int = 1, section: str | None = "Return Window",
            content: str = "You can return items within 30 days.", score: float | None = None) -> Hit:
    return Hit(
        key=f"pdf:{id_}", source="pdf", text=f"{section or ''}\n{content}".strip(), rerank_score=score,
        metadata={"filename": "returns_policy.pdf", "page_start": page_start, "page_end": page_end,
                  "section": section, "content": content},
    )


def product_hit(id_: int = 1, *, sku: str = "00123", name: str = "Trailblaze Running Shoe", price: Decimal | None = Decimal("89.99"),
                in_stock: bool | None = True, score: float | None = None) -> Hit:
    return Hit(
        key=f"prod:{id_}", source="product", text=f"Product: {name}\nSKU: {sku}", rerank_score=score,
        metadata={"sku": sku, "name": name, "brand": "Stride", "category": "Footwear > Running", "price": price,
                  "currency": "USD", "in_stock": in_stock, "attributes": {"color": "blue"}, "description": "Light shoe."},
    )
