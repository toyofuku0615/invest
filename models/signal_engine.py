"""
シグナル生成エンジン
地理的ギャップ×業種連動性の中川慧教授コンセプトに基づく
注目銘柄候補を生成するコアロジック
"""
import json
import yaml
from pathlib import Path
from datetime import date, datetime
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
from models.geo_gap import compute_geo_gap_score, get_information_delay_factor
from explanation.generator import generate_explanation, generate_summary

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
MASTER_PATH = BASE_DIR / "data" / "master.json"
CONFIG_PATH = BASE_DIR / "config.yaml"


def load_master() -> dict:
    with open(MASTER_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_signals(target_date: Optional[str] = None) -> dict:
    """
    本日のシグナルを生成して返す

    Returns: {
        "date": "YYYY-MM-DD",
        "signals": [...],
        "market_summary": {...},
        "generated_at": "...",
    }
    """
    config = load_config()
    master = load_master()
    fetcher = get_fetcher(cache_ttl_minutes=config["data"]["cache_ttl_minutes"])

    today = target_date or str(date.today())
    signal_cfg = config["signal"]
    lookback = signal_cfg["lookback_days"]
    impact_threshold = signal_cfg["impact_threshold"]
    min_lag = signal_cfg["min_lag_for_signal"]
    min_score = signal_cfg["min_total_score"]

    # ── STEP 1: 先行市場（米国）セクターETFの変動率を取得 ──
    us_etfs = master["us_etfs"]
    us_etf_changes = {}
    for etf in us_etfs:
        data = fetcher.get_latest_price(etf["ticker"])
        if data:
            us_etf_changes[etf["ticker"]] = {
                "change_pct": data["change_pct"],
                "sector": etf["sector"],
                "themes": etf["themes"],
                "name": etf["name"],
                "close": data["close"],
            }

    # 主要指数も取得
    us_indices = {}
    for idx in master["us_indices"][:2]:  # S&P500, NASDAQ
        d = fetcher.get_latest_price(idx["ticker"])
        if d:
            us_indices[idx["name"]] = d["change_pct"]

    # ── STEP 2: 有意に動いたセクターを特定 ──
    active_sectors = {}
    for etf_ticker, info in us_etf_changes.items():
        geo = compute_geo_gap_score(info["change_pct"], 0, impact_threshold)
        if geo["has_signal"]:
            active_sectors[info["sector"]] = {
                "etf_ticker": etf_ticker,
                "etf_name": info["name"],
                "change_pct": info["change_pct"],
                "themes": info["themes"],
                "leading_impact": geo["leading_market_impact"],
                "direction": geo["direction"],
            }

    delay_factor = get_information_delay_factor()

    # ── STEP 3 & 4: 日本銘柄の未反応度を計算してシグナル生成 ──
    signals = []

    for jp_stock in master["jp_stocks"]:
        jp_ticker = jp_stock["ticker"]
        jp_sector = jp_stock["sector"]
        jp_themes = jp_stock["themes"]

        # 関連する有意な米国セクターを探す
        best_sector_info = None
        best_sector_proximity = 0.0

        for us_sector, sector_info in active_sectors.items():
            prox = get_sector_proximity(jp_stock, us_sector, sector_info["themes"])
            if prox > best_sector_proximity:
                best_sector_proximity = prox
                best_sector_info = sector_info
                best_sector_info = {**sector_info, "sector": us_sector}

        if best_sector_info is None or best_sector_proximity == 0:
            continue  # 関連する有意な米国セクターがない

        us_sector_change = best_sector_info["change_pct"]
        direction = best_sector_info["direction"]

        # 日本銘柄の現在の変動率を取得
        jp_data = fetcher.get_latest_price(jp_ticker)
        if jp_data is None:
            logger.warning(f"No data for {jp_ticker}, skip")
            continue

        jp_change = jp_data["change_pct"]

        # historical betaを計算
        etf_ticker = best_sector_info["etf_ticker"]
        jp_returns = fetcher.get_historical_returns(jp_ticker, days=lookback)
        us_returns = fetcher.get_historical_returns(etf_ticker, days=lookback)

        # マスターデータのデフォルトbetaを参照
        beta_key = f"beta_to_{etf_ticker.lower()}"
        default_beta = jp_stock.get(beta_key, 1.0)

        if jp_returns is not None and us_returns is not None:
            beta = compute_historical_beta(jp_returns, us_returns)
        else:
            beta = default_beta

        # 期待変動率と未反応度を計算
        expected_change = get_expected_jp_change(us_sector_change, beta, best_sector_proximity)
        lag_response = get_lag_response(jp_change, expected_change)

        if lag_response < min_lag:
            continue  # 未反応度が低すぎる

        # 信頼度計算
        beta_days = len(jp_returns) if jp_returns is not None else 0
        confidence = compute_confidence(beta_days, beta, best_sector_proximity)
        confidence *= delay_factor  # 時間帯補正

        # 総合スコア（乗算式）
        leading_impact = best_sector_info["leading_impact"]
        total_score = leading_impact * best_sector_proximity * lag_response * confidence
        total_score = round(total_score, 4)

        if total_score < min_score:
            continue

        signal = {
            "signal_id": f"{today}-{jp_stock['code']}",
            "date": today,
            "jp_ticker": jp_ticker,
            "jp_code": jp_stock["code"],
            "jp_name": jp_stock["name"],
            "jp_close": jp_data["close"],
            "jp_change": jp_change,
            "target_sell_price": round(jp_data["close"] * (1 + max(0, lag_response)), 0) if jp_data["close"] else None,
            "sector": jp_sector,
            "related_us_tickers": jp_stock.get("related_us_tickers", []),
            "leading_etf": etf_ticker,
            "us_sector_change": us_sector_change,
            "direction": direction,
            "expected_jp_change": round(expected_change, 3),
            "beta": beta,
            "scores": {
                "leading_market_impact": round(leading_impact, 3),
                "sector_proximity": round(best_sector_proximity, 3),
                "lag_response": round(lag_response, 3),
                "confidence": round(confidence, 3),
                "total": total_score,
            },
            "risks": jp_stock.get("risks", []),
            "description": jp_stock.get("description", ""),
        }

        # 説明文を生成
        signal["explanation"] = generate_explanation(signal)
        signal["summary"] = generate_summary(signal)

        signals.append(signal)

    # スコア順にソート
    signals.sort(key=lambda x: x["scores"]["total"], reverse=True)
    signals = signals[:signal_cfg["max_signals"]]

    # 先行市場サマリーを作成
    market_summary = {
        "us_indices": us_indices,
        "active_sectors": {
            sector: {
                "name_ja": _sector_name_ja(sector),
                "change_pct": info["change_pct"],
                "direction": info["direction"],
                "etf": info["etf_ticker"],
            }
            for sector, info in active_sectors.items()
        },
        "all_sector_changes": {
            info["sector"]: info["change_pct"]
            for info in us_etf_changes.values()
        },
    }

    return {
        "date": today,
        "signals": signals,
        "market_summary": market_summary,
        "signal_count": len(signals),
        "generated_at": datetime.now().isoformat(),
    }


def _sector_name_ja(sector: str) -> str:
    names = {
        "semiconductor": "半導体",
        "banking": "銀行・金融",
        "energy": "エネルギー",
        "auto": "自動車",
        "tech": "テクノロジー",
    }
    return names.get(sector, sector)
