"""Tests for AI provider: both providers fail -> returns null/empty results."""

import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.ai.provider import UnifiedSentimentProvider
from backend.ai.base import SentimentResult


class TestAIBothFail:
    """Test UnifiedSentimentProvider: both MiniMax and DeepSeek fail."""

    def test_both_providers_fail_returns_neutral_results(self):
        """When both providers fail, returns neutral/irrelevant results for all articles."""
        articles = [
            {"id": "1", "title": "茅台营收", "description": "贵州茅台一季度营收"},
            {"id": "2", "title": "市场下跌", "description": "今日沪深两市下跌"},
            {"id": "3", "title": "政策发布", "description": "央行发布新政策"},
        ]

        with patch("backend.ai.provider.MiniMaxProvider") as mock_minimax_cls:
            mock_minimax = mock_minimax_cls.return_value
            mock_minimax.analyze.side_effect = RuntimeError("MiniMax API error")

            with patch("backend.ai.provider.DeepSeekProvider") as mock_deepseek_cls:
                mock_deepseek = mock_deepseek_cls.return_value
                mock_deepseek.analyze.side_effect = RuntimeError("DeepSeek API error")

                provider = UnifiedSentimentProvider()
                results = provider.analyze(articles, "600519")

        # Should return one result per article (all marked irrelevant)
        assert len(results) == 3
        for r in results:
            assert r.is_relevant is False
            assert r.sentiment == "neutral"
            assert r.index in (0, 1, 2)

    def test_both_providers_fail_each_gets_called(self):
        """Both MiniMax and DeepSeek are attempted before returning fallback."""
        articles = [{"id": "1", "title": "test", "description": "desc"}]

        with patch("backend.ai.provider.MiniMaxProvider") as mock_minimax_cls:
            mock_minimax = mock_minimax_cls.return_value
            mock_minimax.analyze.side_effect = RuntimeError("MiniMax down")

            with patch("backend.ai.provider.DeepSeekProvider") as mock_deepseek_cls:
                mock_deepseek = mock_deepseek_cls.return_value
                mock_deepseek.analyze.side_effect = RuntimeError("DeepSeek down")

                provider = UnifiedSentimentProvider()
                provider.analyze(articles, "000001")

        assert mock_minimax.analyze.called
        assert mock_deepseek.analyze.called

    def test_both_fail_single_article(self):
        """Both providers fail for single article returns one neutral result."""
        articles = [{"id": "1", "title": "Single test", "description": "Single description"}]

        with patch("backend.ai.provider.MiniMaxProvider") as mock_minimax_cls:
            mock_minimax = mock_minimax_cls.return_value
            mock_minimax.analyze.side_effect = ConnectionError("connection failed")

            with patch("backend.ai.provider.DeepSeekProvider") as mock_deepseek_cls:
                mock_deepseek = mock_deepseek_cls.return_value
                mock_deepseek.analyze.side_effect = ConnectionError("connection failed")

                provider = UnifiedSentimentProvider()
                results = provider.analyze(articles, "600519")

        assert len(results) == 1
        assert results[0].is_relevant is False
        assert results[0].sentiment == "neutral"
        assert results[0].index == 0
        assert results[0].key_discussion == ""
        assert results[0].reason_growth == ""
        assert results[0].reason_decrease == ""

    def test_both_fail_many_articles(self):
        """Both providers fail for 50 articles returns 50 neutral results."""
        articles = [{"id": str(i), "title": f"Title {i}", "description": f"Desc {i}"} for i in range(50)]

        with patch("backend.ai.provider.MiniMaxProvider") as mock_minimax_cls:
            mock_minimax = mock_minimax_cls.return_value
            mock_minimax.analyze.side_effect = RuntimeError("down")

            with patch("backend.ai.provider.DeepSeekProvider") as mock_deepseek_cls:
                mock_deepseek = mock_deepseek_cls.return_value
                mock_deepseek.analyze.side_effect = RuntimeError("down")

                provider = UnifiedSentimentProvider()
                results = provider.analyze(articles, "000001")

        assert len(results) == 50
        indices = {r.index for r in results}
        assert indices == set(range(50))
        for r in results:
            assert r.is_relevant is False
            assert r.sentiment == "neutral"

    def test_both_fail_different_error_types(self):
        """Both providers fail with different exception types."""
        articles = [{"id": "1", "title": "test", "description": "desc"}]

        with patch("backend.ai.provider.MiniMaxProvider") as mock_minimax_cls:
            mock_minimax = mock_minimax_cls.return_value
            mock_minimax.analyze.side_effect = ConnectionResetError("reset")

            with patch("backend.ai.provider.DeepSeekProvider") as mock_deepseek_cls:
                mock_deepseek = mock_deepseek_cls.return_value
                mock_deepseek.analyze.side_effect = TimeoutError("timeout")

                provider = UnifiedSentimentProvider()
                results = provider.analyze(articles, "600519")

        assert len(results) == 1
        assert results[0].is_relevant is False
        assert results[0].sentiment == "neutral"
