"""Unified AI sentiment provider with MiniMax + DeepSeek fallback."""

import logging
from typing import Any, Dict, List, Optional

from backend.ai.base import SentimentProvider, SentimentResult
from backend.ai.minimax import MiniMaxProvider
from backend.ai.deepseek import DeepSeekProvider

logger = logging.getLogger(__name__)


class UnifiedSentimentProvider:
    """Try MiniMax first, fall back to DeepSeek on failure.

    Usage:
        provider = UnifiedSentimentProvider()
        results = provider.analyze(articles, symbol)
    """

    def __init__(self):
        self.minimax = MiniMaxProvider()
        self.deepseek = DeepSeekProvider()

    def analyze(
        self, articles: List[Dict[str, Any]], symbol: str
    ) -> List[SentimentResult]:
        """Analyze articles, trying providers in order until one succeeds."""
        # Try MiniMax first
        try:
            return self.minimax.analyze(articles, symbol)
        except Exception as e:
            logger.warning("MiniMax failed: %s, trying DeepSeek fallback", e)

        # Fall back to DeepSeek
        try:
            return self.deepseek.analyze(articles, symbol)
        except Exception as e:
            logger.error("Both providers failed: MiniMax error, DeepSeek error: %s", e)
            # Return null results for all articles (mark as irrelevant)
            return [
                SentimentResult(
                    index=i,
                    is_relevant=False,
                    sentiment="neutral",
                    key_discussion="",
                    reason_growth="",
                    reason_decrease="",
                )
                for i in range(len(articles))
            ]
