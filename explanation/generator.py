"""
説明文テンプレート生成モジュール
各シグナルに対して日本語の説明文を生成する
将来的にLLMによる自然言語生成に換装可能な設計
"""
from datetime import date
from typing import Optional


SECTOR_NAMES = {
    "semiconductor": "半導体",
    "banking": "銀行・金融",
    "energy": "エネルギー",
    "auto": "自動車",
    "tech": "テクノロジー",
}

DIRECTION_TEXT = {
    "up": "上昇",
    "down": "下落",
    "neutral": "横ばい",
}


def generate_explanation(signal: dict) -> str:
    """
    シグナルデータから日本語の説明文を生成

    Parameters:
        signal: シグナル辞書（signal_engine.pyの出力形式）

    Returns: 日本語説明文（マークダウン非使用のプレーンテキスト）
    """
    jp_name = signal.get("jp_name", "")
    jp_ticker = signal.get("jp_ticker", "")
    sector = signal.get("sector", "")
    sector_ja = SECTOR_NAMES.get(sector, sector)

    scores = signal.get("scores", {})
    leading_impact = scores.get("leading_market_impact", 0)
    sector_proximity = scores.get("sector_proximity", 0)
    lag_response = scores.get("lag_response", 0)
    confidence = scores.get("confidence", 0)

    us_change = signal.get("us_sector_change", 0)
    jp_change = signal.get("jp_change", 0)
    related_us = signal.get("related_us_tickers", [])
    related_etf = signal.get("leading_etf", "")
    direction = signal.get("direction", "up")
    dir_text = DIRECTION_TEXT.get(direction, "動き")

    today = signal.get("date", str(date.today()))

    # 関連米国銘柄・ETFのテキスト
    related_us_text = "・".join(related_us[:3]) if related_us else "米国関連銘柄"
    if related_etf:
        related_us_text += f"（{related_etf}）"

    # 未反応度の説明
    if lag_response >= 0.7:
        lag_text = f"本日{today}時点では{jp_change:+.1f}%と、まだ十分に織り込まれていません（未反応度:{lag_response:.0%}）"
    elif lag_response >= 0.4:
        lag_text = f"本日{today}時点では{jp_change:+.1f}%と、一部のみ反応しています（未反応度:{lag_response:.0%}）"
    else:
        lag_text = f"本日{today}時点では{jp_change:+.1f}%と、ある程度反応が見られます（未反応度:{lag_response:.0%}）"

    # 業種連動の根拠
    if sector_proximity >= 0.9:
        linkage_text = f"米国{sector_ja}セクターとの業種連動性は非常に高く（近接度:{sector_proximity:.2f}）"
    elif sector_proximity >= 0.7:
        linkage_text = f"米国{sector_ja}セクターとテーマ面での関連性があり（近接度:{sector_proximity:.2f}）"
    else:
        linkage_text = f"米国{sector_ja}セクターとの間接的な関連があり（近接度:{sector_proximity:.2f}）"

    # リスク情報
    risks = signal.get("risks", [])
    risks_text = "、".join(risks) if risks else "為替変動リスク、個別材料リスク"

    explanation = (
        f"昨夜の米国市場で{sector_ja}関連が大きく{dir_text}しました（{us_change:+.1f}%）。\n"
        f"{jp_name}（{jp_ticker}）は{related_us_text}と業種的に近い銘柄です。{linkage_text}、"
        f"{lag_text}。\n"
        f"そのため、米国市場の動きが日本市場で遅れて反映される候補として注目されています。\n\n"
        f"⚠️ 注意すべきリスク：{risks_text}\n"
        f"※ 本分析は公開情報に基づく補助情報であり、投資助言ではありません。最終判断はご自身でお願いします。"
    )
    return explanation


def generate_summary(signal: dict) -> str:
    """
    通知向けの短い要約文を生成（1〜2文）
    """
    jp_name = signal.get("jp_name", "")
    sector = signal.get("sector", "")
    sector_ja = SECTOR_NAMES.get(sector, sector)
    us_change = signal.get("us_sector_change", 0)
    direction = signal.get("direction", "up")
    dir_text = DIRECTION_TEXT.get(direction, "動き")
    total_score = signal.get("scores", {}).get("total", 0)

    return (
        f"米国{sector_ja}セクターが{us_change:+.1f}%{dir_text}。"
        f"{jp_name}への波及が遅れている可能性（スコア:{total_score:.2f}）。"
    )
