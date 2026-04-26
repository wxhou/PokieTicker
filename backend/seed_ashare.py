"""Seed script: populate A-share OHLC data for 5 stocks so K-line chart shows real data.

Usage:
    cd /Users/wxhou/Documents/PokieTicker && \
    ~/.conda/envs/zhangxun/bin/python -m backend.seed_ashare
"""
import sys
import logging
from datetime import datetime, timedelta

# Ensure backend is on the path
sys.path.insert(0, str(__file__).rsplit("/backend/", 1)[0])

from backend.akshare.client import fetch_ohlc, fetch_news, fetch_news_bulk, resolve_code
from backend.database import get_conn, init_db
from backend.pipeline.alignment import align_news_for_symbol

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Target stocks
STOCKS = [
    {"code": "600519", "name": "贵州茅台", "resolved": "600519.SH"},
    {"code": "300750", "name": "宁德时代", "resolved": "300750.SZ"},
    {"code": "002594", "name": "比亚迪",   "resolved": "002594.SZ"},
    {"code": "600036", "name": "招商银行", "resolved": "600036.SH"},
    {"code": "000001", "name": "上证指数", "resolved": "000001.SH"},
]

# 2 years of daily data (extra buffer for alignment horizon T+10)
DAYS_SPAN = 2 * 366


def _date_range():
    end = datetime.now().date()
    start = end - timedelta(days=DAYS_SPAN)
    return start.isoformat().replace("-", ""), end.isoformat().replace("-", "")


def _idempotent_upsert_ohlc(conn, rows, symbol):
    """Insert or replace OHLC rows for a symbol (idempotent)."""
    inserted = 0
    for row in rows:
        conn.execute(
            """INSERT OR REPLACE INTO ohlc
               (symbol, date, open, high, low, close, volume, pct_chg)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                symbol,
                row["date"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                row.get("pct_chg", 0),
            ),
        )
        inserted += 1
    return inserted


def _idempotent_register_ticker(conn, symbol, name):
    """Register a stock in tickers table (idempotent)."""
    conn.execute(
        """INSERT OR IGNORE INTO tickers (symbol, name) VALUES (?, ?)""",
        (symbol, name),
    )


def seed_stock(stock: dict) -> dict:
    """Fetch and store OHLC + news for one stock. Returns status dict."""
    code = stock["code"]
    name = stock["name"]
    symbol = stock["resolved"]
    start_date, end_date = _date_range()

    result = {
        "code": code,
        "name": name,
        "symbol": symbol,
        "ohlc_rows": 0,
        "news_items": 0,
        "status": "ok",
    }

    try:
        # 1. Fetch OHLC
        logger.info("[%s] Fetching OHLC %s – %s (%s)", code, start_date, end_date, symbol)
        ohlc_rows = fetch_ohlc(code, start_date, end_date)
        logger.info("[%s] Got %d OHLC rows", code, len(ohlc_rows))

        conn = get_conn()
        try:
            # Idempotent: INSERT OR REPLACE ensures run-once safety
            _idempotent_register_ticker(conn, symbol, name)
            inserted = _idempotent_upsert_ohlc(conn, ohlc_rows, symbol)
            result["ohlc_rows"] = inserted
            conn.commit()
            logger.info("[%s] Inserted/replaced %d OHLC rows", code, inserted)
        finally:
            conn.close()

        # 2. Fetch and store news (bulk: ~500 articles per stock)
        try:
            logger.info("[%s] Fetching bulk news", code)
            news_items = fetch_news_bulk(code, max_pages=5)
            logger.info("[%s] Got %d news items", code, len(news_items))

            conn = get_conn()
            try:
                for art in news_items:
                    news_id = art.get("news_id")
                    if not news_id:
                        continue
                    conn.execute(
                        """INSERT OR IGNORE INTO news_raw
                           (id, title, description, published_utc, article_url)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            news_id,
                            art.get("title"),
                            art.get("content", ""),
                            art.get("published"),
                            art.get("url"),
                        ),
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                        (news_id, symbol),
                    )
                conn.commit()
                result["news_items"] = len(news_items)
                logger.info("[%s] Stored %d news items", code, len(news_items))
            finally:
                conn.close()
        except Exception as e:
            logger.warning("[%s] News fetch/store failed (continuing): %s", code, e)
            result["news_items"] = 0
            result["status"] = "partial"

        # 3. Align news → trading days (use full symbol to match news_ticker)
        try:
            align_result = align_news_for_symbol(symbol)
            logger.info(
                "[%s] Aligned %d news items (total unaligned: %d)",
                code,
                align_result.get("aligned", 0),
                align_result.get("total_news", 0),
            )
        except Exception as e:
            logger.warning("[%s] Alignment failed (non-fatal): %s", code, e)

    except Exception as e:
        logger.error("[%s] Fatal error during seeding: %s", code, e)
        result["status"] = "failed"
        result["error"] = str(e)

    return result


def main():
    logger.info("=" * 60)
    logger.info("Starting A-share seed: %d stocks", len(STOCKS))
    logger.info("=" * 60)

    # Ensure DB and cache tables exist
    init_db()

    summary = {"total": len(STOCKS), "ok": 0, "partial": 0, "failed": 0}

    for stock in STOCKS:
        result = seed_stock(stock)
        status = result["status"]
        summary[status] = summary.get(status, 0) + 1

        logger.info(
            "  [%s] %s | OHLC: %d rows | News: %d items | Status: %s",
            result["code"],
            result["name"],
            result["ohlc_rows"],
            result["news_items"],
            status,
        )

    logger.info("=" * 60)
    logger.info(
        "Seed complete — ok: %d, partial: %d, failed: %d",
        summary["ok"],
        summary["partial"],
        summary["failed"],
    )

    # Verify data
    conn = get_conn()
    try:
        for stock in STOCKS:
            symbol = stock["resolved"]
            count = conn.execute(
                "SELECT COUNT(*) as c FROM ohlc WHERE symbol = ?",
                (symbol,),
            ).fetchone()["c"]
            ticker = conn.execute(
                "SELECT name FROM tickers WHERE symbol = ?",
                (symbol,),
            ).fetchone()
            logger.info(
                "  DB verify: %s (%s) → %d OHLC rows | ticker name: %s",
                symbol,
                stock["name"],
                count,
                ticker["name"] if ticker else "NOT FOUND",
            )
    finally:
        conn.close()

    # Exit with non-zero if any stock failed completely
    if summary["failed"] > 0:
        logger.warning("Some stocks failed — check errors above")
        sys.exit(1)


if __name__ == "__main__":
    main()
