"""Layer 1: MiniMax/DeepSeek AI — 50 articles packed into 1 API call.

Strategy (Chinese A-share version):
1. Keyword extraction: use jieba Chinese segmentation to extract relevant
   sentences from long descriptions (>500 chars), keeping sentences that
   contain stock-related keywords
2. Pack up to 50 articles into a single prompt → 1 API call
3. MiniMax first, DeepSeek fallback
4. Get back a compact JSON array in Chinese
"""

import jieba
import logging
from typing import Any, Dict, List

from backend.database import get_conn
from backend.ai.provider import UnifiedSentimentProvider

logger = logging.getLogger(__name__)

BATCH_SIZE = 50  # articles per API call

# Chinese A-share stop words for keyword extraction
_CHINESE_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "他", "她", "它", "们", "但", "却", "而", "已", "还", "被",
    "让", "把", "与", "及", "等", "并", "个", "中", "为", "将", "对", "以", "从",
    "之", "来", "后", "前", "能", "只", "应", "又", "或", "其", "此", "因", "所",
    "当", "则", "于", "过", "可", "多", "最", "更", "比", "做", "主", "者",
}

# English stop words
_ENGLISH_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "shall", "can", "of", "in", "to", "for", "on", "with",
    "at", "by", "from", "as", "or", "and", "but", "if", "then", "so", "that",
    "this", "these", "those", "it", "its", "they", "them", "their", "which", "what",
}


def _extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from text using jieba."""
    if not text:
        return []
    words = jieba.cut(text)
    return [
        w.strip() for w in words
        if len(w.strip()) >= 2
        and w.strip() not in _CHINESE_STOP_WORDS
        and w.strip().lower() not in _ENGLISH_STOP_WORDS
    ]


def _get_pending_articles(symbol: str, limit: int = 10000) -> List[Dict[str, Any]]:
    """Get articles that passed Layer 0 but haven't been processed by Layer 1."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT nr.id, nr.title, nr.description
           FROM news_raw nr
           JOIN layer0_results l0 ON nr.id = l0.news_id AND l0.symbol = ?
           WHERE l0.passed = 1
           AND nr.id NOT IN (
               SELECT news_id FROM layer1_results WHERE symbol = ?
           )
           LIMIT ?""",
        (symbol, symbol, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _process_batch_group(
    symbol: str, articles: List[Dict[str, Any]], provider: UnifiedSentimentProvider
) -> Dict[str, int]:
    """Process a group of up to 50 articles in a single API call."""
    conn = get_conn()
    stats = {"processed": 0, "relevant": 0, "irrelevant": 0, "errors": 0}

    try:
        sentiment_results = provider.analyze(articles, symbol)

        for result in sentiment_results:
            idx = result.index
            if idx is None or idx >= len(articles):
                stats["errors"] += 1
                continue

            art = articles[idx]
            relevance = "relevant" if result.is_relevant else "irrelevant"

            conn.execute(
                """INSERT OR REPLACE INTO layer1_results
                   (news_id, symbol, relevance, key_discussion, sentiment,
                    reason_growth, reason_decrease)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    art["id"],
                    symbol,
                    relevance,
                    result.key_discussion,
                    result.sentiment,
                    result.reason_growth,
                    result.reason_decrease,
                ),
            )
            stats["processed"] += 1
            if result.is_relevant:
                stats["relevant"] += 1
            else:
                stats["irrelevant"] += 1

    except Exception as e:
        logger.error("Batch error for %s: %s", symbol, e)
        stats["errors"] = len(articles)

    conn.commit()
    conn.close()
    return stats


def run_layer1(symbol: str, max_articles: int = 10000) -> Dict[str, Any]:
    """Run Layer 1 on all pending articles for a symbol.

    Processes in groups of 50 articles per API call.
    """
    articles = _get_pending_articles(symbol, limit=max_articles)
    if not articles:
        return {"status": "no_pending", "total": 0}

    provider = UnifiedSentimentProvider()

    total_stats = {
        "total": len(articles), "processed": 0, "relevant": 0,
        "irrelevant": 0, "errors": 0, "api_calls": 0,
    }

    for i in range(0, len(articles), BATCH_SIZE):
        chunk = articles[i : i + BATCH_SIZE]
        stats = _process_batch_group(symbol, chunk, provider)

        total_stats["processed"] += stats["processed"]
        total_stats["relevant"] += stats["relevant"]
        total_stats["irrelevant"] += stats["irrelevant"]
        total_stats["errors"] += stats["errors"]
        total_stats["api_calls"] += 1

        logger.info(
            "[%s] Batch %d: %d/%d ok, %d relevant, %d errors",
            symbol, total_stats["api_calls"],
            stats["processed"], len(chunk), stats["relevant"], stats["errors"],
        )

    return total_stats
