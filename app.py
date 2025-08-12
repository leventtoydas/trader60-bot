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
def analyze_list(title: str, symbols: list):
    import numpy as np
    msg = f"📊 {title}\n"
    for sym in symbols:
        sym = sym.strip()
        if not sym: 
            continue
        try:
            df = yf.download(sym, period="200d", interval="1d", progress=False)
            if df is None or df.empty or len(df) < 60:
                msg += f"{sym}: veri yok/az\n"
                continue

            # İndikatörler
            close = df["Close"].astype(float)
            sma20 = close.rolling(20).mean()
            sma50 = close.rolling(50).mean()
            sma200 = close.rolling(200).mean()

            # RSI(14)
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / (loss.replace(0, np.nan))
            rsi14 = 100 - (100 / (1 + rs))

            # Son değerleri güvenli şekilde skalar al
            c  = float(close.iloc[-1])
            s20 = float(sma20.iloc[-1]) if not np.isnan(sma20.iloc[-1]) else None
            s50 = float(sma50.iloc[-1]) if not np.isnan(sma50.iloc[-1]) else None
            s200 = float(sma200.iloc[-1]) if not np.isnan(sma200.iloc[-1]) else None
            rsi = float(rsi14.iloc[-1]) if not np.isnan(rsi14.iloc[-1]) else None

            # Günlük değişim
            chg = 0.0
            if len(close) > 1 and close.iloc[-2] != 0:
                chg = (c / float(close.iloc[-2]) - 1.0) * 100.0

            signal = trend_signal_from_vals(c, s20, s50, s200, rsi)
            msg += f"{sym}: {c:.2f} ({chg:+.2f}%) — {signal}\n"

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
