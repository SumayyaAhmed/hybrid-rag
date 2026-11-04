"""What the LLM sees (spec 03): tags, the question, and prices straight from the DB columns."""

from decimal import Decimal

from helpers import pdf_hit, product_hit

from rag.generate.prompts import build_user_message, context_block, source_label


def test_hits_are_tagged_in_order_and_question_included():
    message = build_user_message("what is the return window?", [pdf_hit(1), product_hit(2), pdf_hit(3)])
    assert message.index("[S1] (policy)") < message.index("[S2] (product)") < message.index("[S3] (policy)")
    assert message.rstrip().endswith("Question: what is the return window?")


def test_product_block_uses_db_price_and_stock():
    block = context_block("S1", product_hit(price=Decimal("129.99"), in_stock=False))
    assert "Price: 129.99 USD | In stock: no" in block


def test_missing_price_and_stock_shown_as_unknown():
    block = context_block("S1", product_hit(price=None, in_stock=None))
    assert "Price: unknown | In stock: unknown" in block


def test_source_labels():
    assert source_label(pdf_hit(page_start=1, page_end=1)) == "returns_policy.pdf p.1"
    assert source_label(pdf_hit(page_start=1, page_end=2)) == "returns_policy.pdf pp.1-2"
    assert source_label(product_hit(sku="00123")) == "Trailblaze Running Shoe (SKU 00123)"
