"""
先行市場（米国）データAPIルート
GET /api/market/leading - 米国市場の最新状況
"""
from fastapi import APIRouter, HTTPException
from data.fetcher import get_fetcher
import json
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).parent.parent


@router.get("/market/leading")
def get_leading_market():
    """
    米国先行市場の最新データを返す
    （主要指数・セクターETF変動率）
    """
    try:
        with open(BASE_DIR / "data" / "master.json", encoding="utf-8") as f:
            master = json.load(f)

        fetcher = get_fetcher()

        # 主要指数
        indices_data = {}
        for idx in master["us_indices"]:
            d = fetcher.get_latest_price(idx["ticker"])
            if d:
                indices_data[idx["name"]] = {
                    "ticker": idx["ticker"],
                    "change_pct": d["change_pct"],
                    "close": d["close"],
                    "date": d["date"],
                }

        # セクターETF
        etf_data = {}
        for etf in master["us_etfs"]:
            d = fetcher.get_latest_price(etf["ticker"])
            if d:
                etf_data[etf["sector"]] = {
                    "ticker": etf["ticker"],
                    "name": etf["name"],
                    "change_pct": d["change_pct"],
                    "close": d["close"],
                    "date": d["date"],
                }

        return {
            "indices": indices_data,
            "sectors": etf_data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
