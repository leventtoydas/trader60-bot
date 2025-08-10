#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (same robust TRADER60 main.py as previous package)
# For brevity, this is identical to the earlier main.py you downloaded.
# It supports 5m,15m,30m,1h,4h, RSI/Bollinger/EMA/MACD, debounce, Telegram alerts.
import os, time, json
from datetime import datetime, timezone, timedelta
import numpy as np, pandas as pd, requests, pandas_ta as ta, yfinance as yf, pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from dotenv import load_dotenv

if os.path.exists("config.env"):
    load_dotenv("config.env")
else:
    load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID","").strip()
DEBOUNCE_MIN = int(os.getenv("DEBOUNCE_MIN","60"))
TZ = pytz.timezone(os.getenv("APP_TIMEZONE","Europe/Istanbul"))

SYMBOLS = os.getenv("SYMBOLS","").strip()
if not SYMBOLS:
    SYMBOLS = "THYAO.IS,TOASO.IS,GUBRF.IS,ENKAI.IS,TUPRS.IS,ULKER.IS,KCHOL.IS,ASELS.IS,XU100.IS,USDTRY=X,EURUSD=X,XAUUSD=X,XAGUSD=X,^GSPC,^NDX,^IXIC,^GDAXI,^FTSE,^N225,CL=F,BZ=F,BTC-USD,ETH-USD"
SYMBOLS = [s.strip() for s in SYMBOLS.split(",") if s.strip()]

TIMEFRAMES = [t.strip() for t in os.getenv("TIMEFRAMES","5m,15m,30m,1h,4h").split(",") if t.strip()]

STATE_FILE="state.json"
def _load_state():
    try:
        import json, os
        if os.path.exists(STATE_FILE):
            return json.load(open(STATE_FILE,"r",encoding="utf-8"))
    except: pass
    return {}
