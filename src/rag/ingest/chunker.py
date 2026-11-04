"""Pages -> token-sized chunks.

1. Split the document into sections at headings (the heading becomes section_title).
2. Inside a section, pack whole paragraphs into chunks of at most `max_tokens`.
3. A paragraph that is too big on its own is split into sentences, then words.
4. Each new chunk in the same section starts with the last ~`overlap` tokens of the previous one.

`count_tokens` is passed in, so tests can use a fake counter and the real code uses Voyage's tokenizer.
"""

import re
from collections.abc import Callable

from pydantic import BaseModel

from rag.ingest.pdf_loader import Page

CountTokens = Callable[[str], int]


class Chunk(BaseModel):
    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None
    content: str
    token_count: int


def is_heading(paragraph: str) -> bool:
    # Heuristic: short, starts with a capital or digit ("30-Day ..."), no sentence-ending punctuation.
    return len(paragraph) <= 70 and len(paragraph.split()) <= 10 and not paragraph[0].islower() and paragraph[-1] not in ".!?:,;"


def split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s]


def split_to_fit(text: str, count_tokens: CountTokens, max_tokens: int) -> list[str]:
    """Split an oversized paragraph: sentences first, words only if a single sentence is still too big."""
    if count_tokens(text) <= max_tokens:
        return [text]
    parts = split_sentences(text)
    if len(parts) == 1:
        parts = text.split(" ")
        if len(parts) == 1:
            return [text]  # one giant "word": nothing more we can do
    pieces, current = [], ""
    for part in parts:
        candidate = f"{current} {part}".strip()
        if current and count_tokens(candidate) > max_tokens:
            pieces.append(current)
            current = part
        else:
            current = candidate
    if current:
        pieces.append(current)
    # A single sentence may still be too big -> recurse (it will be split on words).
    return [p for piece in pieces for p in (split_to_fit(piece, count_tokens, max_tokens) if piece != text else [piece])]


def _overlap_tail(text: str, count_tokens: CountTokens, overlap: int) -> str:
    """The last few sentences of `text` that fit in `overlap` tokens."""
    tail = ""
    for sentence in reversed(split_sentences(text)):
        candidate = f"{sentence} {tail}".strip()
        if count_tokens(candidate) > overlap:
            break
        tail = candidate
    return tail


def chunk_pages(pages: list[Page], count_tokens: CountTokens, max_tokens: int = 350, overlap: int = 50) -> list[Chunk]:
    # 1. sections: list of (title, [(page_number, paragraph), ...])
    sections: list[tuple[str | None, list[tuple[int, str]]]] = [(None, [])]
    for page in pages:
        for paragraph in page.text.split("\n\n"):
            if is_heading(paragraph):
                sections.append((paragraph, []))
            else:
                sections[-1][1].append((page.number, paragraph))

    chunks: list[Chunk] = []

    def emit(title: str | None, parts: list[tuple[int, str]]) -> None:
        content = "\n\n".join(text for _, text in parts)
        chunks.append(Chunk(
            chunk_index=len(chunks),
            page_start=min(p for p, _ in parts),
            page_end=max(p for p, _ in parts),
            section_title=title,
            content=content,
            token_count=count_tokens(content),
        ))

    for title, paragraphs in sections:
        # 2./3. every piece now fits on its own
        pieces = [(page, piece) for page, para in paragraphs for piece in split_to_fit(para, count_tokens, max_tokens)]
        current: list[tuple[int, str]] = []
        for page, piece in pieces:
            candidate = current + [(page, piece)]
            if current and count_tokens("\n\n".join(t for _, t in candidate)) > max_tokens:
                emit(title, current)
                # 4. overlap: carry the tail of the previous chunk, unless that makes it too big
                last_page, last_text = current[-1]
                tail = _overlap_tail(last_text, count_tokens, overlap)
                current = [(last_page, tail), (page, piece)] if tail else [(page, piece)]
                if count_tokens("\n\n".join(t for _, t in current)) > max_tokens:
                    current = [(page, piece)]
            else:
                current = candidate
        if current:
            emit(title, current)
    return chunks
