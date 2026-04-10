"""
地理的ギャップモデル
米国市場→日本市場への情報伝播・時間差スコアを計算する
"""
from datetime import datetime
import pytz
import logging

logger = logging.getLogger(__name__)

US_TZ = pytz.timezone("America/New_York")
JP_TZ = pytz.timezone("Asia/Tokyo")


def get_us_market_status() -> dict:
    """
    現在の米国市場の状態を返す
    Returns: {"status": "open"|"closed"|"pre"|"after", "session_jst": str}
    """
    now_us = datetime.now(US_TZ)
    now_jp = datetime.now(JP_TZ)
    hour_us = now_us.hour + now_us.minute / 60

    if 4.0 <= hour_us < 9.5:
        status = "pre"
    elif 9.5 <= hour_us < 16.0:
        status = "open"
    elif 16.0 <= hour_us < 20.0:
        status = "after"
    else:
        status = "closed"

    return {
        "status": status,
        "us_time": now_us.strftime("%H:%M"),
        "jp_time": now_jp.strftime("%H:%M"),
        "is_jp_trading_hours": 9 <= now_jp.hour < 15 and now_jp.weekday() < 5,
    }


def compute_geo_gap_score(
    us_change_pct: float,
    jp_change_pct: float,
    impact_threshold: float = 1.5
) -> dict:
    """
    地理的ギャップスコアを計算
    米国市場で有意な動きがあり、日本市場がまだ反応していない場合に高スコア

    Parameters:
        us_change_pct: 米国先行市場の変動率（%）
        jp_change_pct: 日本後続市場の変動率（%）
        impact_threshold: 有意とみなす変動閾値（%）

    Returns: {
        "leading_market_impact": 0〜1,
        "has_signal": bool,
        "direction": "up"|"down"|"neutral"
    }
    """
    abs_us = abs(us_change_pct)

    # 米国での有意な動きがない場合はシグナルなし
    if abs_us < impact_threshold:
        return {
            "leading_market_impact": 0.0,
            "has_signal": False,
            "direction": "neutral",
            "us_change_pct": us_change_pct,
        }

    # 先行市場インパクトスコア（変動率が大きいほど高スコア、最大5%で1.0）
    impact_score = min(abs_us / 5.0, 1.0)

    # 方向判定
    direction = "up" if us_change_pct > 0 else "down"

    return {
        "leading_market_impact": round(impact_score, 3),
        "has_signal": True,
        "direction": direction,
        "us_change_pct": us_change_pct,
    }


def get_information_delay_factor() -> float:
    """
    情報伝播の遅延係数を返す
    日本市場開場直後（9:00-9:30）は最高スコア（情報反映が最も期待される時間帯）
    時間が経つほど係数は下がる

    Returns: 0.5〜1.0
    """
    now_jp = datetime.now(JP_TZ)
    hour_jp = now_jp.hour + now_jp.minute / 60

    if 9.0 <= hour_jp <= 9.5:
        return 1.0  # 寄り付き直後：最も情報伝播効果が高い
    elif 9.5 <= hour_jp <= 11.5:
        return 0.85  # 午前中
    elif 12.5 <= hour_jp <= 14.0:
        return 0.7   # 午後前半
    elif 14.0 <= hour_jp <= 15.0:
        return 0.6   # 引け前
    else:
        return 0.5   # 市場外時間
