import pandas as pd
import yfinance as yf
import requests
from fastapi import FastAPI

app = FastAPI()

# ----------------- Telegram Ayarları -----------------
TELEGRAM_TOKEN = "8294179459:AAFJROkKzuL4wnZQhTx0e62ib_QVDGtJw1o"
TELEGRAM_CHAT_ID = "7881664904"

# ----------------- İzlenecek Enstrümanlar -----------------
STOCKS = [
    # Altın / Gümüş
    "XAUUSD=X",   # Altın / USD
    "XAGUSD=X",   # Gümüş / USD

    # Ham Petrol / Doğalgaz
    "CL=F",       # Ham Petrol
    "NG=F",       # Doğalgaz

    # Endeksler
    "^NDX",       # Nasdaq 100
    "^GDAXI",     # DAX
    "^DJI",       # Dow Jones
    "^N225",      # Nikkei 225
    "^SSMI",      # Swiss Market Index 20
]

# ----------------- Yardımcı Fonksiyonlar -----------------
def last_scalar(v):
    if isinstance(v, (pd.Series, pd.DataFrame)):
        if v.empty:
            return None
        v = v.iloc[-1]
    if pd.isna(v):
        return None
    return v

def tg_send(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.ok
    except Exception as e:
        print(f"Telegram gönderim hatası: {e}")
        return False

def analyze_block(title, symbols):
    results = [f"📊 <b>{title}</b>"]
    for sym in symbols:
        df = yf.download(sym, period="5d", interval="1d", progress=False)
        if df.empty:
            results.append(f"{sym}: Veri yok")
            continue

        close = last_scalar(df["Close"])
        open_ = last_scalar(df["Open"])

        if close is None or open_ is None:
            results.append(f"{sym}: Eksik veri")
            continue

        change = (close - open_) / open_ * 100
        results.append(f"{sym}: {close:.2f} USD ({change:+.2f}%)")
    return "\n".join(results)

# ----------------- Çalışma Fonksiyonu -----------------
async def run_daily():
    msg = analyze_block("Emtia & Endeksler", STOCKS)
    tg_send(msg)

# ----------------- API Endpoint -----------------
@app.get("/run-now")
async def run_now():
    await run_daily()
    return {"status": "ok", "message": "Analiz Telegram'a gönderildi"}
