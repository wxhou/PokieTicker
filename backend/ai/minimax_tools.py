"""MiniMax Token Plan tools: realtime news search via web search."""

import base64
import hashlib
import httpx
import io
import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from backend.config import settings
from backend.database import get_conn

logger = logging.getLogger(__name__)

BASE_URL = "https://api.minimaxi.com/v1"
TIMEOUT = 30.0
CACHE_TTL_HOURS = 6
VL_TIMEOUT = 60.0
VL_MODEL = "MiniMax-VL-01"
VL_PROMPT = """你是一个A股持仓识别助手。请从截图中提取所有股票信息。

对于每只股票，返回JSON数组：
- stock_code: A股股票代码（如600519），6位数字
- stock_name: 公司简称（如贵州茅台）
- quantity: 持仓数量（如有则填，无则填null）
- source: 来源App名称（如雪球、同花顺、支付宝等，不确定填"截图"）

只返回JSON数组，不要返回任何其他文字。
如果无法识别某只股票，跳过它。"""


def _compute_simhash(text: str) -> str:
    """Compute 64-bit SimHash of a string using MD5.

    Uses character-level tokenization, which works well for Chinese text.
    """
    vectors = [0] * 64
    words = text.lower().split()
    for word in words:
        # Take first 8 bytes (64 bits) of MD5 hash
        h = int(hashlib.md5(word.encode()).hexdigest()[:16], 16)
        for i in range(64):
            vectors[i] += 1 if (h >> i) & 1 else -1
    fingerprint = sum((1 << i) for i, v in enumerate(vectors) if v > 0)
    return format(fingerprint, "016x")


def _hamming_distance(a: str, b: str) -> int:
    """Calculate Hamming distance between two hex SimHashes."""
    ha, hb = int(a, 16), int(b, 16)
    xor = ha ^ hb
    return bin(xor).count("1")


def _parse_json_robust(text: str) -> list:
    """Parse JSON array from text, supporting nested structures.

    Handles:
    - Direct JSON array: [{"title": ...}]
    - Nested {"data": [...]} or {"results": [...]} etc.
    - Markdown code fences around JSON
    - Text with leading/trailing non-JSON content
    """
    text = re.sub(r"```(?:json)?", "", text).strip()

    # Try direct parse first
    try:
        val = json.loads(text)
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            for key in ["data", "results", "items", "news"]:
                if key in val and isinstance(val[key], list):
                    return val[key]
        return []
    except json.JSONDecodeError:
        pass

    # Fallback: find first [ ... ]
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return []


