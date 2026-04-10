"""
FastAPI メインアプリケーション
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from api.signals import router as signals_router
from api.market import router as market_router
from api.backtest import router as backtest_router
from api.settings import router as settings_router
from api.tokens import router as tokens_router
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="GeoGap投資シグナルAPI",
    description="地理的ギャップ×業種連動性に基づく投資意思決定支援API（中川慧教授コンセプト準拠）",
    version="1.0.0",
)

# CORS設定（フロントエンドからのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from scheduler import start_scheduler

@app.on_event("startup")
def on_startup():
    logging.info("Starting up GeoGap Investment API...")
    try:
        start_scheduler()
    except Exception as e:
        logging.error(f"Failed to start scheduler: {e}")

app.include_router(signals_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(tokens_router, prefix="/api")

@app.get("/")
def root():
    return {
        "app": "GeoGap投資シグナルAPI",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
