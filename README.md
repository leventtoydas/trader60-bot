# TRADER60 — Final Robust Build
No pandas_ta. Strong NaN/None guards. Wider history windows. Python 3.10 pinned.

Deploy:
1) Upload all files to GitHub (overwrite previous).
2) Railway: Deployments → Rebuild without cache.
3) Variables: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (and optional SYMBOLS, TIMEFRAMES, DEBOUNCE_MIN).
4) Check logs for start message and Telegram boot note.
