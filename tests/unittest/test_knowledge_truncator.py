"""Unit tests for KnowledgeTruncator (token_utils)."""

import pytest

from oxygent.utils.token_utils import KnowledgeTruncator, TokenEstimator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def approx_tokens(text: str) -> int:
    return TokenEstimator.count_tokens(text, "default")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patched_config(monkeypatch):
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_agent_llm_model",
        lambda: "mock_llm",
    )
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_agent_prompt",
        lambda: "",
    )
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_vearch_config",
        lambda: {},
    )


# ---------------------------------------------------------------------------
# KnowledgeTruncator.fits
# ---------------------------------------------------------------------------

class TestFits:
    def test_empty_text_always_fits(self):
        assert KnowledgeTruncator.fits("", 10) is True

    def test_short_text_fits(self):
        assert KnowledgeTruncator.fits("hello", 100) is True

    def test_text_exactly_at_budget(self):
        text = "a" * 4  # ~1 token with char-based estimator
        assert KnowledgeTruncator.fits(text, 1) is True

    def test_text_over_budget(self):
        text = "word " * 100  # ~100 tokens
        assert KnowledgeTruncator.fits(text, 10) is False


# ---------------------------------------------------------------------------
# KnowledgeTruncator.truncate
# ---------------------------------------------------------------------------

class TestTruncate:
    def test_no_truncation_when_fits(self):
        text = "short text"
        result, truncated = KnowledgeTruncator.truncate(text, 1000)
        assert result == text
        assert truncated is False

    def test_truncation_when_over_budget(self):
        text = "word " * 200
        result, truncated = KnowledgeTruncator.truncate(text, 50)
        assert truncated is True
        assert approx_tokens(result) <= 50

    def test_truncated_result_is_non_empty(self):
        text = "word " * 500
        result, _ = KnowledgeTruncator.truncate(text, 20)
        assert len(result) > 0

    def test_empty_text_unchanged(self):
        result, truncated = KnowledgeTruncator.truncate("", 100)
        assert result == ""
        assert truncated is False

    def test_snaps_to_paragraph_boundary(self):
        para1 = "First paragraph. " * 20
        para2 = "Second paragraph. " * 20
        text = para1 + "\n\n" + para2
        result, truncated = KnowledgeTruncator.truncate(text, 60)
        assert truncated is True
        assert result.strip() != ""

    def test_result_fits_budget_strictly(self):
        text = "token " * 300
        result, _ = KnowledgeTruncator.truncate(text, 80)
        assert approx_tokens(result) <= 80


# ---------------------------------------------------------------------------
# KnowledgeTruncator.split_to_chunks
# ---------------------------------------------------------------------------

class TestSplitToChunks:
    def test_empty_text_returns_empty_list(self):
        assert KnowledgeTruncator.split_to_chunks("", 100) == []

    def test_short_text_is_single_chunk(self):
        text = "hello world"
        chunks = KnowledgeTruncator.split_to_chunks(text, 100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_multiple_chunks_each_within_budget(self):
        text = "\n\n".join(["paragraph " * 20] * 10)
        chunks = KnowledgeTruncator.split_to_chunks(text, 40)
        assert len(chunks) > 1
        for chunk in chunks:
            assert approx_tokens(chunk) <= 40

    def test_chunks_preserve_all_content(self):
        words = ["alpha", "beta", "gamma", "delta", "epsilon"]
        text = "\n\n".join(words)
        chunks = KnowledgeTruncator.split_to_chunks(text, 5)
        joined = " ".join(chunks)
        for w in words:
            assert w in joined

    def test_invalid_chunk_size_raises(self):
        with pytest.raises(ValueError):
            KnowledgeTruncator.split_to_chunks("text", 0)

    def test_oversized_single_paragraph_is_hard_cut(self):
        text = "x " * 400
        chunks = KnowledgeTruncator.split_to_chunks(text, 50)
        assert len(chunks) > 1
        for chunk in chunks:
            assert approx_tokens(chunk) <= 50

    def test_whitespace_only_paragraphs_skipped(self):
        text = "para one\n\n   \n\npara two"
        chunks = KnowledgeTruncator.split_to_chunks(text, 100)
        assert all(c.strip() for c in chunks)
