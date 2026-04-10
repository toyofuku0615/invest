"""
バックテストAPIルート
GET /api/backtest - バックテスト結果取得
"""
from fastapi import APIRouter, HTTPException, Query
from backtest.engine import run_backtest

router = APIRouter()


@router.get("/backtest")
def get_backtest(
    period_days: int = Query(180, description="バックテスト期間（日数）"),
):
    """
    指定期間のバックテスト結果を返す
    勝率・平均リターン・最大ドローダウンを含む
    """
    try:
        if period_days > 365:
            period_days = 365
        if period_days < 30:
            period_days = 30
        result = run_backtest(period_days=period_days)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
