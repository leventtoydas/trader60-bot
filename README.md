# TRADER60 — Fixed build (Python 3.10, pinned deps, string fix)

Steps:
1) Upload files to GitHub repo (overwrite existing).
2) Railway → Settings → Deployments → Clear Cache.
3) Variables: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (and optional SYMBOLS, TIMEFRAMES, DEBOUNCE_MIN).
4) Redeploy. Check Logs for start message.
