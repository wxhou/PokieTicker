import logging

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from backend.database import get_conn
from backend.akshare.client import fetch_ohlc, fetch_news_bulk
from backend.pipeline.layer0 import run_layer0
from backend.pipeline.layer1 import run_layer1
from backend.pipeline.alignment import align_news_for_symbol

import json

router = APIRouter()


class FetchRequest(BaseModel):
    symbol: str
    start: Optional[str] = None
    end: Optional[str] = None


class ProcessRequest(BaseModel):
    symbol: str
    batch_size: int = 1000


@router.post("/fetch")
def trigger_fetch(req: FetchRequest, background_tasks: BackgroundTasks):
    """Trigger A-share data fetch for a symbol."""
    symbol = req.symbol.upper()
    today = datetime.now(timezone.utc).date()
    start = req.start or (today - timedelta(days=2 * 366)).isoformat()
    end = req.end or today.isoformat()

    background_tasks.add_task(_do_fetch, symbol, start, end)
    return {"symbol": symbol, "status": "fetch_started", "start": start, "end": end}


def _do_fetch(symbol: str, start: str, end: str):
    """Background fetch of OHLC + news data for A-shares."""
    try:
        # OHLC
        ohlc_rows = fetch_ohlc(symbol, start, end)
        conn = get_conn()
        for row in ohlc_rows:
            conn.execute(
                """INSERT OR IGNORE INTO ohlc
                   (symbol, date, open, high, low, close, volume, vwap, transactions, pct_chg)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol, row["date"], row["open"], row["high"], row["low"],
                 row["close"], row["volume"], row.get("vwap"), row.get("transactions"),
                 row.get("pct_chg")),
            )
        conn.execute(
            "UPDATE tickers SET last_ohlc_fetch = ? WHERE symbol = ?",
            (end, symbol),
        )
        conn.commit()

        # News (A-share: use fetch_news_bulk)
        articles = fetch_news_bulk(symbol)
        from backend.akshare.client import resolve_code
        ts_code = resolve_code(symbol)
        for art in articles:
            news_id = art.get("news_id")
            if not news_id:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO news_raw
                   (id, title, description, publisher, author,
                    published_utc, article_url, amp_url, tickers_json, insights_json, source_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (news_id, art.get("title"), art.get("content"),
                 art.get("source"), None, art.get("published"),
                 art.get("url"), None,
                 json.dumps([ts_code]),
                 None, art.get("source_type", "news")),
            )
            conn.execute(
                "INSERT OR IGNORE INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                (news_id, ts_code),
            )

        conn.execute(
            "UPDATE tickers SET last_news_fetch = ? WHERE symbol = ?",
            (end, symbol),
        )
        conn.commit()
        conn.close()

        # Run alignment
        align_news_for_symbol(symbol)
    except Exception:
        logger.exception("Fetch error for %s", symbol)


@router.post("/process")
def trigger_process(req: ProcessRequest):
    """Run Layer 0 filter, then submit Layer 1 batch for remaining articles."""
    symbol = req.symbol.upper()

    # Step 1: Alignment
    align_result = align_news_for_symbol(symbol)

    # Step 2: Layer 0
    l0_stats = run_layer0(symbol)

    # Step 3: Run Layer 1 (50 articles per API call)
    l1_stats = run_layer1(symbol, max_articles=req.batch_size)

    return {
        "symbol": symbol,
        "alignment": align_result,
        "layer0": l0_stats,
        "layer1": l1_stats,
    }


@router.get("/batch/{batch_id}")
def get_batch_status(batch_id: str):
    """Batch API is no longer supported. Returns deprecated status."""
    return {
        "batch_id": batch_id,
        "status": "deprecated",
        "message": "Batch API was removed. Use /process instead which runs synchronous analysis.",
    }


@router.post("/reprocess/{symbol}")
def reprocess_symbol(symbol: str):
    """Clear L0 results and re-run pipeline for a symbol (after L0 rule changes)."""
    symbol = symbol.upper()
    conn = get_conn()
    deleted_l0 = conn.execute(
        "DELETE FROM layer0_results WHERE symbol = ?", (symbol,)
    ).rowcount
    deleted_l1 = conn.execute(
        "DELETE FROM layer1_results WHERE symbol = ?", (symbol,)
    ).rowcount
    conn.commit()
    conn.close()

    # Re-run the full pipeline
    align_result = align_news_for_symbol(symbol)
    l0_stats = run_layer0(symbol)
    l1_stats = run_layer1(symbol, max_articles=10000)

    return {
        "symbol": symbol,
        "cleared": {"layer0": deleted_l0, "layer1": deleted_l1},
        "alignment": align_result,
        "layer0": l0_stats,
        "layer1": l1_stats,
    }


@router.post("/reprocess-all")
def reprocess_all():
    """Clear L0 results and re-run pipeline for all symbols with news data."""
    conn = get_conn()
    symbols = [r[0] for r in conn.execute(
        "SELECT DISTINCT symbol FROM news_aligned"
    ).fetchall()]
    conn.close()

    results = []
    for symbol in symbols:
        try:
            result = reprocess_symbol(symbol)
            results.append(result)
        except Exception as e:
            logger.error("Reprocess failed for %s: %s", symbol, e)
            results.append({"symbol": symbol, "error": str(e)})

    return {"processed": len(results), "results": results}
