import os
import requests
from fastapi import FastAPI

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def _log(s: str):
    print(s, flush=True)

@app.on_event("startup")
async def startup_event():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        _log("[ERROR] Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID env vars.")
        return
    try:
        _log(f"[BOOT] CHAT_ID: {TELEGRAM_CHAT_ID}")
        _log("[BOOT] TOKEN tail: ********")
        r1 = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe", timeout=10)
        ok1 = r1.json().get("ok", False) if r1.status_code == 200 else False
        _log(f"[TG DEBUG] getMe status: {r1.status_code} ve ok: {str(ok1).lower()}")
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": "✅ TRADER60 DEBUG — başlangıç testi (Markdown OFF)."
        }
        r2 = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=10)
        ok2 = r2.json().get("ok", False) if r2.status_code == 200 else False
        _log(f"[TG DEBUG] status: {r2.status_code} ve ok: {str(ok2).lower()} (sendMessage)")
    except Exception as e:
        _log(f"[ERROR] Startup error: {e}")

@app.get("/health")
def health():
    return {"ok": True, "chat_id": TELEGRAM_CHAT_ID}
