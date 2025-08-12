import os, datetime, requests
from fastapi import FastAPI

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def log(s: str):
    print(s, flush=True)

def tg_send(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("[ERROR] Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
        return {"ok": False, "error": "missing_env"}
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=12)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    log(f"[TG DEBUG] sendMessage status: {r.status_code}")
    log(f"[TG DEBUG] sendMessage body: {body}")
    return {"ok": (r.status_code == 200 and body.get('ok') is True), "status": r.status_code, "body": body}

@app.on_event("startup")
async def on_startup():
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    env_status = f"TOKEN={'OK' if TELEGRAM_TOKEN else 'MISSING'}, CHAT_ID={TELEGRAM_CHAT_ID or 'MISSING'}"
    tg_send(f"✅ TRADER60 — Deploy OK\n⏱ {ts}\n🔧 Env: {env_status}")

@app.get('/')
def root():
    return {"ok": True, "message": "TRADER60 alive", "notify": "/notify", "health": "/health"}

@app.get('/notify')
def notify():
    return tg_send("🔔 TRADER60 — Manuel test bildirimi")

@app.get('/health')
def health():
    return {"ok": True, "has_token": bool(TELEGRAM_TOKEN), "chat_id": TELEGRAM_CHAT_ID}
