"""
スマホアプリのプッシュトークン登録API
POST /api/tokens
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# トークン保存先 (dataディレクトリ内)
TOKENS_FILE = Path(__file__).parent.parent / "data" / "expo_tokens.json"

class TokenRegister(BaseModel):
    token: str

@router.post("/tokens")
def register_token(req: TokenRegister):
    """
    Expoアプリから送信されたプッシュトークンを保存する
    """
    tokens = set()
    if TOKENS_FILE.exists():
        try:
            with open(TOKENS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                tokens = set(data.get("tokens", []))
        except Exception as e:
            logger.warning(f"Could not read tokens file: {e}")
            
    tokens.add(req.token)
    
    try:
        TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump({"tokens": list(tokens)}, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "message": "Token registered successfully"}
    except Exception as e:
        logger.error(f"Failed to save token: {e}")
        raise HTTPException(status_code=500, detail="Failed to save token")

def get_registered_tokens() -> list[str]:
    """
    保存されているすべてのプッシュトークンを取得する（schedulerから利用）
    """
    if TOKENS_FILE.exists():
        try:
            with open(TOKENS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("tokens", [])
        except Exception:
            return []
    return []
