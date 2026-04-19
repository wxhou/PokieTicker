"""Tests for jieba keyword extraction from layer1.py."""

import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestJiebaKeywords:
    """Test _extract_keywords: stopwords, frequency threshold, Chinese terms."""

    def test_extract_keywords_removes_chinese_stopwords(self):
        """Chinese stop words like 的、了、在、是 are filtered out."""
        from backend.pipeline.layer1 import _extract_keywords

        result = _extract_keywords("茅台的股价在上涨，这是一个好消息。")
        tokens = set(result)
        # Common stop words should be filtered
        assert "的" not in tokens
        assert "在" not in tokens
        # Content words should be kept
        assert "茅台" in tokens or "股价" in tokens or "上涨" in tokens

    def test_extract_keywords_removes_english_stopwords(self):
        """English stop words like the, is, are are filtered out."""
        from backend.pipeline.layer1 import _extract_keywords

        result = _extract_keywords("The stock price is rising and the market is strong.")
        tokens = set(t.lower() for t in result)
        # Core stop words should be removed
        assert "the" not in tokens
        assert "is" not in tokens
        assert "and" not in tokens

    def test_extract_keywords_requires_min_length_2(self):
        """Keywords must be at least 2 characters long."""
        from backend.pipeline.layer1 import _extract_keywords

        result = _extract_keywords("茅台 涨 1")
        tokens = result
        for token in tokens:
            assert len(token) >= 2

    def test_extract_keywords_includes_chinese_stock_terms(self):
        """Meaningful Chinese terms like 茅台、股价、上涨 are kept."""
        from backend.pipeline.layer1 import _extract_keywords

        result = _extract_keywords("贵州茅台股价持续上涨")
        tokens = set(result)
        # Should include meaningful content words
        assert any("茅台" in t for t in tokens) or any("股价" in t for t in tokens)

    def test_extract_keywords_empty_text(self):
        """Empty text returns empty list."""
        from backend.pipeline.layer1 import _extract_keywords

        assert _extract_keywords("") == []
        assert _extract_keywords(None) == []

    def test_extract_keywords_long_text(self):
        """Long text is processed correctly by jieba."""
        from backend.pipeline.layer1 import _extract_keywords

        long_text = (
            "贵州茅台今日发布2026年一季度财报显示营收同比增长15%，"
            "净利润增长20%，超出市场预期。分析师认为茅台高端白酒需求强劲，"
            "品牌溢价能力持续提升，建议增持评级。股价创历史新高。"
        )
        result = _extract_keywords(long_text)
        assert isinstance(result, list)
        tokens = set(result)
        assert len(tokens) > 5

    def test_extract_keywords_english_text(self):
        """English text is tokenized and core stopwords are filtered."""
        from backend.pipeline.layer1 import _extract_keywords

        result = _extract_keywords(
            "NVIDIA stock price jumped 15% after earnings beat expectations"
        )
        tokens = set(t.lower() for t in result)
        # Core stop words from _ENGLISH_STOP_WORDS in layer1.py should be removed:
        # "the", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        # "do", "does", "did", "will", "would", "could", "should", "may", "might", "must",
        # "shall", "can", "of", "in", "to", "for", "on", "with", "at", "by", "from", "as",
        # "or", "and", "but", "if", "then", "so"
        assert "the" not in tokens
        assert "of" not in tokens
        assert "is" not in tokens
        # "after" is NOT in layer1's stopwords (it's only in minimax.py's stopwords)
        assert len(result) >= 4

    def test_extract_keywords_returns_list_with_order(self):
        """_extract_keywords returns a list preserving jieba order."""
        from backend.pipeline.layer1 import _extract_keywords

        result = _extract_keywords("贵州茅台股价持续上涨")
        assert isinstance(result, list)
        assert len(result) > 0
        # All items should be strings
        assert all(isinstance(t, str) for t in result)

    def test_extract_keywords_no_english_numbers_filtered(self):
        """Numbers in English text are included if not stopwords (>=2 chars)."""
        from backend.pipeline.layer1 import _extract_keywords

        result = _extract_keywords("2026年茅台股价100元")
        # Numbers in mixed text may appear; the function filters by stopwords
        # not by isdigit(), so some numeric tokens could remain if >= 2 chars
        tokens = set(result)
        # At minimum, Chinese content words should be present
        assert len(result) >= 2
