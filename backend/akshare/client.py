"""
AKShare data client with caching and retry.

Replaces polygon/client.py for China A-share data.
Retry template mirrors polygon/client.py http_get pattern.
"""
import sqlite3
import time
from http.client import HTTPException
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import akshare as ak
import requests as http_requests

from backend.config import settings

logger = logging.getLogger(__name__)

# ── SQLite cache ──────────────────────────────────────────────────────────────

_CACHE_TTL = {
    "ohlc": 86400,    # 1 day
    "news": 600,       # 10 minutes
    "limit": 86400,    # 1 day
}


def _cache_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _cache_get(table: str, key: str) -> Optional[Any]:
    """Return cached data if fresh, else None."""
    conn = _cache_conn()
    try:
        row = conn.execute(
            f"SELECT data_json, fetched_at FROM {table}_cache WHERE key_col = ?",
            (key,),
        ).fetchone()
        if not row:
            return None
        fetched = datetime.fromisoformat(row["fetched_at"])
        ttl = _CACHE_TTL.get(table, 600)
        if (datetime.now() - fetched).total_seconds() > ttl:
            return None
        return json.loads(row["data_json"])
    finally:
        conn.close()


def _cache_set(table: str, key: str, data: Any) -> None:
    conn = _cache_conn()
    try:
        conn.execute(
            f"""INSERT OR REPLACE INTO {table}_cache (key_col, data_json, fetched_at)
               VALUES (?, ?, ?)""",
            (key, json.dumps(data, ensure_ascii=False), datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


# ── Cache table init ─────────────────────────────────────────────────────────

def init_cache_tables() -> None:
    conn = _cache_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ohlc_cache (
            key_col    TEXT PRIMARY KEY,   -- e.g. "600519.SH,20260401,20260418"
            data_json  TEXT,
            fetched_at TEXT
        );
        CREATE TABLE IF NOT EXISTS news_cache (
            key_col    TEXT PRIMARY KEY,   -- e.g. "600519,20260417"
            data_json  TEXT,
            fetched_at TEXT
        );
        CREATE TABLE IF NOT EXISTS limit_cache (
            key_col    TEXT PRIMARY KEY,   -- e.g. "20260417,U"
            data_json  TEXT,
            fetched_at TEXT
        );
    """)
    conn.close()


# ── Retry wrapper ─────────────────────────────────────────────────────────────

def _with_retry(fn, *args, max_retries: int = 3, **kwargs):
    """Call fn(*args, **kwargs) with exponential-backoff retry on connection errors."""
    last_err = None
    for i in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except (
            ConnectionResetError,
            ConnectionRefusedError,
            OSError,   # covers requests.exceptions.ConnectionError + ProtocolError
            HTTPException,   # covers RemoteDisconnected
        ) as e:
            last_err = e
            if i < max_retries - 1:
                backoff = min(2 ** i + 0.5, 30)
                time.sleep(backoff)
    raise last_err


# ── OHLC ─────────────────────────────────────────────────────────────────────

def resolve_code(code: str) -> str:
    """Resolve a stock code to exchange-qualified form.

    600519 -> 600519.SH (Shanghai)
    000001 -> 000001.SZ (Shenzhen)
    00700  -> 00700.HK (HK)
    Already qualified codes returned unchanged.
    """
    code = code.strip().upper()
    if "." in code:
        return code
    # HK: 5 digits starting 0
    if len(code) == 5 and code.startswith("0"):
        return f"{code}.HK"
    # A-share: 6 digits
    if len(code) == 6 and code.isdigit():
        if code.startswith(("0", "3")):
            return f"{code}.SZ"
        elif code.startswith(("6",)):
            return f"{code}.SH"
        else:
            return f"{code}.SH"   # default to SH
    return code


def fetch_ohlc(
    symbol: str,
    start_date: str,   # YYYYMMDD
    end_date: str,     # YYYYMMDD
) -> List[Dict[str, Any]]:
    """Fetch daily OHLC for a stock, with local cache (TTL=1 day).

    Tries Tencent source (stock_zh_a_hist_tx) first since eastmoney push2his
    is blocked from this machine. Falls back to eastmoney (stock_zh_a_hist).
    Indices use csindex (only Tencent index endpoint available).
    """
    # Normalise symbol
    ts_code = resolve_code(symbol)
    cache_key = f"{ts_code},{start_date},{end_date}"

    cached = _cache_get("ohlc", cache_key)
    if cached is not None:
        return cached

    result = []

    # Detect index: plain code "000001" or resolved to 000001.SH is the Shanghai Composite
    # Use csindex for indices (eastmoney)
    is_index = symbol.strip() == "000001"
    if is_index:
        rows = _with_retry(
            ak.stock_zh_index_hist_csindex,
            symbol="000001",
            start_date=start_date,
            end_date=end_date,
        )
        for _, r in rows.iterrows():
            result.append({
                "date":    str(r["日期"]),
                "symbol":  "000001.SH",
                "open":    float(r["开盘"]),
                "high":    float(r["最高"]),
                "low":     float(r["最低"]),
                "close":   float(r["收盘"]),
                "volume":  float(r["成交量"]) * 10000,   # 万手 → shares
                "amount":  float(r["成交金额"]) * 10000,  # 亿元 → CNY
                "pct_chg": float(r["涨跌幅"]),
            })
    else:
        # Primary: Tencent source (stock_zh_a_hist_tx)
        # Convert ts_code to tx format: 600519.SH → sh600519, 300750.SZ → sz300750
        tx_code = (
            "sh" + ts_code[:6] if ts_code.endswith(".SH") else
            "sz" + ts_code[:6] if ts_code.endswith(".SZ") else
            "sh" + ts_code[:6]
        )
        try:
            rows = _with_retry(
                ak.stock_zh_a_hist_tx,
                symbol=tx_code,
                start_date=start_date,
                end_date=end_date,
            )
            for _, r in rows.iterrows():
                result.append({
                    "date":    str(r["date"]),
                    "symbol":  ts_code,
                    "open":    float(r["open"]),
                    "high":    float(r["high"]),
                    "low":     float(r["low"]),
                    "close":   float(r["close"]),
                    "volume":  float(r.get("amount", 0)) / (float(r["close"]) / 1e6) if float(r["close"]) != 0 else 0,  # amount/price ≈ volume
                    "amount":  float(r.get("amount", 0)) * 1e4,  # 万元 → CNY
                    "pct_chg": None,   # tx source does not provide pct_chg directly
                })
        except Exception as primary_err:
            # Fallback: eastmoney source
            try:
                rows = _with_retry(
                    ak.stock_zh_a_hist,
                    symbol=ts_code[:6],
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq",
                )
                for _, r in rows.iterrows():
                    result.append({
                        "date":    str(r["日期"]),
                        "symbol":  ts_code,
                        "open":    float(r["开盘"]),
                        "high":    float(r["最高"]),
                        "low":     float(r["最低"]),
                        "close":   float(r["收盘"]),
                        "volume":  float(r["成交量"]),
                        "amount":  float(r["成交额"]),
                        "pct_chg": float(r["涨跌幅"]),
                    })
            except Exception:
                # Re-raise the primary error so callers see a real failure
                raise primary_err

    _cache_set("ohlc", cache_key, result)
    return result


# ── News ──────────────────────────────────────────────────────────────────────

def fetch_news(symbol: str, date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch company news for a stock, with local cache (TTL=10 min).

    If date is None, fetches recent news (up to 10 items from AKShare).
    Returns list of news dicts.
    """
    ts_code = resolve_code(symbol)
    plain = ts_code[:6]
    cache_key = f"{plain},{date or 'recent'}"

    cached = _cache_get("news", cache_key)
    if cached is not None:
        return cached

    rows = _with_retry(ak.stock_news_em, symbol=plain)

    result = []
    for _, r in rows.iterrows():
        result.append({
            "news_id":     f"{plain}_{r['发布时间']}",
            "symbol":      plain,
            "title":        str(r["新闻标题"]),
            "content":      str(r.get("新闻内容", "")),
            "published":    str(r["发布时间"]),
            "source":       str(r.get("文章来源", "")),
            "url":          str(r.get("新闻链接", "")),
        })

    _cache_set("news", cache_key, result)
    return result


# ── Bulk News (eastmoney search API directly) ────────────────────────────────

_EM_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"
_EM_SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://so.eastmoney.com/news/s",
}


def _em_search_page(keyword: str, page_index: int, page_size: int = 100) -> List[Dict[str, Any]]:
    """Fetch one page of news from eastmoney search API.

    Returns raw article dicts from the API response.
    """
    inner_param = {
        "uid": "",
        "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": page_index,
                "pageSize": page_size,
                "preTag": "",
                "postTag": "",
            }
        },
    }

    params = {
        "cb": "jQuery_cb",
        "param": json.dumps(inner_param, ensure_ascii=False),
        "_": str(int(time.time() * 1000)),
    }

    resp = http_requests.get(_EM_SEARCH_URL, params=params, headers=_EM_SEARCH_HEADERS, timeout=20)
    text = resp.text.strip()

    # Strip JSONP wrapper
    prefix = "jQuery_cb("
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(")"):
        text = text[:-1]

    data = json.loads(text)
    return data.get("result", {}).get("cmsArticleWebOld", [])