class MiniMaxTools:
    """MiniMax Token Plan tools for realtime news search."""

    def __init__(self):
        self.api_key = settings.minimax_api_key

    def search_realtime_news(self, symbol: str, days: int = 7) -> list[dict]:
        """Search realtime news for a symbol using MiniMax M2.5.

        Flow: cache check → stock name lookup → M2.5 call → dedup → store → return
        Returns list of {title, snippet, date, url, simhash}.
        """
        symbol = symbol.upper()

        # Check cache TTL
        conn = get_conn()
        cached = conn.execute(
            "SELECT last_sync FROM news_sources WHERE source = ?",
            ("minimax_search",),
        ).fetchone()
        conn.close()

        if cached and cached[0]:
            last = datetime.fromisoformat(cached[0])
            if (datetime.now() - last).total_seconds() < CACHE_TTL_HOURS * 3600:
                return []  # Cached, skip

        # Stock name lookup
        conn = get_conn()
        stock = conn.execute(
            "SELECT name FROM tickers WHERE symbol = ?",
            (symbol,),
        ).fetchone()
        conn.close()

        if not stock:
            return []

        stock_name = stock[0]

        # Call MiniMax M2.5 for news search
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(
                f"{BASE_URL}/text/chatcompletion_v2",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "MiniMax-M2.5",
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"搜索{stock_name}({symbol})近{days}天最新A股财经新闻。"
                                f"请返回JSON数组格式，只返回与{symbol}直接相关的新闻：\n"
                                f'[{{"title":"新闻标题","snippet":"100字以内摘要","date":"YYYY-MM-DD","url":"文章链接"}}]\n'
                                f"如果没有找到相关新闻，返回空数组 []。"
                            ),
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2048,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]

        results = self._parse_search_response(text, symbol)

        # Filter by SimHash deduplication
        filtered = self._deduplicate_by_simhash(results, symbol)

        # Store deduplicated results to DB
        if filtered:
            _store_news_to_db(filtered)
            # Update last sync timestamp
            conn = get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO news_sources (source, last_sync) VALUES (?, datetime('now'))",
                ("minimax_search",),
            )
            conn.commit()
            conn.close()

        return filtered

    def _parse_search_response(self, text: str, symbol: str) -> list[dict]:
        """Parse JSON search results using robust parser."""
        items = _parse_json_robust(text)
        if not items:
            logger.warning("Failed to parse search response for %s: %s", symbol, text[:200])
        return [
            {
                "title": it.get("title", ""),
                "snippet": it.get("snippet", ""),
                "date": it.get("date", ""),
                "url": it.get("url", ""),
                "simhash": _compute_simhash(it.get("title", "")),
                "symbol": symbol,
            }
            for it in items
            if it.get("title") and it.get("snippet")
        ]

    def _deduplicate_by_simhash(self, new_items: list[dict], symbol: str) -> list[dict]:
        """Filter out items with SimHash too similar to existing news (Hamming <= 3)."""
        conn = get_conn()
        existing = conn.execute(
            "SELECT news_id, simhash FROM news_raw WHERE symbol = ? AND simhash IS NOT NULL",
            (symbol,),
        ).fetchall()
        conn.close()

        if not existing:
            return new_items

        existing_hashes = {(r["news_id"], r["simhash"]) for r in existing if r["simhash"]}
        THRESHOLD = 3
        result = []
        for item in new_items:
            sh = item["simhash"]
            is_dup = any(
                existing_sh and _hamming_distance(sh, existing_sh) <= THRESHOLD
                for _, existing_sh in existing_hashes
            )
            if not is_dup:
                result.append(item)
        return result

    def parse_screenshot(self, image_bytes: bytes) -> list[dict]:
        """Parse stock holdings from a screenshot using MiniMax VL model.

        Args:
            image_bytes: Raw image bytes (jpg/png/webp)

        Returns:
            List of dicts with keys: stock_code, stock_name, quantity, source, confidence, in_database
        """
        # Encode image to base64
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        # Detect mime type from first bytes
        if image_bytes[:3] == b"\xff\xd8\xff":
            mime = "image/jpeg"
        elif image_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            mime = "image/jpeg"  # default

        image_url = f"data:{mime};base64,{b64}"

        # Call MiniMax VL endpoint
        with httpx.Client(timeout=VL_TIMEOUT) as client:
            resp = client.post(
                f"{BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": VL_MODEL,
                    "messages": [
                        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}]},
                        {"role": "user", "content": VL_PROMPT},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2048,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]

        # Parse VL JSON response
        holdings = self._parse_vl_response(text)

        # Check in_database for each stock
        for h in holdings:
            conn = get_conn()
            exists = conn.execute("SELECT 1 FROM tickers WHERE symbol = ?", (h["stock_code"],)).fetchone()
            conn.close()
            h["in_database"] = exists is not None

        return holdings

    def _parse_vl_response(self, text: str) -> list[dict]:
        """Parse VL JSON output into holdings list."""
        items = _parse_json_robust(text)
        return [
            {
                "stock_code": it.get("stock_code", "").strip(),
                "stock_name": it.get("stock_name", "").strip(),
                "quantity": it.get("quantity"),
                "source": it.get("source", "截图"),
                "confidence": 0.95,  # placeholder, not displayed in UI
            }
            for it in items
            if it.get("stock_code") and it.get("stock_name")
        ]


def _store_news_to_db(items: list[dict]) -> None:
    """Store search results to news_raw + news_aligned tables."""
    conn = get_conn()
    for item in items:
        news_id = f"mms_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO news_raw (id, title, description, publisher, published_utc, article_url, source, simhash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                news_id,
                item.get("title", ""),
                item.get("snippet", ""),
                "minimax_search",
                item.get("date", ""),
                item.get("url", ""),
                "minimax_search",
                item.get("simhash"),
            ),
        )
        # Insert into news_ticker so layer0/1 pipelines pick it up
        conn.execute(
            "INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)",
            (news_id, item["symbol"]),
        )
        conn.execute(
            """INSERT INTO news_aligned (news_id, symbol, trade_date, source)
               VALUES (?, ?, ?, 'minimax_search')""",
            (news_id, item["symbol"], item.get("date", "")),
        )
    conn.commit()
    conn.close()
