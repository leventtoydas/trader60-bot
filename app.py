import pandas as pd
import yfinance as yf
import requests
from fastapi import FastAPI

app = FastAPI()

# --- Telegram ---
TELEGRAM_TOKEN = "8294179459:AAFJROkKzuL4wnZQhTx0e62ib_QVDGtJw1o"
TELEGRAM_CHAT_ID = "7881664904"

# --- Enstrümanlar (futures kullandım: GC=F / SI=F) ---
STOCKS = [
    "GC=F",      # Gold Futures (Altın)
    "SI=F",      # Silver Futures (Gümüş)
    "CL=F",      # Ham Petrol
    "NG=F",      # Doğalgaz
    "^NDX",      # Nasdaq 100
    "^GDAXI",    # DAX
    "^DJI",      # Dow Jones
    "^N225",     # Nikkei 225
    "^SSMI",     # Swiss Market Index
]

DISPLAY = {
    "GC=F": "Altın (GC=F)",
    "SI=F": "Gümüş (SI=F)",
    "CL=F": "Ham Petrol (CL=F)",
    "NG=F": "Doğalgaz (NG=F)",
    "^NDX": "Nasdaq 100",
    "^GDAXI": "DAX",
    "^DJI": "Dow Jones",
    "^N225": "Nikkei 225",
    "^SSMI": "SMI (İsviçre)",
}

def last_scalar(v):
    if isinstance(v, (pd.Series, pd.DataFrame)):
        if v.empty:
            return None
        v = v.iloc[-1]
    if pd.isna(v):
        return None
    return v

def tg_send(text: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        r = requests.post(url, json=payload, timeout=10)
        return r.ok
    except Exception:
        return False

def analyze_block(title, symbols):
    lines = [f"📊 <b>{title}</b>"]
    for sym in symbols:
        try:
            df = yf.download(sym, period="5d", interval="1d", progress=False, auto_adjust=False)
        except Exception:
            lines.append(f"• {DISPLAY.get(sym, sym)}: Veri hatası")
            continue

        if df is None or df.empty:
            lines.append(f"• {DISPLAY.get(sym, sym)}: Veri yok")
            continue

        close = last_scalar(df["Close"])
        open_ = last_scalar(df["Open"])
        if close is None or open_ is None:
            lines.append(f"• {DISPLAY.get(sym, sym)}: Eksik veri")
            continue

        try:
            chg = (close - open_) / open_ * 100.0
            lines.append(f"• {DISPLAY.get(sym, sym)}: {close:.2f} ({chg:+.2f}%)")
        except Exception:
            lines.append(f"• {DISPLAY.get(sym, sym)}: {close}")
    return "\n".join(lines)

async def run_daily():
    msg = analyze_block("Emtia & Endeksler", STOCKS)
    tg_send(msg)

@app.get("/run-now")
async def run_now():
    try:
        await run_daily()
        return {"status": "ok", "message": "Analiz gönderildi"}
    except Exception as e:
        # 500 vermesin; hata olsa da JSON dönsün
        return {"status": "error", "message": f"Hata: {e}"}