def fetch_news_bulk(
    symbol: str,
    max_pages: int = 5,
    page_size: int = 100,
) -> List[Dict[str, Any]]:
    """Fetch bulk historical news for an A-share stock via eastmoney search API.

    Bypasses AKShare's stock_news_em (which hardcodes pageSize=10) by calling
    the eastmoney search API directly with larger pageSize and pagination.

    Args:
        symbol: Stock code, e.g. "600519" or "600519.SH"
        max_pages: Maximum number of pages to fetch (default 5 = ~500 articles)
        page_size: Articles per page (default 100)

    Returns:
        List of news dicts with keys: news_id, symbol, title, content, published, source, url
    """
    ts_code = resolve_code(symbol)
    plain = ts_code[:6]
    cache_key = f"{plain},bulk,{max_pages}"

    cached = _cache_get("news", cache_key)
    if cached is not None:
        return cached

    all_articles: List[Dict[str, Any]] = []
    seen_codes = set()

    for page in range(1, max_pages + 1):
        try:
            items = _with_retry(_em_search_page, plain, page, page_size)
        except Exception as e:
            logger.warning("fetch_news_bulk: page %d failed for %s: %s", page, plain, e)
            break

        if not items:
            break

        new_count = 0
        for item in items:
            code = item.get("code", "")
            if code in seen_codes:
                continue
            seen_codes.add(code)

            all_articles.append({
                "news_id":  f"{plain}_{item.get('date', '')}",
                "symbol":   plain,
                "title":    str(item.get("title", "")).replace("<em>", "").replace("</em>", ""),
                "content":  str(item.get("content", "")).replace("<em>", "").replace("</em>", "").replace("\u3000", "").replace("\r\n", " "),
                "published": str(item.get("date", "")),
                "source":   str(item.get("mediaName", "")),
                "url":      f"http://finance.eastmoney.com/a/{code}.html" if code else "",
            })
            new_count += 1

        logger.info("fetch_news_bulk: %s page %d → %d new (total %d)", plain, page, new_count, len(all_articles))

        # If page returned fewer than page_size, we've reached the end
        if len(items) < page_size:
            break

        # Small delay between pages to be polite
        time.sleep(0.3)

    _cache_set("news", cache_key, all_articles)
    return all_articles


