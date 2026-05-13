"""Layer 0: Rule-based filter (free, instant).

Filters out clearly irrelevant news before sending to LLM.
Supports both English and Chinese A-share articles.
Dedup uses normalized title comparison scoped per trade date —
same title on a different day is a different event and is kept.
"""

import json
import re
from typing import List, Tuple

from backend.database import get_conn

# English patterns for list articles
LIST_PATTERN = re.compile(
    r"^\d+\s+(best|top|worst|biggest|largest|most|highest|lowest)\b",
    re.IGNORECASE,
)
LIST_PATTERN_2 = re.compile(
    r"\b(top|best|worst)\s+\d+\b", re.IGNORECASE
)

# Chinese patterns for list/ranking articles
# Only filter pure ranking formats; daily summaries and named lists are kept
# because they contain stock-specific context useful for chart markers.
_CHINESE_LIST_PATTERN = re.compile(
    r"(涨幅榜|跌幅榜|涨停板|跌停板|榜单|排行)",
)

# Chinese short description threshold (Chinese chars take more info per char)
_CHINESE_SHORT_THRESHOLD = 20

# Patterns to strip from Chinese titles for dedup comparison.
# These are common suffixes added by different publishers to the same article:
# - Parenthetical notes: (修订稿), （豁免版）, (更正)
# - Source tags: |东方财富, ｜同花顺
# We do NOT strip content after ：because that's the actual news content.
_TITLE_SUFFIX_PATTERN = re.compile(
    r"[(\（][^)）]*[)）]|[\|｜].*$",
)


def _count_chinese_chars(text: str) -> int:
    """Count the number of Chinese characters in text."""
    return sum(1 for ch in text if '一' <= ch <= '鿿')


def _normalize_title_for_dedup(title: str) -> str:
    """Normalize a Chinese/English title for duplicate comparison.

    Strips publisher-specific suffixes (parenthetical notes, source tags)
    and removes punctuation, producing a canonical form for comparison.
    """
    t = title.strip()
    # Remove common publisher suffixes: (修订稿), (豁免版), |东方财富, etc.
    t = _TITLE_SUFFIX_PATTERN.sub('', t)
    # Keep only Chinese chars and alphanumeric
    result = []
    for ch in t:
        if '一' <= ch <= '鿿' or ch.isalnum():
            result.append(ch)
    return ''.join(result)


def _extract_stock_codes(text: str) -> list[str]:
    """Extract stock codes (6-digit numbers) from text."""
    return re.findall(r'(?<!\d)\d{6}(?!\d)', text)


def _check_article(
    title: str,
    description: str | None,
    tickers_json: str | None,
    symbol: str,
    seen_titles: set | None = None,
) -> Tuple[bool, str]:
    """Return (passed, reason). passed=True means article should proceed to Layer 1."""
    desc = (description or "").strip()
    t = (title or "").strip()

    # Rule 1: Empty description
    if not desc:
        return False, "empty_description"

    # Rule 2: Description too short
    # Use Chinese threshold if text is primarily Chinese
    if _count_chinese_chars(desc) > len(desc) * 0.3:
        if len(desc) < _CHINESE_SHORT_THRESHOLD:
            return False, "description_too_short"
    else:
        if len(desc) < 30:
            return False, "description_too_short"

    # Rule 3: Market roundup — mentions >10 tickers or >5 stock codes and target not in title
    tickers: list = []
    if tickers_json:
        try:
            tickers = json.loads(tickers_json)
        except (json.JSONDecodeError, TypeError):
            pass
    # English: >10 tickers and target not in title
    if len(tickers) > 10 and symbol.upper() not in (title or "").upper():
        return False, "market_roundup"
    # Chinese: >5 stock codes in text and target not in title
    stock_codes_in_text = _extract_stock_codes(desc + t)
    plain_code = symbol[:6] if symbol else ""
    if len(stock_codes_in_text) > 5 and plain_code not in t:
        return False, "chinese_market_roundup"

    # Rule 4: English list articles
    if LIST_PATTERN.search(t) or LIST_PATTERN_2.search(t):
        return False, "list_article"

    # Rule 5: Chinese list/ranking articles
    if _CHINESE_LIST_PATTERN.search(t):
        return False, "chinese_list_article"

    # Rule 6: Near-duplicate detection scoped per trade date.
    # Normalized title comparison: strips parenthetical suffixes like (修订稿),
    # (豁免版), |东方财富 etc. that different publishers add to the same article.
    # Same normalized title on the SAME day → duplicate.
    # Same title on a DIFFERENT day → different event, kept.
    if seen_titles is not None:
        norm = _normalize_title_for_dedup(t)
        if norm and norm in seen_titles:
            return False, "chinese_duplicate"
        seen_titles.add(norm)

    return True, "passed"


def run_layer0(symbol: str) -> dict:
    """Run Layer 0 on all news for a symbol. Returns stats."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT nr.id, nr.title, nr.description, nr.tickers_json,
                  COALESCE(na.trade_date, '') as trade_date
           FROM news_raw nr
           JOIN news_ticker nt ON nr.id = nt.news_id
           LEFT JOIN news_aligned na ON nr.id = na.news_id AND na.symbol = ?
           WHERE nt.symbol = ?
           AND nr.id NOT IN (
               SELECT news_id FROM layer0_results WHERE symbol = ?
           )""",
        (symbol, symbol, symbol),
    ).fetchall()

    stats = {"total": len(rows), "passed": 0, "filtered": 0}
    # Group by trade_date so same-title articles on different dates pass through
    from collections import OrderedDict
    by_date: dict[str, list] = OrderedDict()
    for row in rows:
        d = row["trade_date"] or ""
        by_date.setdefault(d, []).append(row)

    for date, date_rows in by_date.items():
        seen_titles: set[str] = set()  # Reset per date
        for row in date_rows:
            passed, reason = _check_article(
                row["title"], row["description"], row["tickers_json"], symbol, seen_titles
            )
            conn.execute(
                "INSERT OR IGNORE INTO layer0_results (news_id, symbol, passed, reason) VALUES (?, ?, ?, ?)",
                (row["id"], symbol, 1 if passed else 0, reason),
            )
            if passed:
                stats["passed"] += 1
            else:
                stats["filtered"] += 1

    conn.commit()
    conn.close()
    return stats