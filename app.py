import os, datetime, asyncio
from zoneinfo import ZoneInfo

import requests
import yfinance as yf
import pandas as pd
import numpy as np
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

app = FastAPI()

# --- ENV ---
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
TZ_NAME = os.getenv("TIMEZONE", "Europe/Istanbul")
RUN_HOUR = int(os.getenv("RUN_HOUR", "9"))
RUN_MINUTE = int(os.getenv("RUN_MINUTE", "30"))

# Defaults (Yahoo symbols)
DEFAULT_STOCKS = os.getenv("STOCKS_CSV", "THYAO.IS,TOASO.IS,GUBRF.IS,ENKAI.IS,TUPRS.IS,ULKER.IS,KCHOL.IS,ASELS.IS")
DEFAULT_INDICES = os.getenv("INDICES_CSV", "^XU100,^BIST30,^GSPC,^NDX,^DJI")
DEFAULT_COMMODS = os.getenv("COMMODS_CSV", "XAUUSD=X,EURUSD=X,USDTRY=X,BZ=F,CL=F,BTC-USD")

def log(s: str):
    print(s, flush=True)

def tg_send(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("[ERROR] Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text[:3900]}, timeout=20)
    try:
        ok = r.json().get("ok", False)
    except Exception:
        ok = False
    log(f"[TG] status={r.status_code} ok={ok}")
    if not ok:
        log(f"[TG] body={r.text}")
    return ok

def indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]
    df["SMA8"] = close.rolling(8).mean()
    df["SMA20"] = close.rolling(20).mean()
    df["SMA50"] = close.rolling(50).mean()
    df["SMA200"] = close.rolling(200).mean()
    # RSI(14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss.replace(0, np.nan))
    df["RSI14"] = 100 - (100 / (1 + rs))
    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACDsig"] = df["MACD"].ewm(span=9, adjust=False).mean()
    return df

def fetch_ticker(ticker: str, period="200d", interval="1d"):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
        if df is None or df.empty:
            return None
        return indicators(df)
    except Exception as e:
        log(f"[ERR] fetch {ticker}: {e}")
        return None

def trend_signal(row):
    sigs = []
    if row["Close"] > row["SMA50"] > row["SMA200"]:
        sigs.append("Uptrend")
    elif row["Close"] < row["SMA50"] < row["SMA200"]:
        sigs.append("Downtrend")
    # Crossovers
    if row["SMA8"] > row["SMA20"]:
        sigs.append("SMA8>20")
    else:
        sigs.append("SMA8<20")
    # RSI zones
    rsi = row.get("RSI14", np.nan)
    if pd.notna(rsi):
        if rsi >= 70: sigs.append("RSI↑70")
        elif rsi <= 30: sigs.append("RSI↓30")
    # MACD
    if row["MACD"] > row["MACDsig"]:
        sigs.append("MACD>Sig")
    else:
        sigs.append("MACD<Sig")
    return ", ".join(sigs)

def analyze_list(name: str, tickers_csv: str):
    lines = [f"*{name}*"]
    for t in [x.strip() for x in tickers_csv.split(",") if x.strip()]:
        df = fetch_ticker(t)
        if df is None or df.empty:
            lines.append(f"- {t}: veri yok")
            continue
        last = df.iloc[-1]
        chg = (last["Close"] / df["Close"].iloc[-2] - 1.0) * 100 if len(df) > 1 else 0.0
        sig = trend_signal(last)
        lines.append(f"- {t}: {last['Close']:.2f} ({chg:+.2f}%) | {sig}")
    return "\n".join(lines)

async def run_daily():
    ts = datetime.datetime.now(ZoneInfo(TZ_NAME)).strftime("%Y-%m-%d %H:%M")
    header = f"📈 TRADER60 — Günlük Analiz ({ts} {TZ_NAME})"
    body1 = analyze_list("Hisseler", DEFAULT_STOCKS)
    body2 = analyze_list("Endeksler", DEFAULT_INDICES)
    body3 = analyze_list("Emtia/FX/Kripto", DEFAULT_COMMODS)
    text = "\n\n".join([header, body1, body2, body3])
    tg_send(text)

@app.on_event("startup")
async def startup_event():
    # Schedule daily job 09:30 Europe/Istanbul (vars)
    scheduler = AsyncIOScheduler(timezone=TZ_NAME)
    trigger = CronTrigger(hour=RUN_HOUR, minute=RUN_MINUTE)
    scheduler.add_job(run_daily, trigger, id="daily")
    scheduler.start()
    # Send deploy ping
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    tg_send(f"✅ TRADER60 — Worker aktif (cron {RUN_HOUR:02d}:{RUN_MINUTE:02d} {TZ_NAME})\n⏱ {ts}")

@app.get("/run-now")
async def run_now():
    await run_daily()
    return {"ok": True}

@app.get("/health")
def health():
    return {"ok": True, "tz": TZ_NAME, "hour": RUN_HOUR, "minute": RUN_MINUTE}
