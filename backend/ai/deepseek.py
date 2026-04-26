"""DeepSeek sentiment analysis provider as fallback.

Endpoint: https://api.deepseek.com/v1
Model: deepseek-chat
"""

import json
import re
from typing import Any, Dict, List, Optional

import httpx

from backend.config import settings
from backend.ai.base import SentimentProvider, SentimentResult

MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com/v1"
TIMEOUT = 15.0


class DeepSeekProvider(SentimentProvider):
    """DeepSeek Chat provider for stock sentiment analysis (fallback)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.deepseek_api_key
    @property
    def name(self) -> str:
        return "DeepSeek-Chat"

    def analyze(self, articles: List[Dict[str, Any]], symbol: str) -> List[SentimentResult]:
        """Analyze articles using DeepSeek."""
        if not self.api_key:
            raise RuntimeError("DeepSeek API key not configured")

        prompt = self._build_prompt(symbol, articles)

        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(
                f"{BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]

        return self._parse_response(text, articles)

    def _build_prompt(self, symbol: str, articles: List[Dict[str, Any]]) -> str:
        """Build the prompt for batch sentiment analysis."""
        lines = []
        for i, art in enumerate(articles):
            desc = art.get("description") or art.get("content") or ""
            # Simple extraction: first 200 chars for long descriptions
            extracted = desc[:300] if len(desc) > 300 else desc
            lines.append(f"[{i}] {art['title']}")
            if extracted:
                lines.append(f"  > {extracted}")

        return f"""Analyze these {len(articles)} news articles for impact on stock {symbol}.
Return results as a JSON array.

{chr(10).join(lines)}

Format:
[{{"i":0,"r":"y"|"n","s":"+"|"-"|"0","e":"10-word summary","u":"up reason","d":"down reason"}}]

Rules:
- i: article index (starting from 0)
- r: "y" = directly discusses {symbol}, "n" = irrelevant or brief mention only
- s: "+" positive, "-" negative, "0" neutral
- e: what happened (10 words max, empty string if irrelevant)
- u: why this could push {symbol} UP (empty if irrelevant or no up reasons)
- d: why this could push {symbol} DOWN (empty if irrelevant or no down reasons)

Return JSON array only, no other text."""

    def _parse_response(self, text: str, articles: List[Dict[str, Any]]) -> List[SentimentResult]:
        """Parse JSON response with robust extraction (matches MiniMax provider)."""
        text = text.strip()
        # Remove markdown code fences
        text = re.sub(r"```(?:json)?", "", text)
        text = text.strip()

        # Find JSON array bounds
        start = text.find("[")
        end = text.rfind("]") + 1
        if start < 0 or end <= start:
            # Try object format as fallback
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0:
                raise ValueError(f"Cannot find JSON in response: {text[:200]}")

        json_str = text[start:end] if end > start else text[start:]

        try:
            items = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse error: {e}, text: {text[:500]}") from e

        if isinstance(items, dict):
            items = [items]

        # Map index -> result
        results = []
        idx_map = {item["i"]: item for item in items if "i" in item}

        for i in range(len(articles)):
            item = idx_map.get(i, {})
            r_val = item.get("r", "n")
            is_relevant = r_val in ("y", "relevant", True)
            s_raw = item.get("s", "0")
            sentiment_map = {"+": "positive", "-": "negative", "0": "neutral"}
            sentiment = sentiment_map.get(s_raw, "neutral")

            results.append(SentimentResult(
                index=i,
                is_relevant=is_relevant,
                sentiment=sentiment,
                key_discussion=str(item.get("e", ""))[:200],
                reason_growth=str(item.get("u", ""))[:300],
                reason_decrease=str(item.get("d", ""))[:300],
            ))

        return results
