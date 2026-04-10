"""
定期実行スケジューラ 
毎朝のシグナル計算・通知および、ザラ場中の価格監視・アラーム機能
"""
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import logging
from datetime import datetime
from models import signal_engine as engine
from data.fetcher import get_fetcher
from notifier import notify_all

logger = logging.getLogger(__name__)

# JST (日本時間)
jst = pytz.timezone('Asia/Tokyo')

# ザラ場監視用の状態保持（その日にアラームを鳴らした銘柄を二度鳴らさないように）
alarmed_tickers_today = set()
current_date_str = ""

def morning_job():
    """毎朝8:50等に走るジョブ。シグナルを生成して通知する。"""
    global alarmed_tickers_today, current_date_str
    logger.info("Running morning job...")
    
    # 状態リセット
    today_str = datetime.now(jst).strftime("%Y-%m-%d")
    if current_date_str != today_str:
        alarmed_tickers_today.clear()
        current_date_str = today_str
        
    try:
        res = engine.generate_signals("latest")
        count = len(res["signals"])
        
        if count > 0:
            top_ticker = res["signals"][0]["jp_name"]
            msg = f"本日の注目候補は {count} 件です。\nトップ候補: {top_ticker}\nダッシュボードを確認してください。"
            notify_all("📈 GeoGapシグナル検知", msg, "chart_with_upwards_trend")
        else:
            notify_all("💤 今日のGeoGapシグナル", "米国市場での有意な変動が検出されませんでした。", "zzz")
            
    except Exception as e:
        logger.error(f"Morning job error: {e}")

def intraday_monitor_job():
    """ザラ場（9:00〜15:00）の間に10分おきに走って利確アラームをチェックする"""
    now = datetime.now(jst)
    
    # ザラ場判定 (9:00〜15:00, 11:30-12:30の昼休み除く)
    time_num = now.hour * 100 + now.minute
    if time_num < 900 or time_num > 1500:
        return # 場外
    if 1130 < time_num < 1230:
        return # 昼休み中
        
    # 平日判定
    if now.weekday() >= 5: # 土・日
        return
        
    logger.info("Running intraday monitor job...")
    
    try:
        # 最新のシグナルを取得
        res = engine.generate_signals("latest")
        if not res["signals"]:
            return
            
        for s in res["signals"]:
            ticker = s["jp_code"]
            if ticker in alarmed_tickers_today:
                continue # 今日すでにアラーム済
                
            target_price = s.get("target_sell_price")
            if not target_price:
                continue
                
            # 現在の株価を取得（fetcherモジュールに依存）
            current_data = get_fetcher().get_latest_price(f"{ticker}.T")
            current = current_data["close"] if current_data else None
            if current and current >= target_price:
                # 目標到達
                msg = f"{s['jp_name']} ({ticker}) が目標価格 {target_price:.0f}円 に到達しました！\n現在値: {current:.0f}円\n利益確定を検討してください。"
                notify_all(f"🚨 利確アラーム: {s['jp_name']}", msg, "tada")
                alarmed_tickers_today.add(ticker)
                
    except Exception as e:
        logger.error(f"Intraday monitor job error: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=jst)
    
    # 朝の通知 (毎朝 8:50) - 月〜金
    scheduler.add_job(morning_job, 'cron', day_of_week='mon-fri', hour=8, minute=50)
    
    # ザラ場監視 (月〜金、9:00〜15:00の間、10分おき)
    # 簡略化のため10分おきのcronを使用し、ジョブ内部のロジックで時間外を弾く
    scheduler.add_job(intraday_monitor_job, 'interval', minutes=10)
    
    scheduler.start()
    logger.info("Scheduler started successfully. (Morning job: 8:50 / Intraday monitor: every 10 mins)")
    
    # デバッグ用に起動時に一度テスト監視を走らせることも可能
    # intraday_monitor_job()
