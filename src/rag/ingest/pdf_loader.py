"""PDF -> list of Page(number, text). Paragraphs inside `text` are separated by blank lines."""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass
class Page:
    number: int  # 1-based
    text: str


def _clean_block(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)    # ligatures like "ﬀ" -> "ff"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # de-hyphenate "exam-\nple" -> "example"
    return re.sub(r"\s+", " ", text).strip()      # collapse whitespace, line breaks inside a paragraph


def _repeat_key(block: str) -> str:
    # "Page 1 of 2" and "Page 2 of 2" should count as the same line.
    return re.sub(r"\d+", "#", block)


def _merge_broken_paragraphs(blocks: list[str]) -> list[str]:
    # PyMuPDF sometimes splits one paragraph into two blocks; a block starting lowercase continues the previous one.
    merged: list[str] = []
    for block in blocks:
        if merged and block[0].islower():
            merged[-1] += " " + block
        else:
            merged.append(block)
    return merged


def load_pdf(path: Path) -> list[Page]:
    doc = pymupdf.open(path)
    # Each PyMuPDF text block is roughly one paragraph or heading.
    pages_blocks = [[_clean_block(b[4]) for b in page.get_text("blocks") if b[6] == 0] for page in doc]
    pages_blocks = [_merge_broken_paragraphs([b for b in blocks if b]) for blocks in pages_blocks]

    # Headers/footers: a line that appears on more than half of the pages. Needs >= 2 pages to be meaningful.
    repeated = set()
    if len(pages_blocks) >= 2:
        counts = Counter(key for blocks in pages_blocks for key in {_repeat_key(b) for b in blocks})
        repeated = {key for key, n in counts.items() if n > len(pages_blocks) / 2}

    return [
        Page(number=i, text="\n\n".join(b for b in blocks if _repeat_key(b) not in repeated))
        for i, blocks in enumerate(pages_blocks, start=1)
    ]
