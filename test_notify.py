from notifier import notify_all

print("Sending test notification to desktop and smartphone...")
notify_all("テスト通知", "これはGeoGap投資アプリからのテストアラームです！🎯", "tada")
print("Done. Check desktop and smartphone (ntfy.sh app).")
