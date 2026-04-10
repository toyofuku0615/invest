"""
バックテストエンジン
シグナルロジックの過去検証を行い、勝率・平均リターン・ドローダウンを計算する
"""
import json
import yaml
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, timedelta, datetime
from typing import Optional
import logging

from data.fetcher import get_fetcher
from models.sector_linkage import (
    get_sector_proximity,
    compute_historical_beta,
    get_expected_jp_change,
    get_lag_response,
    compute_confidence,
)
from models.geo_gap import compute_geo_gap_score

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
MASTER_PATH = BASE_DIR / "data" / "master.json"
CONFIG_PATH = BASE_DIR / "config.yaml"


def load_master():
    with open(MASTER_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_backtest(period_days: int = 180, hold_periods: list = None) -> dict:
    """
    過去period_days日間のシグナルと、その後の実績騰落率を計算し
    バックテスト結果を返す

    Returns: {
        "period_days": int,
        "total_signals": int,
        "results": [...],
        "statistics": {...},
    }
    """
    if hold_periods is None:
        hold_periods = [1, 3, 7]

    config = load_config()
    master = load_master()
    fetcher = get_fetcher(cache_ttl_minutes=5)

    impact_threshold = config["signal"]["impact_threshold"]
    min_lag = config["signal"]["min_lag_for_signal"]

    # 全JP銘柄の長期履歴を取得
    all_jp_data: dict[str, pd.DataFrame] = {}
    all_us_data: dict[str, pd.DataFrame] = {}

    for jp_stock in master["jp_stocks"]:
        hist = fetcher.get_price_history(jp_stock["ticker"], days=period_days + 30)
        if hist is not None and not hist.empty:
            all_jp_data[jp_stock["ticker"]] = hist

    for etf in master["us_etfs"]:
        hist = fetcher.get_price_history(etf["ticker"], days=period_days + 30)
        if hist is not None and not hist.empty:
            all_us_data[etf["ticker"]] = hist

    # バックテスト実行
    results = []
    end_date = date.today()
    start_date = end_date - timedelta(days=period_days)

    current_date = start_date
    while current_date <= end_date - timedelta(days=7):
        # その日の米国ETF変動率を計算
        day_us_signals = _get_us_signals_for_date(
            current_date, master, all_us_data, impact_threshold
        )

        if not day_us_signals:
            current_date += timedelta(days=1)
            continue

        # 翌営業日（日本市場）のデータで日本銘柄のシグナルを評価
        for jp_stock in master["jp_stocks"]:
            jp_ticker = jp_stock["ticker"]
            if jp_ticker not in all_jp_data:
                continue

            jp_hist = all_jp_data[jp_ticker]

            for us_sector, sector_info in day_us_signals.items():
                prox = get_sector_proximity(jp_stock, us_sector, sector_info["themes"])
                if prox == 0:
                    continue

                etf_ticker = sector_info["etf_ticker"]
                us_hist = all_us_data.get(etf_ticker)

                # シグナル発生日の翌日の日本銘柄変動率
                jp_change_next = _get_price_change_at_date(jp_hist, current_date + timedelta(days=1))
                if jp_change_next is None:
                    continue

                us_sector_change = sector_info["change_pct"]
                beta = jp_stock.get(f"beta_to_{etf_ticker.lower()}", 1.0)
                expected_change = get_expected_jp_change(us_sector_change, beta, prox)
                lag = get_lag_response(jp_change_next, expected_change)

                if lag < min_lag:
                    continue

                leading_impact = sector_info["leading_impact"]
                confidence = compute_confidence(40, beta, prox)
                total_score = leading_impact * prox * lag * confidence

                if total_score < config["signal"]["min_total_score"]:
                    continue

                # 保有期間別の実績騰落率を計算
                hold_returns = {}
                for hp in hold_periods:
                    ret = _get_return_over_period(jp_hist, current_date + timedelta(days=1), hp)
                    hold_returns[f"return_{hp}d"] = ret

                result_entry = {
                    "date": str(current_date),
                    "jp_ticker": jp_ticker,
                    "jp_name": jp_stock["name"],
                    "jp_code": jp_stock["code"],
                    "sector": us_sector,
                    "us_sector_change": round(us_sector_change, 3),
                    "direction": sector_info["direction"],
                    "total_score": round(total_score, 4),
                    "scores": {
                        "leading_market_impact": round(leading_impact, 3),
                        "sector_proximity": round(prox, 3),
                        "lag_response": round(lag, 3),
                        "confidence": round(confidence, 3),
                    },
                    **hold_returns,
                }
                results.append(result_entry)

        current_date += timedelta(days=1)

    # 統計計算
    statistics = _compute_statistics(results, hold_periods)

    return {
        "period_days": period_days,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "total_signals": len(results),
        "results": results[:200],  # 最大200件
        "statistics": statistics,
        "generated_at": datetime.now().isoformat(),
    }


def _get_us_signals_for_date(target_date, master, all_us_data, threshold) -> dict:
    """指定日の米国ETFシグナルを取得"""
    signals = {}
    for etf in master["us_etfs"]:
        ticker = etf["ticker"]
        if ticker not in all_us_data:
            continue
        change = _get_price_change_at_date(all_us_data[ticker], target_date)
        if change is None:
            continue
        geo = compute_geo_gap_score(change, 0, threshold)
        if geo["has_signal"]:
            signals[etf["sector"]] = {
                "etf_ticker": ticker,
                "change_pct": change,
                "themes": etf["themes"],
                "leading_impact": geo["leading_market_impact"],
                "direction": geo["direction"],
            }
    return signals


def _get_price_change_at_date(hist: pd.DataFrame, target_date) -> Optional[float]:
    """指定日の変動率を計算"""
    try:
        date_index = hist.index.date
        mask = date_index == target_date
        if not any(mask):
            return None
        idx = list(date_index).index(target_date)
        if idx == 0:
            return None
        close = hist["Close"].iloc[idx]
        prev_close = hist["Close"].iloc[idx - 1]
        if prev_close == 0:
            return None
        return float((close - prev_close) / prev_close * 100)
    except Exception:
        return None


def _get_return_over_period(
    hist: pd.DataFrame,
    start_date,
    hold_days: int
) -> Optional[float]:
    """保有期間後のリターン（%）を計算"""
    try:
        date_index = list(hist.index.date)
        if start_date not in date_index:
            return None
        start_idx = date_index.index(start_date)
        end_idx = start_idx + hold_days
        if end_idx >= len(hist):
            return None
        start_price = float(hist["Close"].iloc[start_idx])
        end_price = float(hist["Close"].iloc[end_idx])
        if start_price == 0:
            return None
        return round((end_price - start_price) / start_price * 100, 3)
    except Exception:
        return None


def _compute_statistics(results: list, hold_periods: list) -> dict:
    """バックテスト統計を計算"""
    if not results:
        return {"message": "シグナルが見つかりませんでした"}

    stats = {"total_signals": len(results)}

    for hp in hold_periods:
        key = f"return_{hp}d"
        returns = [r[key] for r in results if r.get(key) is not None]
        if not returns:
            continue

        returns_arr = np.array(returns)
        wins = sum(1 for r in returns if r > 0)

        # 最大ドローダウン
        cum = np.cumsum(returns_arr)
        rolling_max = np.maximum.accumulate(cum)
        drawdown = cum - rolling_max
        max_dd = float(np.min(drawdown)) if len(drawdown) > 0 else 0

        stats[f"hold_{hp}d"] = {
            "sample_count": len(returns),
            "win_rate": round(wins / len(returns) * 100, 1),
            "avg_return": round(float(np.mean(returns_arr)), 3),
            "median_return": round(float(np.median(returns_arr)), 3),
            "std_return": round(float(np.std(returns_arr)), 3),
            "max_return": round(float(np.max(returns_arr)), 3),
            "min_return": round(float(np.min(returns_arr)), 3),
            "max_drawdown": round(max_dd, 3),
        }

    return stats
