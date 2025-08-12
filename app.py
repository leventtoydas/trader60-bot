import os, datetime, requests
from fastapi import FastAPI

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def log(s): 
    print(s, flush=True)

def tg_send(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("[ERROR] Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=12)
    log(f"[TG DEBUG] sendMessage status: {r.status_code}")
    log(f"[TG DEBUG] sendMessage body: {r.text}")
    return r.status_code == 200 and r.json().get("ok", False)

@app.on_event("startup")
async def startup_event():
    # Deploy/Restart bildirimi
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    msg = f"✅ TRADER60 — Deploy OK\n⏱ {ts}\n🔧 Env: TOKEN={'OK' if TELEGRAM_TOKEN else 'MISSING'}, CHAT_ID={TELEGRAM_CHAT_ID or 'MISSING'}"
    tg_send(msg)

@app.get("/notify")
def notify():
    # Manuel test için: .../notify aç → Telegram’a test düşer
    return {"ok": tg_send("🔔 TRADER60 — Manuel test bildirimi")}
    
@app.get("/health")
def health():
    return {"ok": True, "has_token": bool(TELEGRAM_TOKEN), "chat_id": TELEGRAM_CHAT_ID}
