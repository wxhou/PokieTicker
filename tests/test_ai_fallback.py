"""Tests for AI provider fallback: MiniMax fail -> DeepSeek success."""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.ai.provider import UnifiedSentimentProvider
from backend.ai.base import SentimentResult


class TestAIFallback:
    """Test UnifiedSentimentProvider: MiniMax fails, DeepSeek succeeds."""

    def test_minimax_fails_deepseek_succeeds(self):
        """MiniMax raises exception, DeepSeek returns valid results."""
        articles = [
            {"id": "1", "title": "茅台营收增长", "description": "贵州茅台一季度营收同比增长15%"},
            {"id": "2", "title": "市场整体下跌", "description": "沪深股市今日整体下跌"},
        ]

        deepseek_results = [
            SentimentResult(index=0, is_relevant=True, sentiment="positive",
                           key_discussion="营收增长15%", reason_growth="业绩超预期", reason_decrease=""),
            SentimentResult(index=1, is_relevant=False, sentiment="neutral",
                           key_discussion="", reason_growth="", reason_decrease=""),
        ]

        with patch("backend.ai.provider.MiniMaxProvider") as mock_minimax_cls:
            mock_minimax = mock_minimax_cls.return_value
            mock_minimax.analyze.side_effect = RuntimeError("MiniMax API unavailable")

            with patch("backend.ai.provider.DeepSeekProvider") as mock_deepseek_cls:
                mock_deepseek = mock_deepseek_cls.return_value
                mock_deepseek.analyze.return_value = deepseek_results
                mock_deepseek.name = "DeepSeek-Chat"

                provider = UnifiedSentimentProvider()
                results = provider.analyze(articles, "600519")

        assert len(results) == 2
        assert results[0].is_relevant is True
        assert results[0].sentiment == "positive"
        assert results[0].key_discussion == "营收增长15%"
        assert results[1].is_relevant is False
        assert mock_minimax.analyze.called
        assert mock_deepseek.analyze.called

    def test_minimax_connection_error_deepseek_ok(self):
        """MiniMax connection error triggers DeepSeek fallback."""
        articles = [{"id": "1", "title": "test", "description": "desc"}]

        deepseek_results = [
            SentimentResult(index=0, is_relevant=True, sentiment="positive",
                           key_discussion="test", reason_growth="growth", reason_decrease=""),
        ]

        with patch("backend.ai.provider.MiniMaxProvider") as mock_minimax_cls:
            mock_minimax = mock_minimax_cls.return_value
            mock_minimax.analyze.side_effect = ConnectionResetError("connection reset")

            with patch("backend.ai.provider.DeepSeekProvider") as mock_deepseek_cls:
                mock_deepseek = mock_deepseek_cls.return_value
                mock_deepseek.analyze.return_value = deepseek_results

                provider = UnifiedSentimentProvider()
                results = provider.analyze(articles, "000001")

        assert len(results) == 1
        assert results[0].is_relevant is True
        assert mock_deepseek.analyze.called

    def test_fallback_receives_correct_symbol(self):
        """DeepSeek fallback receives the same symbol parameter."""
        articles = [{"id": "1", "title": "test", "description": "desc"}]

        with patch("backend.ai.provider.MiniMaxProvider") as mock_minimax_cls:
            mock_minimax = mock_minimax_cls.return_value
            mock_minimax.analyze.side_effect = RuntimeError("fail")

            with patch("backend.ai.provider.DeepSeekProvider") as mock_deepseek_cls:
                mock_deepseek = mock_deepseek_cls.return_value
                mock_deepseek.analyze.return_value = [
                    SentimentResult(index=0, is_relevant=False, sentiment="neutral"),
                ]

                provider = UnifiedSentimentProvider()
                provider.analyze(articles, "600519.SH")

        mock_deepseek.analyze.assert_called_once_with(articles, "600519.SH")

    def test_fallback_receives_correct_articles(self):
        """DeepSeek fallback receives the same articles list."""
        articles = [
            {"id": "a", "title": "Title A", "description": "Desc A"},
            {"id": "b", "title": "Title B", "description": "Desc B"},
            {"id": "c", "title": "Title C", "description": "Desc C"},
        ]

        with patch("backend.ai.provider.MiniMaxProvider") as mock_minimax_cls:
            mock_minimax = mock_minimax_cls.return_value
            mock_minimax.analyze.side_effect = RuntimeError("fail")

            with patch("backend.ai.provider.DeepSeekProvider") as mock_deepseek_cls:
                mock_deepseek = mock_deepseek_cls.return_value
                mock_deepseek.analyze.return_value = [
                    SentimentResult(index=i, is_relevant=False, sentiment="neutral")
                    for i in range(3)
                ]

                provider = UnifiedSentimentProvider()
                provider.analyze(articles, "000001")

        # Verify articles list is passed unchanged
        call_args = mock_deepseek.analyze.call_args
        assert call_args[0][0] == articles
