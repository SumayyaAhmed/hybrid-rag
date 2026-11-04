from rag.retrieve.fusion import rrf


def test_found_by_two_lists_beats_found_by_one():
    fused = rrf({"vec": ["a", "b"], "fts": ["a", "c"], "other": ["c"]})
    assert list(fused)[0] == "a"


def test_rank_one_in_two_lists_beats_rank_one_in_one_list():
    fused = rrf({"vec": ["a", "x"], "fts": ["b", "a"]})
    # a: 1/61 + 1/62, b: 1/61
    assert fused["a"] > fused["b"]


def test_ties_are_deterministic():
    fused = rrf({"vec": ["b"], "fts": ["a"]})  # same score
    assert list(fused) == ["a", "b"]


def test_score_formula():
    fused = rrf({"vec": ["a"]}, k=60)
    assert fused["a"] == 1 / 61
