"""Prediction API endpoints.

Note: Models were originally trained on US stocks (BABA, TSLA, AAPL, NVDA, GLD)
and have since been retrained on A-share data (28 tickers, 2026-04-26). Per-ticker
accuracy on A-share is at or below random for several tickers — treat all
predictions as experimental / not investment advice.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "models"


EXPERIMENTAL_WARNING = (
    "实验性功能：模型于2026-04-26用28只A股重训，"
    "准确率接近随机，结果仅供参考，不构成投资建议。"
)

EXPERIMENTAL_RESPONSE = {
    "experimental": True,
    "disclaimer": EXPERIMENTAL_WARNING,
}


@router.get("/{symbol}")
def get_prediction(symbol: str, horizon: str = Query("t1", pattern="^t[15]$")):
    """Get direction prediction for a symbol."""
    from backend.ml.model import predict

    result = predict(symbol.upper(), horizon)
    if "error" in result:
        return {**EXPERIMENTAL_RESPONSE, "available": False, "error": result["error"]}
    return {**EXPERIMENTAL_RESPONSE, "available": True, **result}


@router.get("/{symbol}/backtest")
def get_backtest(symbol: str, horizon: str = Query("t1", pattern="^t[15]$")):
    """Get backtest results for a symbol."""
    sym = symbol.upper()
    path = MODELS_DIR / f"{sym}_{horizon}_backtest.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No backtest for {sym}/{horizon}. Run training with --backtest.")
    return {**EXPERIMENTAL_RESPONSE, **json.loads(path.read_text())}


@router.get("/{symbol}/forecast")
def get_forecast(symbol: str, window: int = Query(7, ge=3, le=60), lang: str = Query("zh", pattern="^(zh|en)$")):
    """Generate forecast based on recent news window (7d or 30d)."""
    from backend.ml.inference import generate_forecast

    result = generate_forecast(symbol.upper(), window, lang=lang)
    if "error" in result:
        return {**EXPERIMENTAL_RESPONSE, "available": False, "error": result["error"]}
    return {**EXPERIMENTAL_RESPONSE, "available": True, **result}


@router.get("/{symbol}/similar-days")
def get_similar_days(symbol: str, date: str = Query(...), top_k: int = Query(10, ge=1, le=30)):
    """Find historically similar trading days based on ML features."""
    from backend.ml.similar import find_similar_days

    result = find_similar_days(symbol.upper(), date, top_k)
    if "error" in result:
        return {**EXPERIMENTAL_RESPONSE, "available": False, "error": result["error"]}
    return {**EXPERIMENTAL_RESPONSE, "available": True, **result}
