"""
業種連動性モデル
米国銘柄・セクターETFと日本銘柄の連動度を計算する
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

MASTER_PATH = Path(__file__).parent.parent / "data" / "master.json"


def load_master() -> dict:
    with open(MASTER_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_sector_proximity(jp_stock: dict, us_sector: str, us_themes: list[str]) -> float:
    """
    日本銘柄と米国セクターの業種近接度を計算
    - 完全業種一致: 1.0
    - テーマ一致: 0.7
    - 類似関連: 0.5
    - 非一致: 0.0
    """
    jp_sector = jp_stock.get("sector", "")
    jp_themes = jp_stock.get("themes", [])

    # 完全業種一致
    if jp_sector == us_sector:
        return 1.0

    # テーマレベルの一致（AI・EV・半導体など）
    theme_overlap = set(jp_themes) & set(us_themes)
    if theme_overlap:
        # 重複テーマが多いほど高スコア
        overlap_ratio = len(theme_overlap) / max(len(jp_themes), len(us_themes), 1)
        return round(0.5 + overlap_ratio * 0.4, 3)  # 0.5〜0.9

    return 0.0


def compute_historical_beta(
    jp_returns: pd.Series,
    us_returns: pd.Series
) -> float:
    """
    日本銘柄のリターンと米国セクターETFのリターンの回帰係数（beta）を計算
    期間は両者の共通インデックスを使用
    """
    if jp_returns is None or us_returns is None:
        return 1.0  # デフォルト

    # 共通の日付インデックスで整合
    common_idx = jp_returns.index.intersection(us_returns.index)
    if len(common_idx) < 10:
        return 1.0  # データ不足時はデフォルト

    jp_r = jp_returns.loc[common_idx].values
    us_r = us_returns.loc[common_idx].values

    # 線形回帰: jp_r = alpha + beta * us_r
    try:
        cov = np.cov(us_r, jp_r)
        if cov[0, 0] == 0:
            return 1.0
        beta = cov[0, 1] / cov[0, 0]
        return round(float(beta), 3)
    except Exception:
        return 1.0


def get_expected_jp_change(
    us_sector_change: float,
    beta: float,
    sector_proximity: float
) -> float:
    """
    米国セクターの動きに対して期待される日本銘柄の変動率を推定
    """
    return us_sector_change * beta * sector_proximity


def get_lag_response(
    jp_actual_change: float,
    expected_change: float
) -> float:
    """
    未反応度（lag_response）を計算
    = 1 - (実際の変動 / 期待変動)
    値が大きいほど「まだ反応していない」＝シグナル強

    Returns: 0.0〜1.0 (負になる場合も0にクリップ)
    """
    if abs(expected_change) < 0.01:
        return 0.0  # 期待変動が小さすぎる場合はシグナルなし

    # 同方向か確認（逆方向なら既に行き過ぎ）
    if expected_change > 0 and jp_actual_change >= expected_change:
        return 0.0  # 既に十分以上反応済み
    if expected_change < 0 and jp_actual_change <= expected_change:
        return 0.0

    lag = 1 - (jp_actual_change / expected_change)
    return max(0.0, min(1.0, round(lag, 3)))


def compute_confidence(
    beta_days: int,
    beta_value: float,
    sector_proximity: float
) -> float:
    """
    信頼度を計算
    - beta計算に十分なデータがある
    - betaが合理的な範囲にある
    - 業種近接度が高い
    """
    # データ量ボーナス（60日以上あれば最高）
    data_score = min(beta_days / 60, 1.0)

    # betaの合理性（0.3〜3.0が合理的）
    beta_score = 1.0 if 0.3 <= abs(beta_value) <= 3.0 else 0.5

    # 業種近接度の信頼性寄与
    proximity_score = sector_proximity

    confidence = (data_score * 0.3 + beta_score * 0.3 + proximity_score * 0.4)
    return round(confidence, 3)
