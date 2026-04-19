"""Abstract base class for AI sentiment analysis providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class SentimentResult:
    """Represents the result of a single article's sentiment analysis."""

    def __init__(
        self,
        index: int,
        is_relevant: bool,
        sentiment: str,  # "positive", "negative", "neutral"
        key_discussion: str = "",
        reason_growth: str = "",
        reason_decrease: str = "",
    ):
        self.index = index
        self.is_relevant = is_relevant
        self.sentiment = sentiment
        self.key_discussion = key_discussion
        self.reason_growth = reason_growth
        self.reason_decrease = reason_decrease

    def to_dict(self) -> Dict[str, Any]:
        return {
            "i": self.index,
            "r": "y" if self.is_relevant else "n",
            "s": self._sentiment_code(),
            "e": self.key_discussion,
            "u": self.reason_growth,
            "d": self.reason_decrease,
        }

    def _sentiment_code(self) -> str:
        return {"positive": "+", "negative": "-", "neutral": "0"}.get(self.sentiment, "0")


class SentimentProvider(ABC):
    """Abstract base class for AI sentiment analysis providers.

    Subclasses implement the actual API calls to different LLM providers.
    """

    @abstractmethod
    def analyze(self, articles: List[Dict[str, Any]], symbol: str) -> List[SentimentResult]:
        """Analyze a batch of articles for a given stock symbol.

        Args:
            articles: List of article dicts, each must have:
                - "title" (str)
                - "description" or "content" (str, optional)
                - "id" (str)
            symbol: Stock ticker/symbol being analyzed.

        Returns:
            List of SentimentResult, one per article (in same order).
            Providers that fail to analyze an article should either:
            - Return a result with is_relevant=False, or
            - Raise an exception (for the caller to handle retry/fallback)
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging/debugging."""
        ...
