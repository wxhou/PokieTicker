"""Event-stock linking logic.

Matches events to affected stocks via:
- Direct symbol (notices)
- Name matching (flash news)
- Industry keyword mapping (policy)
"""

import re
import logging
from typing import Dict, List, Optional

from backend.database import get_conn

logger = logging.getLogger(__name__)

# Policy keywords for filtering
_POLICY_KEYWORDS = re.compile(
    r"政策|央行|降准|降息|加息|两会|国务院|发改委|证监会|财政部|"
    r"人民银行|银保监|外汇局|央行行长|货币政策|财政政策|"
    r"注册制|退市|IPO|再融资|减持|增持|回购|分红|"
    r"国企改革|混改|碳中和|碳达峰|新质生产力|数字经济"
)

# Industry keyword -> stock symbol mapping
_INDUSTRY_MAP: Dict[str, List[str]] = {}


def _get_industry_map() -> Dict[str, List[str]]:
    """Build industry keyword -> stock symbols mapping from active tickers."""
    if _INDUSTRY_MAP:
        return _INDUSTRY_MAP

    conn = get_conn()
    rows = conn.execute(
        "SELECT symbol, name, sector FROM tickers WHERE last_ohlc_fetch IS NOT NULL"
    ).fetchall()
    conn.close()

    # Group by sector
    sector_stocks: Dict[str, List[str]] = {}
    for r in rows:
        sector = r["sector"] or ""
        if sector:
            sector_stocks.setdefault(sector, []).append(r["symbol"])

    # Map common industry keywords to sectors
    industry_keywords = {
        "新能源": ["新能源", "光伏", "风电", "储能", "锂电"],
        "半导体": ["半导体", "芯片", "集成电路"],
        "医药": ["医药", "医疗", "生物", "制药"],
        "白酒": ["白酒", "酿酒"],
        "银行": ["银行", "金融"],
        "房地产": ["房地产", "地产", "楼市"],
        "消费": ["消费", "零售", "电商"],
        "科技": ["科技", "互联网", "AI", "人工智能"],
        "汽车": ["汽车", "新能源汽车", "电动车"],
        "电力": ["电力", "电网", "核电"],
    }

    for industry, keywords in industry_keywords.items():
        symbols = []
        for sector, stocks in sector_stocks.items():
            if any(kw in sector for kw in keywords):
                symbols.extend(stocks)
        # Also match by stock name
        for r in rows:
            name = r["name"] or ""
            if any(kw in name for kw in keywords):
                if r["symbol"] not in symbols:
                    symbols.append(r["symbol"])
        if symbols:
            _INDUSTRY_MAP[industry] = list(set(symbols))

    return _INDUSTRY_MAP


def get_active_ticker_names() -> Dict[str, str]:
    """Get symbol -> name mapping for active tickers."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT symbol, name FROM tickers WHERE last_ohlc_fetch IS NOT NULL"
    ).fetchall()
    conn.close()
    return {r["symbol"]: (r["name"] or "") for r in rows}


def is_policy_event(title: str, description: str = "") -> bool:
    """Check if an article title/description contains policy keywords."""
    text = f"{title} {description}"
    return bool(_POLICY_KEYWORDS.search(text))


def link_notice_event(conn, event_id: str, symbol: str):
    """Link a notice event directly to its stock."""
    conn.execute(
        "INSERT OR IGNORE INTO event_stock (event_id, symbol) VALUES (?, ?)",
        (event_id, symbol),
    )


def link_flash_event(conn, event_id: str, title: str, description: str = ""):
    """Link a flash event to stocks via name matching."""
    text = f"{title} {description}"
    names = get_active_ticker_names()
    matched = False
    for symbol, name in names.items():
        if name and len(name) >= 2 and name in text:
            conn.execute(
                "INSERT OR IGNORE INTO event_stock (event_id, symbol) VALUES (?, ?)",
                (event_id, symbol),
            )
            matched = True
    return matched


def link_policy_event(conn, event_id: str, title: str, description: str = ""):
    """Link a policy event to stocks via industry keyword mapping."""
    text = f"{title} {description}"
    industry_map = _get_industry_map()
    matched = False
    for industry, symbols in industry_map.items():
        if industry in text:
            for symbol in symbols:
                conn.execute(
                    "INSERT OR IGNORE INTO event_stock (event_id, symbol) VALUES (?, ?)",
                    (event_id, symbol),
                )
            matched = True
    return matched