def _save_state(st):
    try:
        json.dump(st, open(STATE_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    except: pass
STATE=_load_state()

def tg_send(text):
    if not BOT_TOKEN or not CHAT_ID: 
        print("[WARN] Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
        return
    url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id":CHAT_ID,"text":text,"parse_mode":"Markdown"}, timeout=20)
    except Exception as e:
        print("[TG ERROR]",e)

def can_send(symbol,tf,side,now_dt):
    key=f"{symbol}|{tf}|{side}"
    last=STATE.get(key)
    if last is None: return True
    import datetime as dt
    last_dt = datetime.fromtimestamp(last, tz=timezone.utc).astimezone(TZ)
    return (now_dt - last_dt) >= timedelta(minutes=DEBOUNCE_MIN)

def touch(symbol,tf,side,now_dt):
    key=f"{symbol}|{tf}|{side}"
    STATE[key]= now_dt.astimezone(timezone.utc).timestamp()
    _save_state(STATE)

def fetch(symbol, tf):
    tfmap={"5m":("5m","7d"),"15m":("15m","30d"),"30m":("30m","60d"),"1h":("60m","60d"),"4h":("60m","60d")}
    interval, period = tfmap.get(tf,("60m","60d"))
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=False, threads=True)
    if df is None or df.empty: return df
    df = df.rename(columns=str.lower)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    if tf=="4h":
        df = df.resample("4H").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    return df

def indicators(df):
    df["rsi"]=ta.rsi(df["close"], length=14)
    bb=ta.bbands(df["close"], length=20, std=2.0)
    if bb is not None and not bb.empty:
        df["bb_lower"]=bb["BBL_20_2.0"]; df["bb_mid"]=bb["BBM_20_2.0"]; df["bb_upper"]=bb["BBU_20_2.0"]
    else:
        df["bb_lower"]=np.nan; df["bb_mid"]=np.nan; df["bb_upper"]=np.nan
    df["ema20"]=ta.ema(df["close"], length=20)
    df["ema50"]=ta.ema(df["close"], length=50)
    macd=ta.macd(df["close"], fast=12, slow=26, signal=9)
    if macd is not None and not macd.empty:
        df["macd"]=macd["MACD_12_26_9"]; df["macd_signal"]=macd["MACDs_12_26_9"]; df["macd_hist"]=macd["MACDh_12_26_9"]
    else:
        df["macd"]=np.nan; df["macd_signal"]=np.nan; df["macd_hist"]=np.nan
    return df

def rule(row):
    c=row["close"]; r=row["rsi"]; lb=row["bb_lower"]; ub=row["bb_upper"]; e20=row["ema20"]; e50=row["ema50"]; h=row["macd_hist"]
    if any([np.isnan(x) for x in [c,r,lb,ub,e20,e50]]): return (None,None,0)
    if c<=lb and r<=30:
        conf=1; reason=[f"Bollinger alt temas","RSI %.1f"%r]
        if e20>e50: conf+=1; reason.append("EMA20>EMA50")
        if not np.isnan(h) and h>0: conf+=1; reason.append("MACD hist > 0")
        return ("BUY", ", ".join(reason), conf)
    if c>=ub and r>=70:
        conf=1; reason=[f"Bollinger üst temas","RSI %.1f"%r]
        if e20<e50: conf+=1; reason.append("EMA20<EMA50")
        if not np.isnan(h) and h<0: conf+=1; reason.append("MACD hist < 0")
        return ("SELL", ", ".join(reason), conf)
    return (None,None,0)

def analyze_once(symbol, tf):
    now = datetime.now(TZ)
    df = fetch(symbol, tf)
    if df is None or df.empty or len(df)<50: return
    df = indicators(df)
    row = df.iloc[-1]
    side, reason, conf = rule(row)
    if side is None: return
    if not can_send(symbol, tf, side, now): return
    price=row["close"]; r=row["rsi"]; lb=row["bb_lower"]; mb=row["bb_mid"]; ub=row["bb_upper"]; e20=row["ema20"]; e50=row["ema50"]; m=row["macd"]; ms=row["macd_signal"]; mh=row["macd_hist"]
    stars="⭐"*max(1,min(3,int(conf)))
    msg=(f"⏱ *TRADER60 — {tf} Sinyal*
"
         f"• *{symbol}* — Fiyat: `{price:.4f}`
"
         f"• Sinyal: *{('📈 ALIM' if side=='BUY' else '📉 SATIŞ')}* {stars}
"
         f"• Neden: {reason}
"
         f"• RSI: `{r:.1f}`
"
         f"• BB(L/M/U): `{lb:.4f}` / `{mb:.4f}` / `{ub:.4f}`
"
         f"• EMA20/EMA50: `{e20:.4f}` / `{e50:.4f}`
"
         f"• MACD/Signal/Hist: `{m:.4f}` / `{ms:.4f}` / `{mh:.4f}`
"
         f"_Zaman: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}_")
    tg_send(msg); touch(symbol, tf, side, now); print("[OK] Sent", side, symbol, tf, now)

def run_tf(tf):
    print("[RUN] TF", tf, datetime.now(TZ))
    for s in SYMBOLS:
        try: analyze_once(s, tf)
        except Exception as e: print("[ERR]", s, tf, e)

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[FATAL] TELEGRAM_TOKEN veya TELEGRAM_CHAT_ID eksik"); return
    print("=== TRADER60 start ==="); print("TFs:", TIMEFRAMES); print("Symbols:", len(SYMBOLS)); print("TZ:", TZ)
    scheduler = BackgroundScheduler(jobstores={"default":MemoryJobStore()}, executors={"default":ThreadPoolExecutor(10),"processpool":ProcessPoolExecutor(2)}, job_defaults={"coalesce":True,"max_instances":3}, timezone=TZ)
    for tf in TIMEFRAMES:
        if tf=="5m": trig=CronTrigger(minute="*/5")
        elif tf=="15m": trig=CronTrigger(minute="*/15")
        elif tf=="30m": trig=CronTrigger(minute="*/30")
        elif tf=="1h": trig=CronTrigger(minute="0")
        elif tf=="4h": trig=CronTrigger(minute="0", hour="0,4,8,12,16,20")
        else: trig=CronTrigger(minute="0")
        scheduler.add_job(run_tf, trig, args=[tf], name=f"tf_{tf}")
    scheduler.start(); tg_send("✅ TRADER60 bot başlatıldı.")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()

if __name__=="__main__": main()
