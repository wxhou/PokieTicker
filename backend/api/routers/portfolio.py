"""Portfolio management API — protected by JWT authentication."""

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from backend.database import get_conn
from backend.api.routers.auth import get_current_user
from backend.ai.minimax_tools import MiniMaxTools
from backend.akshare.client import stock_info_a_code_name

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class CreatePortfolioRequest(BaseModel):
    name: str


class AddHoldingRequest(BaseModel):
    portfolio_id: int
    stock_code: str


class BatchImportRequest(BaseModel):
    stock_codes: list[str]


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


@router.post("/screenshot", name="screenshot-import")
async def screenshot_import(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> dict:
    """Import holdings by uploading a screenshot from A-share apps.

    Accepts jpg/png/webp images. The image is sent to MiniMax VL for parsing,
    then stocks are enriched via AKShare if needed.
    """
    # Validate file type
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=422,
            detail="仅支持 jpg、png、webp 格式",
        )

    # Read file bytes
    image_bytes = await file.read()

    # Check file size (10MB limit)
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="图片不能超过10MB",
        )

    # Parse screenshot via MiniMax VL
    try:
        mm = MiniMaxTools()
        holdings = mm.parse_screenshot(image_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail="AI 识别服务暂时不可用，请稍后重试",
        )

    if not holdings:
        return {
            "holdings": [],
            "unidentified": 0,
            "message": "未能识别到股票，请尝试更清晰的截图",
        }

    # Separate known vs unknown stock codes
    known_holdings = [h for h in holdings if h.get("in_database")]
    unknown_holdings = [h for h in holdings if not h.get("in_database")]

    # Enrich unknown stocks via AKShare in parallel
    if unknown_holdings:
        async def enrich_one(h: dict) -> dict:
            info = stock_info_a_code_name(h["stock_code"])
            if info:
                conn = get_conn()
                conn.execute(
                    "INSERT OR IGNORE INTO tickers (symbol, name) VALUES (?, ?)",
                    (h["stock_code"], info.get("name", "")),
                )
                conn.commit()
                conn.close()
                h["in_database"] = True
            else:
                h["in_database"] = False
            return h

        enriched = await asyncio.gather(*[enrich_one(h) for h in unknown_holdings])
        known_holdings.extend([h for h in enriched if h.get("in_database")])

    # Get or create default portfolio
    conn = get_conn()
    portfolio = conn.execute(
        "SELECT id FROM portfolios WHERE user_id = ? AND name = '我的持仓' ORDER BY created_at DESC LIMIT 1",
        (user["id"],),
    ).fetchone()
    if not portfolio:
        row = conn.execute(
            "INSERT INTO portfolios (user_id, name) VALUES (?, ?) RETURNING id",
            (user["id"], "我的持仓"),
        ).fetchone()
        portfolio_id = row["id"]
        conn.commit()
    else:
        portfolio_id = portfolio["id"]
    conn.close()

    # Batch insert (INSERT OR IGNORE — duplicates skipped)
    conn = get_conn()
    for h in known_holdings:
        conn.execute(
            "INSERT OR IGNORE INTO portfolio_holdings (portfolio_id, stock_code, source) VALUES (?, ?, ?)",
            (portfolio_id, h["stock_code"], "screenshot"),
        )
    conn.commit()
    conn.close()

    return {
        "holdings": known_holdings,
        "unidentified": len(holdings) - len(known_holdings),
        "message": f"识别成功",
        "portfolio_id": portfolio_id,
    }


@router.post("/import", name="batch-import")
def batch_import(
    req: BatchImportRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Import selected stocks to user's default portfolio.

    Uses INSERT OR IGNORE for idempotent batch insert.
    Returns imported count, skipped duplicates, and invalid codes.
    """
    if not req.stock_codes:
        raise HTTPException(status_code=400, detail="至少选择一个股票")

    conn = get_conn()

    # Get or create default portfolio
    portfolio = conn.execute(
        "SELECT id FROM portfolios WHERE user_id = ? AND name = '我的持仓' "
        "ORDER BY created_at DESC LIMIT 1",
        (user["id"],),
    ).fetchone()
    if not portfolio:
        row = conn.execute(
            "INSERT INTO portfolios (user_id, name) VALUES (?, ?) RETURNING id",
            (user["id"], "我的持仓"),
        ).fetchone()
        portfolio_id = row["id"]
        conn.commit()
    else:
        portfolio_id = portfolio["id"]

    # Check remaining slots
    current = conn.execute(
        "SELECT COUNT(*) as c FROM portfolio_holdings WHERE portfolio_id = ?",
        (portfolio_id,),
    ).fetchone()["c"]
    remaining = MAX_HOLDINGS_PER_PORTFOLIO - current

    if remaining <= 0:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"组合已满（{MAX_HOLDINGS_PER_PORTFOLIO}只），请先移除部分持仓",
        )

    # Batch insert with INSERT OR IGNORE
    imported = 0
    skipped = 0
    not_found = []

    for code in req.stock_codes:
        code_upper = code.strip().upper()
        if not code_upper:
            continue

        # Check if stock exists in tickers
        ticker = conn.execute(
            "SELECT symbol FROM tickers WHERE symbol = ?",
            (code_upper,),
        ).fetchone()

        if not ticker:
            not_found.append(code)
            continue

        if imported >= remaining:
            skipped += 1
            continue

        conn.execute(
            "INSERT OR IGNORE INTO portfolio_holdings "
            "(portfolio_id, stock_code, source) VALUES (?, ?, ?)",
            (portfolio_id, code_upper, "screenshot"),
        )
        # Check if actually inserted (changes() returns rows affected by last INSERT)
        if conn.execute("SELECT changes()").fetchone()[0] == 1:
            imported += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()

    return {
        "imported": imported,
        "skipped": skipped,
        "not_found": not_found,
        "message": "导入成功" if not_found == [] and skipped == 0 else "部分导入",
    }


def get_portfolio_holdings(portfolio_id: int) -> list:
    """Get all holdings for a portfolio, enriched with latest price data."""
    conn = get_conn()
    holdings = conn.execute(
        "SELECT id, stock_code, added_at, source FROM portfolio_holdings WHERE portfolio_id = ? ORDER BY added_at",
        (portfolio_id,),
    ).fetchall()
    conn.close()

    result = []
    for h in holdings:
        item: dict[str, Any] = {
            "id": h["id"],
            "stock_code": h["stock_code"],
            "added_at": h["added_at"],
            "source": h["source"] or "manual",
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
