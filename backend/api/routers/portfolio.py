"""Portfolio management API — protected by JWT authentication."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from backend.database import get_conn
from backend.api.routers.auth import get_current_user

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class CreatePortfolioRequest(BaseModel):
    name: str


class AddHoldingRequest(BaseModel):
    portfolio_id: int
    stock_code: str


class PortfolioResponse(BaseModel):
    id: int
    name: str
    created_at: str
    holdings: list

MAX_HOLDINGS_PER_PORTFOLIO = 10


@router.get("")
def list_portfolios(user: dict = Depends(get_current_user)) -> list:
    """List all portfolios for the authenticated user."""
    conn = get_conn()
    portfolios = conn.execute(
        "SELECT id, name, created_at FROM portfolios WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],),
    ).fetchall()
    conn.close()

    result = []
    for p in portfolios:
        holdings = get_portfolio_holdings(p["id"])
        result.append({
            "id": p["id"],
            "name": p["name"],
            "created_at": p["created_at"],
            "holdings": holdings,
        })
    return result


@router.post("", status_code=201)
def create_portfolio(
    req: CreatePortfolioRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Create a new portfolio."""
    if not req.name or len(req.name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Portfolio name is required")
    if len(req.name) > 100:
        raise HTTPException(status_code=400, detail="Portfolio name too long")

    conn = get_conn()
    row = conn.execute(
        "INSERT INTO portfolios (user_id, name) VALUES (?, ?) RETURNING id, name, created_at",
        (user["id"], req.name.strip()),
    ).fetchone()
    conn.commit()
    conn.close()

    return {
        "id": row["id"],
        "name": row["name"],
        "created_at": row["created_at"],
        "holdings": [],
    }


@router.delete("/{portfolio_id}")
def delete_portfolio(
    portfolio_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    """Delete a portfolio and all its holdings."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM portfolios WHERE id = ? AND user_id = ?",
        (portfolio_id, user["id"]),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Portfolio not found")

    conn.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
    conn.commit()
    conn.close()
    return {"id": portfolio_id, "deleted": True}


@router.post("/holdings")
def add_holding(
    req: AddHoldingRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Add a stock to a portfolio (max 10 holdings per portfolio)."""
    stock_code = req.stock_code.strip().upper()
    if not stock_code:
        raise HTTPException(status_code=400, detail="Stock code is required")
    if len(stock_code) > 10:
        raise HTTPException(status_code=400, detail="Invalid stock code")

    conn = get_conn()

    # Verify ownership
    portfolio = conn.execute(
        "SELECT id FROM portfolios WHERE id = ? AND user_id = ?",
        (req.portfolio_id, user["id"]),
    ).fetchone()
    if not portfolio:
        conn.close()
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Check holding count
    count = conn.execute(
        "SELECT COUNT(*) as c FROM portfolio_holdings WHERE portfolio_id = ?",
        (req.portfolio_id,),
    ).fetchone()["c"]
    if count >= MAX_HOLDINGS_PER_PORTFOLIO:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Portfolio already has {MAX_HOLDINGS_PER_PORTFOLIO} holdings. Remove one before adding more.",
        )

    try:
        conn.execute(
            "INSERT INTO portfolio_holdings (portfolio_id, stock_code) VALUES (?, ?)",
            (req.portfolio_id, stock_code),
        )
        conn.commit()
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail="Stock already in portfolio")
        raise HTTPException(status_code=500, detail=str(e))

    conn.close()
    return {
        "portfolio_id": req.portfolio_id,
        "stock_code": stock_code,
        "added": True,
    }


@router.delete("/holdings/{holding_id}")
def remove_holding(
    holding_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    """Remove a stock from a portfolio."""
    conn = get_conn()

    # Verify ownership through portfolio
    row = conn.execute(
        """SELECT ph.id FROM portfolio_holdings ph
           JOIN portfolios p ON ph.portfolio_id = p.id
           WHERE ph.id = ? AND p.user_id = ?""",
        (holding_id, user["id"]),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Holding not found")

    conn.execute("DELETE FROM portfolio_holdings WHERE id = ?", (holding_id,))
    conn.commit()
    conn.close()
    return {"id": holding_id, "removed": True}


def get_portfolio_holdings(portfolio_id: int) -> list:
    """Get all holdings for a portfolio, enriched with latest price data."""
    conn = get_conn()
    holdings = conn.execute(
        "SELECT id, stock_code, added_at FROM portfolio_holdings WHERE portfolio_id = ? ORDER BY added_at",
        (portfolio_id,),
    ).fetchall()
    conn.close()

    result = []
    for h in holdings:
        item: dict[str, Any] = {
            "id": h["id"],
            "stock_code": h["stock_code"],
            "added_at": h["added_at"],
        }
        # Try to get latest price
        try:
            from backend.database import get_conn as _conn
            c = _conn()
            latest = c.execute(
                "SELECT close, pct_chg FROM ohlc WHERE symbol = ? ORDER BY date DESC LIMIT 1",
                (h["stock_code"],),
            ).fetchone()
            c.close()
            if latest:
                item["close"] = latest["close"]
                item["pct_chg"] = latest["pct_chg"]
        except Exception:
            pass
        result.append(item)
    return result
