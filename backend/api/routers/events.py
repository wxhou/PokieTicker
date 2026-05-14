"""Events API — calendar view of A-share events with stock linking."""

from fastapi import APIRouter, Query
from backend.database import get_conn

router = APIRouter()


@router.get("")
def list_events(
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    """List events in a date range, grouped by date."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT e.id, e.title, e.description, e.event_date, e.category, e.impact, e.source
           FROM events e
           WHERE e.event_date BETWEEN ? AND ?
           ORDER BY e.event_date DESC, e.created_at DESC""",
        (start, end),
    ).fetchall()

    # Attach linked stocks for each event
    events = []
    for r in rows:
        stocks = conn.execute(
            """SELECT es.symbol, t.name
               FROM event_stock es
               LEFT JOIN tickers t ON es.symbol = t.symbol
               WHERE es.event_id = ?""",
            (r["id"],),
        ).fetchall()
        events.append({
            "id": r["id"],
            "title": r["title"],
            "description": r["description"],
            "event_date": r["event_date"],
            "category": r["category"],
            "impact": r["impact"],
            "source": r["source"],
            "stocks": [{"symbol": s["symbol"], "name": s["name"] or s["symbol"]} for s in stocks],
        })

    conn.close()
    return events


@router.get("/{event_id}")
def get_event(event_id: str):
    """Get event detail with linked stocks and their latest attribution."""
    conn = get_conn()
    r = conn.execute(
        """SELECT id, title, description, event_date, category, impact, source
           FROM events WHERE id = ?""",
        (event_id,),
    ).fetchone()

    if not r:
        conn.close()
        return {"error": "Event not found"}

    # Get linked stocks with latest layer1 attribution
    stocks = conn.execute(
        """SELECT es.symbol, t.name
           FROM event_stock es
           LEFT JOIN tickers t ON es.symbol = t.symbol
           WHERE es.event_id = ?""",
        (event_id,),
    ).fetchall()

    stock_list = []
    for s in stocks:
        news_id = event_id.replace("evt_", "")
        # Try direct news_id match first (works for notice/news events)
        l1 = conn.execute(
            """SELECT l1.sentiment, l1.reason_growth, l1.reason_decrease, l1.key_discussion
               FROM layer1_results l1
               WHERE l1.news_id = ? AND l1.symbol = ?""",
            (news_id, s["symbol"]),
        ).fetchone()

        # Fallback: latest layer1 for this stock on the event date
        if not l1:
            l1 = conn.execute(
                """SELECT l1.sentiment, l1.reason_growth, l1.reason_decrease, l1.key_discussion
                   FROM layer1_results l1
                   JOIN news_aligned na ON l1.news_id = na.news_id AND l1.symbol = na.symbol
                   WHERE l1.symbol = ? AND na.trade_date = ?
                   ORDER BY l1.rowid DESC LIMIT 1""",
                (s["symbol"], r["event_date"]),
            ).fetchone()

        stock_info = {
            "symbol": s["symbol"],
            "name": s["name"] or s["symbol"],
            "sentiment": None,
            "reason": None,
        }
        if l1:
            stock_info["sentiment"] = l1["sentiment"]
            if l1["sentiment"] == "positive":
                stock_info["reason"] = (l1["reason_growth"] or "")[:50]
            elif l1["sentiment"] == "negative":
                stock_info["reason"] = (l1["reason_decrease"] or "")[:50]
            elif l1["key_discussion"]:
                stock_info["reason"] = (l1["key_discussion"] or "")[:50]
        stock_list.append(stock_info)

    conn.close()
    return {
        "id": r["id"],
        "title": r["title"],
        "description": r["description"],
        "event_date": r["event_date"],
        "category": r["category"],
        "impact": r["impact"],
        "source": r["source"],
        "stocks": stock_list,
    }
