"""Stock data API — powered by AKShare (China A-share data)."""

import json
import logging

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone

from backend.akshare.client import fetch_ohlc, fetch_news, search_stocks, resolve_code
from backend.database import get_conn
from backend.pipeline.alignment import align_news_for_symbol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


class AddStockRequest(BaseModel):
    code: str  # e.g. "600519" or "000001"
    name: Optional[str] = None


@router.get("")
def list_stocks():
    """List all tracked stocks."""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tickers ORDER BY symbol").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/search")
def search(q: str = Query(..., min_length=1)):
    """Search A-share stocks by code or name using AKShare."""
    try:
        results = search_stocks(q)
        return results
    except Exception as e:
        logger.error("AKShare search failed: %s", e)
        # Fallback: search local DB
        conn = get_conn()
        local = conn.execute(
            "SELECT symbol, name FROM ohlc WHERE symbol LIKE ? OR symbol LIKE ? LIMIT 10",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
        conn.close()
        return [dict(r) for r in local]


@router.get("/{code}/ohlc")
def get_ohlc(
    code: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """Get OHLC data for a stock.

    Supports plain codes (e.g. "600519") which are auto-resolved to
    exchange-qualified form (e.g. "600519.SH").
    """
    # Normalize: resolve plain code to exchange-qualified form
    resolved = resolve_code(code)

    conn = get_conn()

    query = "SELECT * FROM ohlc WHERE symbol = ?"
    params: list = [resolved]

    if start:
        query += " AND date >= ?"
        params.append(start)
    if end:
        query += " AND date <= ?"
        params.append(end)

    query += " ORDER BY date ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No OHLC data for {resolved}")

    return [dict(r) for r in rows]


@router.get("/{code}/news")
def get_news(code: str, limit: int = Query(20, ge=1, le=100)):
    """Get news for a stock."""
    resolved = resolve_code(code)
    plain = resolved[:6]  # strip .SH/.SZ suffix for AKShare

    try:
        news_items = fetch_news(plain)
        return news_items[:limit]
    except Exception as e:
        logger.error("AKShare news failed for %s: %s", code, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch news: {e}")


@router.get("/{code}/limit-up-down")
def get_limit_up_down(
    code: str,
    limit_type: str = Query("U", pattern="^[UD]$"),
):
    """Get limit-up (U) or limit-down (D) stocks for today."""
    today = datetime.now().strftime("%Y%m%d")
    from backend.akshare.client import fetch_limit_up_down
    try:
        rows = fetch_limit_up_down(today, limit_type)
        return rows
    except Exception as e:
        logger.error("AKShare limit-up-down failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch limit pool: {e}")


@router.post("")
def add_stock(req: AddStockRequest, background_tasks: BackgroundTasks):
    """Add a new stock and trigger background data fetch."""
    resolved = resolve_code(req.code)
    plain = resolved[:6]

    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO tickers (symbol, name) VALUES (?, ?)",
        (resolved, req.name or plain),
    )
    conn.commit()
    conn.close()

    background_tasks.add_task(_fetch_stock_data, resolved)
    return {
        "code": resolved,
        "status": "added",
        "message": "Data fetch started in background",
    }


def _fetch_stock_data(resolved: str):
    """Background task to fetch OHLC and news for a stock via AKShare."""
    today = datetime.now().date()
    start = (today - timedelta(days=2 * 366)).isoformat().replace("-", "")
    end = today.isoformat().replace("-", "")
    plain = resolved[:6]

    try:
        # Fetch OHLC
        ohlc_rows = fetch_ohlc(plain, start, end)
        conn = get_conn()
        for row in ohlc_rows:
            # Convert date format from YYYY-MM-DD to YYYY-MM-DD for storage
            conn.execute(
                """INSERT OR IGNORE INTO ohlc
                   (symbol, date, open, high, low, close, volume, pct_chg)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    resolved,
                    row["date"],
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["volume"],
                    row.get("pct_chg", 0),
                ),
            )
        conn.execute(
            "UPDATE tickers SET last_ohlc_fetch = ? WHERE symbol = ?",
            (end, resolved),
        )
        conn.commit()

        # Fetch news
        news_items = fetch_news(plain)
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
                    art.get("content"),
                    art.get("published"),
                    art.get("url"),
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                (news_id, resolved),
            )

        conn.execute(
            "UPDATE tickers SET last_news_fetch = ? WHERE symbol = ?",
            (end, resolved),
        )
        conn.commit()
        conn.close()

        # Run alignment
        align_news_for_symbol(resolved)
    except Exception:
        logger.exception("Error fetching data for %s", resolved)
