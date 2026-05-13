"""Unified AI sentiment provider using MiniMax via Anthropic SDK."""

import logging
from typing import Any, Dict, List

from backend.ai.minimax import MiniMaxProvider, _get_client, _extract_text_from_response
from backend.ai.base import SentimentResult

logger = logging.getLogger(__name__)


class UnifiedSentimentProvider:
    """Single provider using MiniMax M2.5 via Anthropic SDK.

    Falls back to returning neutral/irrelevant results on failure
    (no secondary provider needed).
    """

    def __init__(self):
        self.minimax = MiniMaxProvider()

    def analyze(self, articles: List[Dict[str, Any]], symbol: str) -> List[SentimentResult]:
        """Analyze articles. Returns results or neutral fallback on failure."""
        try:
            return self.minimax.analyze(articles, symbol)
        except Exception as e:
            logger.error("MiniMax sentiment analysis failed: %s", e)
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