# ── Limit-up / limit-down ──────────────────────────────────────────────────────

def fetch_limit_up_down(date: str, limit_type: str = "U") -> List[Dict[str, Any]]:
    """Fetch limit-up (U) or limit-down (D) pool for a given date.

    date: YYYYMMDD
    limit_type: "U" = 涨停, "D" = 跌停
    Returns list of stock dicts.
    """
    cache_key = f"{date},{limit_type}"

    cached = _cache_get("limit", cache_key)
    if cached is not None:
        return cached

    rows = _with_retry(ak.stock_zt_pool_em, date=date)

    # Filter by direction: 涨幅 >= 9.5% → limit-up, 涨幅 <= -9.5% → limit-down
    if limit_type == "U":
        rows = rows[rows["涨跌幅"] >= 9.5]
    else:
        rows = rows[rows["涨跌幅"] <= -9.5]

    result = []
    for _, r in rows.iterrows():
        result.append({
            "code":    str(r.get("代码", "")),
            "name":    str(r.get("名称", "")),
            "pct_chg": float(r.get("涨跌幅", 0)),
            "lianban": int(r.get("连板数", 0)),
        })

    _cache_set("limit", cache_key, result)
    return result


# ── Stock search ───────────────────────────────────────────────────────────────

# Local cache of all A-share stock basic info for fast search
_stock_basic_cache: Optional[List[Dict[str, str]]] = None


def _get_stock_basic() -> List[Dict[str, str]]:
    """Get all A-share stock basic info (cached in memory)."""
    global _stock_basic_cache
    if _stock_basic_cache is not None:
        return _stock_basic_cache
    df = _with_retry(ak.stock_info_a_code_name)
    _stock_basic_cache = [
        {"code": str(r["code"]), "name": str(r["name"])}
        for _, r in df.iterrows()
    ]
    return _stock_basic_cache


def search_stocks(keyword: str) -> List[Dict[str, str]]:
    """Search A-share stocks by name or code. Fast in-memory search."""
    basic = _get_stock_basic()
    kw = keyword.strip().lower()
    matches = [
        s for s in basic
        if kw in s["code"].lower() or kw in s["name"].lower()
    ]
    return matches[:20]


def stock_info_a_code_name(code: str) -> dict | None:
    """Look up stock info by code from cached basic info.

    Returns {"name": "贵州茅台"} or None if not found.
    """
    basic = _get_stock_basic()
    for s in basic:
        if s["code"] == code:
            return {"name": s["name"]}
    return None
