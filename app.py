import os
import pandas as pd
import yfinance as yf
import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI
import requests

# ==== ENV AYARLARI ====
TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TZ_NAME = os.getenv("TIMEZONE", "Europe/Istanbul")
RUN_HOUR = int(os.getenv("RUN_HOUR", 9))
RUN_MINUTE = int(os.getenv("RUN_MINUTE", 30))

DEFAULT_STOCKS = os.getenv("STOCKS_CSV", "THYAO.IS,TOASO.IS,GUBRF.IS,ENKAI.IS,TUPRS.IS,ULKER.IS,KCHOL.IS,ASELS.IS").split(",")
DEFAULT_INDICES = os.getenv("INDICES_CSV", "^XU100,^BIST30,^GSPC,^NDX,^DJI").split(",")
DEFAULT_COMMODS = os.getenv("COMMODS_CSV", "XAUUSD=X,EURUSD=X,USDTRY=X,BZ=F,CL=F,BTC-USD").split(",")

app = FastAPI()


# ==== TELEGRAM ====
def tg_send(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}
        r = requests.post(url, json=payload, timeout=10)
        print(f"[TG] status={r.status_code} ok={r.json().get('ok')}")
    except Exception as e:
        print(f"[TG ERROR] {e}")


# ==== ANALİZ ====
def trend_signal(df: pd.DataFrame):
    if df.empty:
        return "Veri yok"
    last = df.iloc[-1]
    close = last["Close"]
    sma50 = last["SMA50"]
    sma200 = last["SMA200"]

    try:
        if pd.notna(close) and pd.notna(sma50) and pd.notna(sma200):
            if close > sma50 > sma200:
                return "📈 Yükseliş trendi"
            elif close < sma50 < sma200:
                return "📉 Düşüş trendi"
            else:
                return "➖ Kararsız"
        else:
            return "❓ Veri eksik"
    except Exception as e:
        return f"[ERR] {e}"


def analyze_list(title: str, symbols: list):
    msg = f"📊 {title}\n"
    for sym in symbols:
        try:
            df = yf.download(sym, period="6mo", interval="1d", progress=False)
            df["SMA50"] = df["Close"].rolling(50).mean()
            df["SMA200"] = df["Close"].rolling(200).mean()
            sig = trend_signal(df)
            msg += f"{sym}: {sig}\n"
        except Exception as e:
            msg += f"{sym}: [ERR] {e}\n"
    return msg


# ==== GÜNLÜK ÇALIŞTIRMA ====
async def run_daily():
    ts = datetime.datetime.now(ZoneInfo(TZ_NAME)).strftime("%Y-%m-%d %H:%M")
    tg_send(f"📈 TRADER60 — Günlük Analiz ({ts} {TZ_NAME})")

    tg_send(analyze_list("Hisseler", DEFAULT_STOCKS))
    tg_send(analyze_list("Endeksler", DEFAULT_INDICES))
    tg_send(analyze_list("Emtia/FX/Kripto", DEFAULT_COMMODS))

    tg_send("✅ TRADER60 — Günlük Analiz bitti.")


# ==== ENDPOINTS ====
@app.get("/health")
def health():
    return {"ok": True, "tz": TZ_NAME, "hour": RUN_HOUR, "minute": RUN_MINUTE}


@app.get("/notify")
def notify():
    tg_send("🔔 TRADER60 — Manuel test bildirimi")
    return {"ok": True}


@app.get("/run-now")
async def run_now():
    await run_daily()
    return {"ok": True}


# ==== OTOMATİK ÇALIŞTIRMA ====
import asyncio

async def scheduler():
    while True:
        now = datetime.datetime.now(ZoneInfo(TZ_NAME))
        if now.hour == RUN_HOUR and now.minute == RUN_MINUTE:
            await run_daily()
            await asyncio.sleep(60)
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    tg_send("✅ TRADER60 — Worker aktif...")
    asyncio.create_task(scheduler())
