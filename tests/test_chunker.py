from rag.ingest.chunker import chunk_pages, is_heading
from rag.ingest.pdf_loader import Page


def words(text: str) -> int:
    """Fake tokenizer: 1 word = 1 token. Keeps tests fast and offline."""
    return len(text.split())


def sentence(n: int, word: str = "word") -> str:
    return " ".join([word] * (n - 1)) + " end."


def test_heading_heuristic():
    assert is_heading("Return Window")
    assert is_heading("30-Day Test Run Guarantee for Running Shoes")
    assert not is_heading("You can return most items within 30 days.")


def test_section_titles_and_pages():
    pages = [
        Page(1, "Return Window\n\nYou can return items within 30 days."),
        Page(2, "Refund Timing\n\nRefunds arrive in 5 to 7 business days."),
    ]
    chunks = chunk_pages(pages, words, max_tokens=50, overlap=10)
    assert [c.section_title for c in chunks] == ["Return Window", "Refund Timing"]
    assert [(c.page_start, c.page_end) for c in chunks] == [(1, 1), (2, 2)]


def test_respects_max_tokens():
    paragraph = " ".join(sentence(10) for _ in range(30))  # 300 tokens in one paragraph
    chunks = chunk_pages([Page(1, f"Heading\n\n{paragraph}")], words, max_tokens=50, overlap=10)
    assert len(chunks) > 1
    assert all(c.token_count <= 50 for c in chunks)


def test_overlap_repeats_last_sentence():
    paras = [sentence(10, f"p{i}") for i in range(6)]  # 6 paragraphs x 10 tokens
    chunks = chunk_pages([Page(1, "Heading\n\n" + "\n\n".join(paras))], words, max_tokens=30, overlap=10)
    for prev, nxt in zip(chunks, chunks[1:]):
        last_sentence = prev.content.split("\n\n")[-1]
        assert nxt.content.startswith(last_sentence)


def test_chunk_spanning_pages():
    pages = [Page(1, "Heading\n\nFirst part on page one."), Page(2, "Second part on page two.")]
    [chunk] = chunk_pages(pages, words, max_tokens=50, overlap=10)
    assert (chunk.page_start, chunk.page_end) == (1, 2)
