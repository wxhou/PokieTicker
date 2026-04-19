"""MiniMax M2.5 sentiment analysis provider.

Endpoint: https://api.minimaxi.com/v1
Model: MiniMax-M2.5
"""

import json
import re
import jieba
from typing import Any, Dict, List, Optional

import httpx

from backend.config import settings
from backend.ai.base import SentimentProvider, SentimentResult

MODEL = "MiniMax-M2.5"
BASE_URL = "https://api.minimaxi.com/v1"
TIMEOUT = 10.0


class MiniMaxProvider(SentimentProvider):
    """MiniMax M2.5 provider for Chinese/English stock sentiment analysis."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.minimax_api_key
        self.name = "MiniMax-M2.5"

    def analyze(self, articles: List[Dict[str, Any]], symbol: str) -> List[SentimentResult]:
        """Analyze articles using MiniMax M2.5."""
        if not self.api_key:
            raise RuntimeError("MiniMax API key not configured")

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
            # Extract Chinese sentences using jieba sentence boundary detection
            extracted = _extract_chinese_sentences(desc, symbol)
            lines.append(f"[{i}] {art['title']}")
            if extracted:
                lines.append(f"  > {extracted}")

        return f"""分析以下 {len(articles)} 篇新闻对股票 {symbol} 的影响。以JSON数组格式返回结果。

{chr(10).join(lines)}

格式要求：
[
  {{"i":0,"r":"y"|"n","s":"+"|"-"|"0","e":"10字摘要","u":"上涨原因","d":"下跌原因"}}
]

说明：
- i: 文章序号（从0开始）
- r: "y"=与{symbol}直接相关，"n"=无关或仅简单提及
- s: "+"=利好，"-"=利空，"0"=中性
- e: 发生了什么（10字以内摘要，无关文章填空字符串）
- u: 该消息为何可能推动{symbol}上涨（利好原因，无关则填空）
- d: 该消息为何可能推动{symbol}下跌（利空原因，无关则填空）

只返回JSON数组，不要包含任何其他文字。"""

    def _parse_response(self, text: str, articles: List[Dict[str, Any]]) -> List[SentimentResult]:
        """Parse JSON response with robust extraction."""
        # Extract JSON from potential markdown code blocks or extra text
        text = text.strip()
        # Remove markdown code fences
        text = re.sub(r"```(?:json)?", "", text)
        text = text.strip()

        # Find JSON bounds: first { or [ to last } or ]
        start = max(text.find("{"), text.find("["))
        end = text.rfind("}") if text.rfind("}") > text.rfind("]") else text.rfind("]")
        if start < 0 or end <= start:
            # Fallback: try to find any [ or ]
            start = text.find("[")
            end = text.rfind("]") + 1
            if start < 0:
                raise ValueError(f"Cannot find JSON in response: {text[:200]}")

        json_str = text[start:end + 1] if end > start else text[start:]

        try:
            items = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse error: {e}, text: {text[:500]}") from e

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


def _extract_chinese_sentences(text: str, symbol: str) -> str:
    """Extract relevant sentences from Chinese/English text using jieba.

    For Chinese text: split by 。！？ and extract sentences containing stock keywords.
    For English text: split by sentence-ending punctuation.
    """
    if not text:
        return ""

    text = text.strip()
    if len(text) < 100:
        return text

    # Use jieba for Chinese word segmentation
    words = set(jieba.cut(symbol))
    words.update({symbol})

    # Common A-share related stop words to filter out
    stop_words = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "自己", "这", "那", "他", "她", "它", "们", "但", "却", "而", "已", "还",
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "may", "might", "must", "shall", "can", "of", "in", "to", "for", "on", "with",
        "at", "by", "from", "as", "or", "and", "but", "if", "then", "so",
    }

    # Detect if text is primarily Chinese
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    is_chinese = chinese_chars / max(len(text), 1) > 0.3

    if is_chinese:
        # Split by Chinese sentence boundaries
        import re
        sentences = re.split(r"(?<=[。！？])", text)
        relevant = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            # Check if sentence contains any keyword
            sent_words = set(jieba.cut(sent))
            keywords_found = sent_words - stop_words - words
            # Keep sentences with enough content words
            if len(keywords_found) >= 2:
                relevant.append(sent)
        if relevant:
            return " ".join(relevant[:5])  # Max 5 sentences
        # Fallback: return first 2 sentences
        return " ".join(sentences[:2]).strip() if sentences else text[:300]
    else:
        # English: split by sentence-ending punctuation
        sentences = re.split(r"(?<=[.!?])\s+", text)
        relevant = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            lower = sent.lower()
            # Check for keyword match (case-insensitive)
            symbol_lower = symbol.lower()
            if (symbol_lower in lower or
                any(kw.lower() in lower for kw in words if len(kw) > 3)):
                relevant.append(sent)
        if relevant:
            return " ".join(relevant[:3])
        return " ".join(sentences[:2]).strip() if sentences else text[:300]
