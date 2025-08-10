#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRADER60 — Multi-asset, multi-timeframe Telegram signal bot
Indicators: Bollinger Bands (20,2), RSI(14), EMA20/EMA50, MACD(12,26,9)
Signals: 
 - Buy: close <= BB.lower AND RSI <= 30
 - Sell: close >= BB.upper AND RSI >= 70
Debounce: same (symbol, timeframe, side) not resent within DEBOUNCE_MIN minutes
Author: ChatGPT (for Levent)
"""

import os
import json
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import requests
import pandas_ta as ta
import yfinance as yf

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
import pytz
from dotenv import load_dotenv

# ---------- Load env (config.env if present) ----------
if os.path.exists("config.env"):
    load_dotenv("config.env")
else:
    load_dotenv()  # Load regular .env if provided

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Optional keys (not strictly required for yfinance)
TWELVEDATA_KEY = os.getenv("TWELVEDATA_KEY", "").strip()
FINNHUB_KEY = os.getenv("FINNHUB_KEY", "").strip()

# Debounce minutes
DEBOUNCE_MIN = int(os.getenv("DEBOUNCE_MIN", "60"))

# Timezone (Turkey)
TZ = pytz.timezone(os.getenv("APP_TIMEZONE", "Europe/Istanbul"))

# Symbols: You can edit this list
SYMBOLS = os.getenv("SYMBOLS", "").strip()
if not SYMBOLS:
    SYMBOLS = ",".join([
        # --- BIST (Yahoo Finance with .IS) ---
        "THYAO.IS","TOASO.IS","GUBRF.IS","ENKAI.IS","TUPRS.IS","ULKER.IS","KCHOL.IS","ASELS.IS",
        "XU100.IS",
        # --- FX & Metals ---
        "USDTRY=X","EURUSD=X","XAUUSD=X","XAGUSD=X",
        # --- Indices (Yahoo tickers) ---
        "^GSPC","^NDX","^IXIC","^GDAXI","^FTSE","^N225",
        # --- Commodities Futures ---
        "CL=F","BZ=F",
        # --- Crypto via Yahoo (from Binance) ---
        "BTC-USD","ETH-USD"
    ])
SYMBOLS = [s.strip() for s in SYMBOLS.split(",") if s.strip()]

# Timeframes
TIMEFRAMES = os.getenv("TIMEFRAMES", "5m,15m,30m,1h,4h").split(",")
TIMEFRAMES = [t.strip() for t in TIMEFRAMES if t.strip()]

# ------------- Helper: Telegram -------------
def tg_send(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("[WARN] TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing. Message not sent.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code != 200:
            print("[ERROR] Telegram send failed:", r.text)
    except Exception as e:
        print("[ERROR] Telegram exception:", e)

# ------------- Helper: State (debounce) -------------
STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(st):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[WARN] Could not save state:", e)

STATE = load_state()

def can_send(symbol, tf, side, now_dt):
    """Prevent duplicate signals within DEBOUNCE_MIN."""
    key = f"{symbol}|{tf}|{side}"
    last_ts = STATE.get(key)
    if last_ts is None:
        return True
    last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc).astimezone(TZ)
    return (now_dt - last_dt) >= timedelta(minutes=DEBOUNCE_MIN)

def touch_signal(symbol, tf, side, now_dt):
    key = f"{symbol}|{tf}|{side}"
    # store as UTC timestamp
    utc_ts = now_dt.astimezone(timezone.utc).timestamp()
    STATE[key] = utc_ts
    save_state(STATE)

# ------------- Data fetching -------------
def fetch_ohlc(symbol: str, tf: str) -> pd.DataFrame:
    """
    Use yfinance to fetch OHLCV.
    tf can be: 5m, 15m, 30m, 1h, 4h
    For 4h we resample 60m data.
    """
    tf_map = {
        "5m": ("5m", "7d"),
        "15m": ("15m", "30d"),
        "30m": ("30m", "60d"),
        "1h": ("60m", "60d"),
        "4h": ("60m", "60d"),  # fetch 60m then resample
    }
    if tf not in tf_map:
        raise ValueError(f"Unsupported timeframe: {tf}")
    interval, period = tf_map[tf]

    try:
        df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=False, threads=True)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns=str.lower)
        df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
        # For 4h, resample
        if tf == "4h":
            # resample to 4H
            df = df.resample("4H").agg({
                "open":"first","high":"max","low":"min","close":"last","volume":"sum"
            }).dropna()
        return df
    except Exception as e:
        print(f"[ERROR] yfinance fetch failed for {symbol} {tf}: {e}")
        return pd.DataFrame()

# ------------- Indicators & signals -------------
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # RSI (14)
    df["rsi"] = ta.rsi(df["close"], length=14)
    # Bollinger Bands (20, 2)
    bb = ta.bbands(df["close"], length=20, std=2.0)
    if bb is not None and not bb.empty:
        df["bb_lower"] = bb["BBL_20_2.0"]
        df["bb_mid"] = bb["BBM_20_2.0"]
        df["bb_upper"] = bb["BBU_20_2.0"]
    else:
        df["bb_lower"] = np.nan
        df["bb_mid"] = np.nan
        df["bb_upper"] = np.nan
    # EMA 20/50
    df["ema20"] = ta.ema(df["close"], length=20)
    df["ema50"] = ta.ema(df["close"], length=50)
    # MACD
    macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        df["macd"] = macd_df["MACD_12_26_9"]
        df["macd_signal"] = macd_df["MACDs_12_26_9"]
        df["macd_hist"] = macd_df["MACDh_12_26_9"]
    else:
        df["macd"] = df["macd_signal"] = df["macd_hist"] = np.nan
    return df

def signal_from_row(row) -> tuple:
    """
    Returns (side, reason, confidence) or (None, None, 0)
    side: 'BUY' or 'SELL'
    confidence: 1..3 (simple heuristic)
    """
    c = row["close"]
    rsi = row["rsi"]
    lb = row["bb_lower"]
    ub = row["bb_upper"]
    ema20 = row["ema20"]
    ema50 = row["ema50"]
    macdh = row["macd_hist"]

    # Guard
    if np.isnan([c, rsi, lb, ub, ema20, ema50]).any():
        return (None, None, 0)

    # Base rules
    if c <= lb and rsi <= 30:
        # extra confirmations
        conf = 1
        reason = ["Bollinger alt temas", f"RSI {rsi:.1f}"]
        if ema20 > ema50:
            conf += 1
            reason.append("EMA20>EMA50 (trend ↑)")
        if macdh is not None and not np.isnan(macdh) and macdh > 0:
            conf += 1
            reason.append("MACD hist > 0")
        return ("BUY", ", ".join(reason), conf)

    if c >= ub and rsi >= 70:
        conf = 1
        reason = ["Bollinger üst temas", f"RSI {rsi:.1f}"]
        if ema20 < ema50:
            conf += 1
            reason.append("EMA20<EMA50 (trend ↓)")
        if macdh is not None and not np.isnan(macdh) and macdh < 0:
            conf += 1
            reason.append("MACD hist < 0")
        return ("SELL", ", ".join(reason), conf)

    return (None, None, 0)

# ------------- Analysis & Notify -------------
def analyze_once(symbol: str, tf: str):
    now_local = datetime.now(TZ)
    df = fetch_ohlc(symbol, tf)
    if df.empty or len(df) < 50:
        print(f"[INFO] No data for {symbol} {tf}")
        return

    df = compute_indicators(df)
    last = df.iloc[-1]

    side, reason, conf = signal_from_row(last)
    if side is None:
        return

    if not can_send(symbol, tf, side, now_local):
        return

    price = last["close"]
    rsi = last["rsi"]
    bb_l = last["bb_lower"]
    bb_m = last["bb_mid"]
    bb_u = last["bb_upper"]
    ema20 = last["ema20"]
    ema50 = last["ema50"]
    macd = last.get("macd", np.nan)
    macds = last.get("macd_signal", np.nan)
    macdh = last.get("macd_hist", np.nan)

    # Build message
    conf_stars = "⭐" * max(1, min(3, int(conf)))
    msg = (
        f"⏱ *TRADER60 — {tf} Sinyal*  \n"
        f"• *{symbol}* — Fiyat: `{price:.4f}`  \n"
        f"• Sinyal: *{('📈 ALIM' if side=='BUY' else '📉 SATIŞ')}* {conf_stars}  \n"
        f"• Neden: {reason}  \n"
        f"• RSI: `{rsi:.1f}`  \n"
        f"• BB(L/M/U): `{bb_l:.4f}` / `{bb_m:.4f}` / `{bb_u:.4f}`  \n"
        f"• EMA20/EMA50: `{ema20:.4f}` / `{ema50:.4f}`  \n"
        f"• MACD / Signal / Hist: `{macd:.4f}` / `{macds:.4f}` / `{macdh:.4f}`  \n"
        f"_Zaman: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}_"
    )

    tg_send(msg)
    touch_signal(symbol, tf, side, now_local)
    print(f"[OK] Sent {side} for {symbol} {tf} at {now_local}")

# ------------- Scheduler -------------
def run_timeframe(tf: str):
    print(f"[RUN] Checking timeframe {tf} @ {datetime.now(TZ)}")
    for sym in SYMBOLS:
        try:
            analyze_once(sym, tf)
        except Exception as e:
            print(f"[ERR] analyze {sym} {tf}: {e}")

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[FATAL] TELEGRAM_TOKEN or TELEGRAM_CHAT_ID is missing. Set them in Railway env or config.env")
        return

    print("=== TRADER60 bot starting... ===")
    print(f"Symbols: {len(SYMBOLS)} | TFs: {TIMEFRAMES}")
    print(f"Timezone: {TZ}")
    print(f"Debounce: {DEBOUNCE_MIN} min")

    jobstores = {"default": MemoryJobStore()}
    executors = {"default": ThreadPoolExecutor(10), "processpool": ProcessPoolExecutor(2)}
    job_defaults = {"coalesce": True, "max_instances": 3}
    scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults, timezone=TZ)

    # Schedule per timeframe
    # We'll trigger at exact multiples: */5, */15, */30 minutes, and hourly at :00, 4-hourly at 00/04/08/12/16/20
    for tf in TIMEFRAMES:
        if tf == "5m":
            trigger = CronTrigger(minute="*/5")
        elif tf == "15m":
            trigger = CronTrigger(minute="*/15")
        elif tf == "30m":
            trigger = CronTrigger(minute="*/30")
        elif tf == "1h":
            trigger = CronTrigger(minute="0")
        elif tf == "4h":
            trigger = CronTrigger(minute="0", hour="0,4,8,12,16,20")
        else:
            # default: run every hour
            trigger = CronTrigger(minute="0")

        scheduler.add_job(run_timeframe, trigger, args=[tf], name=f"tf_{tf}")

    scheduler.start()
    tg_send("✅ TRADER60 bot başlatıldı. Sinyaller seçili periyotlarda gönderilecektir.")
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Bot stopped.")

if __name__ == "__main__":
    main()
