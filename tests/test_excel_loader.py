from decimal import Decimal

import pandas as pd

from rag.ingest.excel_loader import load_catalogue, render_search_text


def write_sheet(tmp_path, rows):
    path = tmp_path / "catalogue.xlsx"
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def row(**overrides):
    base = {"SKU": "00123", "Product Name": "Trailblaze", "Brand": "Stride", "Category": "Footwear",
            "Price": "89.99", "Stock": "Yes", "Description": "Light shoe", "Color": "blue"}
    return base | overrides


def test_leading_zeros_kept(tmp_path):
    products, errors = load_catalogue(write_sheet(tmp_path, [row(SKU="00123")]))
    assert products[0].sku == "00123" and errors == []


def test_stock_values(tmp_path):
    rows = [row(SKU="1", Stock="Yes"), row(SKU="2", Stock="no"), row(SKU="3", Stock="0"), row(SKU="4", Stock="")]
    products, _ = load_catalogue(write_sheet(tmp_path, rows))
    assert [p.in_stock for p in products] == [True, False, False, None]


def test_empty_price_is_none(tmp_path):
    products, errors = load_catalogue(write_sheet(tmp_path, [row(Price="")]))
    assert products[0].price is None and errors == []


def test_bad_rows_are_skipped_with_reason(tmp_path):
    rows = [row(SKU="1"), row(SKU="2", **{"Product Name": ""}), row(SKU="3", Price="abc")]
    products, errors = load_catalogue(write_sheet(tmp_path, rows))
    assert [p.sku for p in products] == ["1"]
    assert errors[0].startswith("row 3: name") and errors[1].startswith("row 4: price")


def test_unmapped_columns_go_to_attributes_and_search_text(tmp_path):
    products, _ = load_catalogue(write_sheet(tmp_path, [row(Color="blue")]))
    p = products[0]
    assert p.attributes == {"color": "blue"}
    assert p.price == Decimal("89.99")
    assert "Attributes: color=blue" in render_search_text(p)
