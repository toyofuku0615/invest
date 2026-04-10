"""
設定APIルート
GET/POST /api/settings - 設定取得・更新
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import yaml
from pathlib import Path

router = APIRouter()
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class SettingsUpdate(BaseModel):
    impact_threshold: float | None = None
    min_lag_for_signal: float | None = None
    min_total_score: float | None = None
    max_signals: int | None = None


@router.get("/settings")
def get_settings():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings")
def update_settings(update: SettingsUpdate):
    """
    シグナル閾値等の設定を更新する
    """
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if update.impact_threshold is not None:
            config["signal"]["impact_threshold"] = update.impact_threshold
        if update.min_lag_for_signal is not None:
            config["signal"]["min_lag_for_signal"] = update.min_lag_for_signal
        if update.min_total_score is not None:
            config["signal"]["min_total_score"] = update.min_total_score
        if update.max_signals is not None:
            config["signal"]["max_signals"] = update.max_signals

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)

        return {"status": "updated", "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
