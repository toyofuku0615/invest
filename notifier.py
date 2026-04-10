"""
デスクトップ通知およびスマホ通知 (ntfy.sh) モジュール
"""
import requests
import logging
from plyer import notification
import platform

logger = logging.getLogger(__name__)

NTFY_TOPIC = "geogap_invest_app_kazut"  # スマホ通知用のトピック名（必要に応じて変更）

def send_desktop_notification(title: str, message: str):
    """Windowsのデスクトップ通知を表示し、音を鳴らす"""
    try:
        if platform.system() == "Windows":
            import winsound
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        
        notification.notify(
            title=title,
            message=message,
            app_name="GeoGap Investment App",
            timeout=10  # 10秒表示
        )
        logger.info(f"Desktop notification sent: {title}")
    except Exception as e:
        logger.error(f"Failed to send desktop notification: {e}")

def send_smartphone_notification(title: str, message: str, tags: str = "chart_with_upwards_trend"):
    """ntfy.sh 経由でスマホへプッシュ通知を送信する"""
    try:
        response = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={
                "Title": title.encode('utf-8'),
                "Tags": tags,
                "Priority": "high"
            }
        )
        response.raise_for_status()
        logger.info(f"Smartphone notification sent: {title} via topic: {NTFY_TOPIC}")
    except Exception as e:
        logger.error(f"Failed to send smartphone notification: {e}")

def send_expo_notification(title: str, message: str, data: dict = None):
    """Expo Push API経由でプッシュ通知を送信する"""
    try:
        from api.tokens import get_registered_tokens
        tokens = get_registered_tokens()
        if not tokens:
            return
            
        url = 'https://exp.host/--/api/v2/push/send'
        headers = {
            'Accept': 'application/json',
            'Accept-encoding': 'gzip, deflate',
            'Content-Type': 'application/json',
        }
        
        payload = []
        for token in tokens:
            payload.append({
                'to': token,
                'title': title,
                'body': message,
                'data': data or {},
                'sound': 'default'
            })
            
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Expo notification sent to {len(payload)} devices")
    except Exception as e:
        logger.error(f"Failed to send Expo notification: {e}")

def notify_all(title: str, message: str, tags: str = "bell"):
    """デスクトップとスマホ両方に通知を送る"""
    send_desktop_notification(title, message)
    send_smartphone_notification(title, message, tags)
    send_expo_notification(title, message)
