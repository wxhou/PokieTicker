from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging

from backend.database import init_db
from backend.api.routers import stocks, news, analysis, predict
from backend.api.routers import auth, portfolio, pipeline, events

logger = logging.getLogger(__name__)

app = FastAPI(title="涨讯 ZhangXun", version="2.0.0", description="A股事件驱动分析工具")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:7777",
        "http://127.0.0.1:7777",
        "https://pokieticker.pages.dev",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(stocks.router, tags=["stocks"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(predict.router, prefix="/api/predict", tags=["predict"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(portfolio.router, tags=["portfolio"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(events.router, prefix="/api/events", tags=["events"])


@app.on_event("startup")
async def startup():
    init_db()
    # Start background scheduler for news fetching
    try:
        from backend.scheduler import scheduler_main
        asyncio.create_task(scheduler_main())
        logger.info("Background scheduler started")
    except Exception:
        logger.exception("Failed to start background scheduler")


@app.get("/api/health")
def health():
    return {"status": "ok"}
