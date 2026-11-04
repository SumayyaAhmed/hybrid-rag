"""Excel catalogue -> validated Product rows (1 row = 1 product)."""

import hashlib
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ValidationError, field_validator

# Sheet header -> Product field. Every other column goes into `attributes`.
COLUMN_MAP = {
    "SKU": "sku",
    "Product Name": "name",
    "Brand": "brand",
    "Category": "category",
    "Price": "price",
    "Stock": "in_stock",
    "Description": "description",
}

TRUE_VALUES = {"yes", "y", "true", "1", "in stock"}
FALSE_VALUES = {"no", "n", "false", "0", "out of stock"}


class Product(BaseModel):
    sku: str
    name: str
    brand: str | None = None
    category: str | None = None
    price: Decimal | None = None
    currency: str = "USD"
    in_stock: bool | None = None
    attributes: dict[str, str] = {}
    description: str | None = None

    @field_validator("sku", "name")
    @classmethod
    def required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("is empty")
        return v.strip()

    @field_validator("brand", "category", "description", mode="before")
    @classmethod
    def empty_to_none(cls, v):
        return v.strip() or None if isinstance(v, str) else v

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, v):
        if v is None or str(v).strip() == "":
            return None
        try:
            return Decimal(str(v).replace("$", "").replace(",", "").strip())
        except InvalidOperation:
            raise ValueError(f"not a number: {v!r}")

    @field_validator("in_stock", mode="before")
    @classmethod
    def parse_stock(cls, v):
        s = str(v or "").strip().lower()
        if s == "":
            return None
        if s in TRUE_VALUES:
            return True
        if s in FALSE_VALUES:
            return False
        raise ValueError(f"unknown stock value: {v!r}")


def render_search_text(p: Product) -> str:
    """The text the embedder and the reranker 'see' for this product."""
    stock = {True: "yes", False: "no", None: "unknown"}[p.in_stock]
    price = f"{p.price} {p.currency}" if p.price is not None else "unknown"
    lines = [
        f"Product: {p.name}",
        f"SKU: {p.sku}",  # without this the reranker can't match "SKU 00232" queries
        f"Brand: {p.brand or '-'} | Category: {p.category or '-'}",
        f"Price: {price} | In stock: {stock}",
    ]
    if p.attributes:
        lines.append("Attributes: " + ", ".join(f"{k}={v}" for k, v in p.attributes.items()))
    if p.description:
        lines.append(f"Description: {p.description}")
    return "\n".join(lines)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def load_catalogue(path: Path) -> tuple[list[Product], list[str]]:
    """Returns (valid products, error messages for skipped rows)."""
    df = pd.read_excel(path, sheet_name=0, dtype=str).fillna("")  # strings only: "00123" keeps its zeros
    products, errors = [], []
    for i, row in df.iterrows():
        row_number = i + 2  # +1 for 0-based index, +1 for the header row = the row number you see in Excel
        fields = {COLUMN_MAP[col]: val for col, val in row.items() if col in COLUMN_MAP}
        fields["attributes"] = {col.lower(): val.strip() for col, val in row.items() if col not in COLUMN_MAP and val.strip()}
        try:
            products.append(Product(**fields))
        except ValidationError as e:
            reasons = "; ".join(f"{err['loc'][0]}: {err['msg']}" for err in e.errors())
            errors.append(f"row {row_number}: {reasons}")
    return products, errors
