"""Background scheduler for periodic A-share data fetching.

Runs on FastAPI startup as an asyncio background task.
Fetches news, notices, and flash news at configured intervals,
then runs alignment + layer0/layer1 pipeline automatically.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List

from backend.database import get_conn
from backend.akshare.client import (
    fetch_ohlc,
    fetch_news_bulk,
    fetch_notices,
    fetch_flash_news,
    match_flash_to_tickers,
    resolve_code,
    _get_stock_basic,
)
from backend.pipeline.alignment import align_news_for_symbol
from backend.pipeline.layer0 import run_layer0
from backend.pipeline.layer1 import run_layer1

logger = logging.getLogger(__name__)

# Fetch intervals (seconds)
OHLC_INTERVAL = 30 * 60       # 30 minutes
NEWS_INTERVAL = 30 * 60       # 30 minutes
NOTICE_INTERVAL = 24 * 3600   # 24 hours
FLASH_INTERVAL = 15 * 60      # 15 minutes


def _get_active_tickers() -> List[dict]:
    """Get all active tickers from database."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT symbol, name FROM tickers WHERE last_ohlc_fetch IS NOT NULL"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _insert_news_bulk(symbol: str, articles: List[dict], source_type: str = "news") -> int:
    """Insert news articles into DB with dedup. Returns count of new articles."""
    ts_code = resolve_code(symbol)
    conn = get_conn()
    new_count = 0
    for art in articles:
        news_id = art.get("news_id") or art.get("id")
        if not news_id:
            continue
        # Check dedup
        exists = conn.execute(
            "SELECT 1 FROM news_raw WHERE id = ?", (news_id,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            """INSERT OR IGNORE INTO news_raw
               (id, title, description, publisher, author,
                published_utc, article_url, amp_url, tickers_json, insights_json, source_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (news_id, art.get("title"), art.get("content") or art.get("description"),
             art.get("source") or art.get("publisher"), art.get("author"),
             art.get("published") or art.get("published_utc"),
             art.get("url") or art.get("article_url"), art.get("amp_url"),
             None, None, source_type),
        )
        conn.execute(
            "INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)",
            (news_id, ts_code),
        )
        new_count += 1
    conn.commit()
    conn.close()
    return new_count


def _insert_flash_news(matched: dict) -> int:
    """Insert matched flash news articles into DB. Returns total new count."""
    conn = get_conn()
    new_count = 0
    for symbol, articles in matched.items():
        ts_code = resolve_code(symbol) if "." not in symbol else symbol
        for art in articles:
            news_id = art.get("id") or art.get("news_id")
            if not news_id:
                continue
            exists = conn.execute(
                "SELECT 1 FROM news_raw WHERE id = ?", (news_id,)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO news_raw
                   (id, title, description, publisher, author,
                    published_utc, article_url, amp_url, tickers_json, insights_json, source_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (news_id, art.get("title"), art.get("content") or art.get("description"),
                 art.get("publisher"), art.get("author"),
                 art.get("published") or art.get("published_utc"),
                 art.get("url") or art.get("article_url"), art.get("amp_url"),
                 None, None, "flash"),
            )
            conn.execute(
                "INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                (news_id, ts_code),
            )
            new_count += 1
    conn.commit()
    conn.close()
    return new_count


def _run_pipeline_for_symbol(symbol: str):
    """Run alignment + layer0 + layer1 for a symbol."""
    try:
        align_news_for_symbol(symbol)
    except Exception:
        logger.exception("Alignment failed for %s", symbol)
    try:
        run_layer0(symbol)
    except Exception:
        logger.exception("Layer0 failed for %s", symbol)
        return
    try:
        run_layer1(symbol)
    except Exception:
        logger.exception("Layer1 failed for %s", symbol)


async def _fetch_news_loop():
    """Periodically fetch news for all active tickers."""
    while True:
        try:
            tickers = _get_active_tickers()
            logger.info("Scheduler: fetching news for %d tickers", len(tickers))
            symbols_with_new = []
            for t in tickers:
                try:
                    articles = fetch_news_bulk(t["symbol"])
                    new_count = _insert_news_bulk(t["symbol"], articles, source_type="news")
                    if new_count > 0:
                        symbols_with_new.append(t["symbol"])
                        logger.info("Scheduler: %d new news for %s", new_count, t["symbol"])
                except Exception:
                    logger.exception("Scheduler: news fetch failed for %s", t["symbol"])
                    continue

            # Run pipeline for symbols with new articles
            for symbol in symbols_with_new:
                _run_pipeline_for_symbol(symbol)

        except Exception:
            logger.exception("Scheduler: news loop error")

        await asyncio.sleep(NEWS_INTERVAL)


async def _fetch_notices_loop():
    """Periodically fetch notices for all active tickers."""
    while True:
        try:
            tickers = _get_active_tickers()
            logger.info("Scheduler: fetching notices for %d tickers", len(tickers))
            for t in tickers:
                try:
                    notices = fetch_notices(t["symbol"])
                    new_count = _insert_news_bulk(t["symbol"], notices, source_type="notice")
                    if new_count > 0:
                        logger.info("Scheduler: %d new notices for %s", new_count, t["symbol"])
                        _run_pipeline_for_symbol(t["symbol"])
                except Exception:
                    logger.exception("Scheduler: notice fetch failed for %s", t["symbol"])
                    continue

        except Exception:
            logger.exception("Scheduler: notices loop error")

        await asyncio.sleep(NOTICE_INTERVAL)


async def _fetch_flash_loop():
    """Periodically fetch flash news and match to tickers."""
    while True:
        try:
            flash_articles = fetch_flash_news()
            if not flash_articles:
                await asyncio.sleep(FLASH_INTERVAL)
                continue

            # Get ticker basic info for matching
            try:
                basic = _get_stock_basic()
            except Exception:
                logger.exception("Scheduler: failed to get stock basic info")
                await asyncio.sleep(FLASH_INTERVAL)
                continue

            matched = match_flash_to_tickers(flash_articles, basic)
            new_count = _insert_flash_news(matched)
            if new_count > 0:
                logger.info("Scheduler: %d new flash news matched", new_count)
                for symbol in matched:
                    _run_pipeline_for_symbol(symbol)

        except Exception:
            logger.exception("Scheduler: flash loop error")

        await asyncio.sleep(FLASH_INTERVAL)


def _fetch_ohlc_for_tickers():
    """Fetch latest OHLC data for all active tickers (sync, called from loop)."""
    conn = get_conn()
    tickers = conn.execute(
        "SELECT symbol FROM tickers WHERE last_ohlc_fetch IS NOT NULL"
    ).fetchall()
    conn.close()

    today = datetime.now(timezone.utc).date()
    # Fetch last 5 days to cover weekends/holidays
    start = (today - timedelta(days=5)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    for t in tickers:
        symbol = t[0]
        try:
            rows = fetch_ohlc(symbol, start_date=start, end_date=end)
            if not rows:
                continue
            conn = get_conn()
            for row in rows:
                conn.execute(
                    """INSERT OR IGNORE INTO ohlc
                       (symbol, date, open, high, low, close, volume, vwap, transactions, pct_chg)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (symbol, row["date"], row["open"], row["high"], row["low"],
                     row["close"], row["volume"], row.get("vwap"),
                     row.get("transactions"), row.get("pct_chg")),
                )
            conn.execute(
                "UPDATE tickers SET last_ohlc_fetch = ? WHERE symbol = ?",
                (end, symbol),
            )
            conn.commit()
            conn.close()
        except Exception:
            logger.exception("Scheduler: OHLC fetch failed for %s", symbol)


async def _fetch_ohlc_loop():
    """Periodically fetch OHLC data for all active tickers."""
    while True:
        try:
            _fetch_ohlc_for_tickers()
        except Exception:
            logger.exception("Scheduler: OHLC loop error")

        await asyncio.sleep(OHLC_INTERVAL)


async def scheduler_main():
    """Entry point: start all background fetch loops."""
    logger.info("Scheduler: starting background fetch loops")
    # Initial delay to let the app fully start
    await asyncio.sleep(10)

    await asyncio.gather(
        _fetch_ohlc_loop(),
        _fetch_news_loop(),
        _fetch_flash_loop(),
        _fetch_notices_loop(),
    )