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
from backend.event_linking import (
    is_policy_event,
    link_notice_event,
    link_flash_event,
    link_policy_event,
)

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


async def _run_pipeline_for_symbol(symbol: str):
    """Run alignment + layer0 + layer1 for a symbol."""
    try:
        align_news_for_symbol(symbol)
    except Exception:
        logger.exception("Alignment failed for %s", symbol)
    await asyncio.sleep(0)
    try:
        run_layer0(symbol)
    except Exception:
        logger.exception("Layer0 failed for %s", symbol)
        return
    await asyncio.sleep(0)
    try:
        run_layer1(symbol)
    except Exception:
        logger.exception("Layer1 failed for %s", symbol)


def _collect_events_from_articles(articles: List[dict], category: str, symbol: str = ""):
    """Create events from newly inserted articles and link to stocks."""
    conn = get_conn()
    count = 0
    for art in articles:
        news_id = art.get("news_id") or art.get("id")
        if not news_id:
            continue
        event_id = f"evt_{news_id}"
        # Skip if event already exists
        exists = conn.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone()
        if exists:
            continue

        title = art.get("title", "").strip()
        if not title:
            continue

        desc = art.get("content") or art.get("description") or ""
        pub_date = art.get("published") or art.get("published_utc") or ""
        # Normalize date to YYYY-MM-DD
        event_date = pub_date[:10] if len(pub_date) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Determine impact from layer1 if available
        impact = None
        layer1 = conn.execute(
            "SELECT sentiment FROM layer1_results WHERE news_id = ?", (news_id,)
        ).fetchone()
        if layer1 and layer1["sentiment"]:
            impact = layer1["sentiment"]

        conn.execute(
            """INSERT OR IGNORE INTO events (id, title, description, event_date, category, impact, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, title, desc[:500], event_date, category, impact, art.get("source", "")),
        )

        # Link to stocks
        if category == "notice" and symbol:
            link_notice_event(conn, event_id, symbol)
        elif category == "flash":
            link_flash_event(conn, event_id, title, desc)
        elif category == "news" and is_policy_event(title, desc):
            # Update category to policy
            conn.execute("UPDATE events SET category = 'policy' WHERE id = ?", (event_id,))
            link_policy_event(conn, event_id, title, desc)

        count += 1

    conn.commit()
    conn.close()
    if count > 0:
        logger.info("Scheduler: collected %d events (category=%s)", count, category)
    return count


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
                        _collect_events_from_articles(articles, "news", t["symbol"])
                except Exception:
                    logger.exception("Scheduler: news fetch failed for %s", t["symbol"])
                    continue

            # Run pipeline for symbols with new articles
            for symbol in symbols_with_new:
                await _run_pipeline_for_symbol(symbol)

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
                        _collect_events_from_articles(notices, "notice", t["symbol"])
                        await _run_pipeline_for_symbol(t["symbol"])
                except Exception:
                    logger.exception("Scheduler: notice fetch failed for %s", t["symbol"])
                    continue
                await asyncio.sleep(0)

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
                _collect_events_from_articles(flash_articles, "flash")
                for symbol in matched:
                    await _run_pipeline_for_symbol(symbol)

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


def _backfill_events():
    """One-time backfill: create events from existing news_raw data."""
    conn = get_conn()
    # Only backfill if events table is empty
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if count > 0:
        conn.close()
        logger.info("Scheduler: events table already has %d rows, skipping backfill", count)
        return

    logger.info("Scheduler: backfilling events from existing news_raw...")
    rows = conn.execute(
        "SELECT id, title, description, published_utc, source_type FROM news_raw WHERE title IS NOT NULL"
    ).fetchall()

    ticker_names = {}
    for r in conn.execute("SELECT symbol, name FROM tickers WHERE last_ohlc_fetch IS NOT NULL").fetchall():
        ticker_names[r["symbol"]] = r["name"] or ""

    event_count = 0
    for row in rows:
        news_id = row["id"]
        event_id = f"evt_{news_id}"
        title = (row["title"] or "").strip()
        if not title:
            continue

        desc = row["description"] or ""
        pub_date = (row["published_utc"] or "")[:10]
        if len(pub_date) < 10:
            continue
        source_type = row["source_type"] or "news"

        # Determine category
        if source_type == "notice":
            category = "notice"
        elif source_type == "flash":
            category = "flash"
        elif is_policy_event(title, desc):
            category = "policy"
        else:
            # Include news-type articles as 'news' events (was previously dropped).
            # Note: this expands the events table by ~9K rows. If too noisy, we
            # can filter by sentiment != 'neutral' in a later migration.
            category = "news"

        # Get sentiment from layer1
        impact = None
        layer1 = conn.execute(
            "SELECT sentiment FROM layer1_results WHERE news_id = ?", (news_id,)
        ).fetchone()
        if layer1 and layer1["sentiment"]:
            impact = layer1["sentiment"]

        conn.execute(
            """INSERT OR IGNORE INTO events (id, title, description, event_date, category, impact, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, title, desc[:500], pub_date, category, impact, ""),
        )

        # Link to stocks
        if category == "notice":
            # Find the symbol from news_ticker
            nt = conn.execute(
                "SELECT symbol FROM news_ticker WHERE news_id = ?", (news_id,)
            ).fetchone()
            if nt:
                link_notice_event(conn, event_id, nt["symbol"])
        elif category == "flash":
            link_flash_event(conn, event_id, title, desc)
        elif category == "policy":
            link_policy_event(conn, event_id, title, desc)
        elif category == "news":
            # News events: link to the first ticker this news is mapped to.
            # Most news articles correspond to a single ticker that the
            # scheduler picked up via news_ticker.
            nt = conn.execute(
                "SELECT symbol FROM news_ticker WHERE news_id = ? LIMIT 1",
                (news_id,),
            ).fetchone()
            if nt:
                conn.execute(
                    "INSERT OR IGNORE INTO event_stock (event_id, symbol) VALUES (?, ?)",
                    (event_id, nt["symbol"]),
                )

        event_count += 1

    conn.commit()
    conn.close()
    logger.info("Scheduler: backfilled %d events", event_count)


async def scheduler_main():
    """Entry point: start all background fetch loops."""
    logger.info("Scheduler: starting background fetch loops")
    # Backfill events from existing data (one-time)
    try:
        _backfill_events()
    except Exception:
        logger.exception("Scheduler: event backfill failed")

    # Initial delay to let the app fully start
    await asyncio.sleep(10)

    await asyncio.gather(
        _fetch_ohlc_loop(),
        _fetch_news_loop(),
        _fetch_flash_loop(),
        _fetch_notices_loop(),
    )