#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, time, json
from datetime import datetime, timezone, timedelta
import numpy as np, pandas as pd, yfinance as yf, requests, pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from dotenv import load_dotenv

if os.path.exists("config.env"):
    load_dotenv("config.env")
else:
    load_dotenv()

BOT_TOKEN=os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID=os.getenv("TELEGRAM_CHAT_ID","").strip()
DEBOUNCE_MIN=int(os.getenv("DEBOUNCE_MIN","60"))
TZ=pytz.timezone(os.getenv("APP_TIMEZONE","Europe/Istanbul"))

DEFAULT_SYMBOLS=[
    "THYAO.IS","ASELS.IS","KCHOL.IS","TOASO.IS","TUPRS.IS","ULKER.IS","ENKAI.IS","GUBRF.IS",
    "USDTRY=X","EURTRY=X","EURUSD=X","GBPUSD=X","USDJPY=X",
    "^N225","^IXIC","^GSPC","^FCHI","^RUT","^FTSE","^GDAXI","^SSMI","^DJI","^WIG20",
    "GC=F","SI=F","BZ=F","CL=F",
    "BTC-USD","ETH-USD","XRP-USD","SOL-USD","ADA-USD","SUI-USD","BCH-USD",
    "PEPE-USD","AVAX-USD","ARB-USD","LTC-USD","HBAR-USD","WBTC-USD","XLM-USD","SHIB-USD"
]
SYMBOLS=[s.strip() for s in os.getenv("SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(",") if s.strip()]
TIMEFRAMES=[t.strip() for t in os.getenv("TIMEFRAMES","5m,15m,30m,1h,4h").split(",") if t.strip()]

STATE_FILE="state.json"
def load_state():
    try:
        if os.path.exists(STATE_FILE):
            import json
            return json.load(open(STATE_FILE,"r",encoding="utf-8"))
    except: pass
    return {}
def save_state(st):
    try:
        import json
        json.dump(st, open(STATE_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    except: pass
STATE=load_state()

def can_send(symbol, tf, side, now):
    key=f"{symbol}|{tf}|{side}"
    last=STATE.get(key)
    if last is None: return True
    last_dt=datetime.fromtimestamp(last, tz=timezone.utc).astimezone(TZ)
    return (now-last_dt)>=timedelta(minutes=DEBOUNCE_MIN)

def touch(symbol, tf, side, now):
    key=f"{symbol}|{tf}|{side}"
    STATE[key]=now.astimezone(timezone.utc).timestamp()
    save_state(STATE)

def tg_send(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("[FATAL] TELEGRAM_TOKEN/CHAT_ID eksik"); return
    try:
        url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id":CHAT_ID,"text":text,"parse_mode":"Markdown"}, timeout=20)
    except Exception as e:
        print("[TG ERROR]",e)

def rsi(series, length=14):
    delta=series.diff()
    gain=delta.clip(lower=0)
    loss=(-delta).clip(lower=0)
    avg_gain=gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss=loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs=avg_gain/avg_loss.replace(0, np.nan)
    return 100-(100/(1+rs))

def bollinger(series, length=20, std_mult=2.0):
    ma=series.rolling(length, min_periods=length).mean()
    sd=series.rolling(length, min_periods=length).std(ddof=0)
    lower=ma-std_mult*sd
    upper=ma+std_mult*sd
    return lower, ma, upper

def fetch(symbol, tf):
    tfmap={"5m":("5m","7d"),"15m":("15m","30d"),"30m":("30m","60d"),"1h":("60m","60d"),"4h":("60m","60d")}
    interval, period=tfmap.get(tf,("60m","60d"))
    try:
        df=yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=False, threads=True)
        if df is None or df.empty: return pd.DataFrame()
        df=df.rename(columns=str.lower)
        if getattr(df.index,"tz",None) is not None:
            df.index=df.index.tz_localize(None)
        if tf=="4h":
            df=df.resample("4H").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
        return df
    except Exception as e:
        print("[FETCH ERR]",symbol,tf,e); return pd.DataFrame()

def analyze_once(symbol, tf):
    now=datetime.now(TZ)
    df=fetch(symbol, tf)
    if df.empty or len(df)<50: return
    close=df["close"]
    rsi14=rsi(close,14)
    bb_l, bb_m, bb_u=bollinger(close,20,2.0)
    idx=df.index[-1]
    c=float(close.loc[idx])
    r=float(rsi14.loc[idx]) if not np.isnan(rsi14.loc[idx]) else np.nan
    lb=float(bb_l.loc[idx]) if not np.isnan(bb_l.loc[idx]) else np.nan
    ub=float(bb_u.loc[idx]) if not np.isnan(bb_u.loc[idx]) else np.nan
    mb=float(bb_m.loc[idx]) if not np.isnan(bb_m.loc[idx]) else np.nan
    side=None; reason=[]
    if not np.isnan(r) and not np.isnan(lb) and c<=lb and r<=30:
        side="BUY"; reason=[f"Bollinger alt temas", f"RSI {r:.1f}"]
    elif not np.isnan(r) and not np.isnan(ub) and c>=ub and r>=70:
        side="SELL"; reason=[f"Bollinger üst temas", f"RSI {r:.1f}"]
    if side is None: return
    if not can_send(symbol, tf, side, now): return
    stars="⭐⭐"
    msg=(f"⏱ *TRADER60 — {tf} Sinyal*
"
         f"• *{symbol}* — Fiyat: `{c:.4f}`
"
         f"• Sinyal: *{('📈 ALIM' if side=='BUY' else '📉 SATIŞ')}* {stars}
"
         f"• Neden: {', '.join(reason)}
"
         f"• RSI: `{(r if not np.isnan(r) else float('nan')):.1f}`
"
         f"• BB(L/M/U): `{(lb if not np.isnan(lb) else float('nan')):.4f}` / `{(mb if not np.isnan(mb) else float('nan')):.4f}` / `{(ub if not np.isnan(ub) else float('nan')):.4f}`
"
         f"_Zaman: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}_")
    tg_send(msg); touch(symbol, tf, side, now); print("[OK]",symbol,tf,side,now)

def run_tf(tf):
    print("[RUN]",tf,datetime.now(TZ))
    for s in SYMBOLS:
        try: analyze_once(s, tf)
        except Exception as e: print("[ANALYZE ERR]",s,tf,e)

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[FATAL] TELEGRAM_TOKEN veya TELEGRAM_CHAT_ID eksik"); return
    print("=== TRADER60 FINAL start ==="); print("TFs:",TIMEFRAMES); print("Symbols:",len(SYMBOLS)); print("TZ:",TZ)
    scheduler=BackgroundScheduler(jobstores={"default":MemoryJobStore()}, executors={"default":ThreadPoolExecutor(10),"processpool":ProcessPoolExecutor(2)}, job_defaults={"coalesce":True,"max_instances":3}, timezone=TZ)
    for tf in TIMEFRAMES:
        if tf=="5m": trig=CronTrigger(minute="*/5")
        elif tf=="15m": trig=CronTrigger(minute="*/15")
        elif tf=="30m": trig=CronTrigger(minute="*/30")
        elif tf=="1h": trig=CronTrigger(minute="0")
        elif tf=="4h": trig=CronTrigger(minute="0", hour="0,4,8,12,16,20")
        else: trig=CronTrigger(minute="0")
        scheduler.add_job(run_tf, trig, args=[tf], name=f"tf_{tf}")
    scheduler.start(); tg_send("✅ TRADER60 bot başlatıldı (final clean build).")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()

if __name__=="__main__":
    main()
