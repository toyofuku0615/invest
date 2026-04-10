"""
シグナルAPIルート
GET /api/signals - 本日のシグナル一覧
GET /api/signals/{ticker} - 銘柄個別シグナル詳細
"""
from fastapi import APIRouter, HTTPException, Query
from models.signal_engine import generate_signals

router = APIRouter()


@router.get("/signals")
def get_signals(date: str = Query(None, description="対象日 YYYY-MM-DD (省略時は本日)")):
    """
    本日（または指定日）の注目銘柄シグナル一覧を返す
    スコア順にソート済み
    """
    try:
        result = generate_signals(target_date=date)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/{ticker}")
def get_signal_detail(ticker: str):
    """
    特定銘柄のシグナル詳細を返す
    """
    try:
        result = generate_signals()
        signals = result.get("signals", [])
        # コードまたはティッカーで検索
        for s in signals:
            if s["jp_ticker"] == ticker or s["jp_code"] == ticker:
                return s
        raise HTTPException(status_code=404, detail=f"{ticker} のシグナルが見つかりません")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
