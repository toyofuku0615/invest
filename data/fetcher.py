"""
データ取得モジュール
yfinanceを抽象化したインターフェースで将来的に差替可能な構成
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """
    株価データ取得の抽象クラス
    将来的にRefinitiv/Bloomberg APIへの差替を容易にするため
    すべてのデータ取得はこのクラス経由で行う
    """

    def __init__(self, cache_ttl_minutes: int = 60):
        self._cache: dict = {}
        self._cache_ttl = timedelta(minutes=cache_ttl_minutes)

    def _cache_key(self, ticker: str, period: str) -> str:
        return f"{ticker}_{period}"

    def _is_cache_valid(self, key: str) -> bool:
        if key not in self._cache:
            return False
        cached_time, _ = self._cache[key]
        return datetime.now() - cached_time < self._cache_ttl

    def get_price_history(
        self,
        ticker: str,
        days: int = 60,
        interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        指定銘柄の過去N日間の株価履歴を取得
        Returns: OHLCV DataFrameまたNone（取得失敗時）
        """
        period_str = f"{days}d"
        cache_key = self._cache_key(ticker, period_str)

        if self._is_cache_valid(cache_key):
            _, data = self._cache[cache_key]
            return data

        try:
            t = yf.Ticker(ticker)
            hist = t.history(period=period_str, interval=interval)
            if hist.empty:
                logger.warning(f"Empty data for {ticker}")
                return None
            self._cache[cache_key] = (datetime.now(), hist)
            return hist
        except Exception as e:
            logger.error(f"Failed to fetch {ticker}: {e}")
            return None

    def get_latest_price(self, ticker: str) -> Optional[dict]:
        """
        最新の株価情報を取得（終値・始値・当日変動率）
        """
        hist = self.get_price_history(ticker, days=5)
        if hist is None or hist.empty:
            return None

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) >= 2 else None

        change_pct = 0.0
        if prev is not None and prev["Close"] != 0:
            change_pct = (latest["Close"] - prev["Close"]) / prev["Close"] * 100

        return {
            "ticker": ticker,
            "date": str(hist.index[-1].date()),
            "close": float(latest["Close"]),
            "open": float(latest["Open"]),
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "volume": int(latest["Volume"]),
            "change_pct": round(change_pct, 3),
        }

    def get_multiple_latest(self, tickers: list[str]) -> dict[str, dict]:
        """
        複数銘柄の最新価格を一括取得
        """
        results = {}
        for ticker in tickers:
            data = self.get_latest_price(ticker)
            if data:
                results[ticker] = data
        return results

    def get_price_changes(self, tickers: list[str]) -> dict[str, float]:
        """
        複数銘柄の直近変動率（%）を返す辞書
        """
        data = self.get_multiple_latest(tickers)
        return {ticker: info["change_pct"] for ticker, info in data.items()}

    def get_historical_returns(self, ticker: str, days: int = 60) -> Optional[pd.Series]:
        """
        日次リターン系列を取得（beta計算用）
        """
        hist = self.get_price_history(ticker, days=days)
        if hist is None or hist.empty:
            return None
        returns = hist["Close"].pct_change().dropna()
        return returns

    def clear_cache(self):
        self._cache.clear()


# シングルトンインスタンス
_fetcher_instance = None


def get_fetcher(cache_ttl_minutes: int = 60) -> MarketDataFetcher:
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = MarketDataFetcher(cache_ttl_minutes)
    return _fetcher_instance
