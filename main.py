#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time, json
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
import yfinance as yf
import requests
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from dotenv import load_dotenv

# ==== ENV ====
if os.path.exists("config.env"):
    load_dotenv("config.env")
else:
    load_dotenv()

BOT_TOKEN    = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID      = os.getenv("TELEGRAM_CHAT_ID","").strip()
TZ           = pytz.timezone(os.getenv("APP_TIMEZONE","Europe/Istanbul"))
DEBOUNCE_MIN = int(os.getenv("DEBOUNCE_MIN","60"))
TIMEFRAMES   = [t.strip() for t in os.getenv("TIMEFRAMES","5m,15m,30m,1h,4h").split(",") if t.strip()]

# ==== Semboller (geçerli olanlar) ====
LIST_BIST = ["THYAO.IS","ASELS.IS","KCHOL.IS","TOASO.IS","TUPRS.IS","ULKER.IS","ENKAI.IS","GUBRF.IS"]
LIST_FX   = ["USDTRY=X","EURTRY=X","EURUSD=X","GBPUSD=X","USDJPY=X"]
LIST_IDX  = ["^N225","^IXIC","^GSPC","^FCHI","^RUT","^FTSE","^GDAXI","^SSMI","^DJI"]  # ^BIST100 yok
LIST_COM  = ["GC=F","SI=F","BZ=F","CL=F"]  # Altın, Gümüş, Brent, WTI
LIST_CR_USDT = [
    "BTCUSDT","ETHUSDT","XRPUSDT","SOLUSDT","ADAUSDT","SUIUSDT","BCHUSDT",
    "PEPEUSDT","AVAXUSDT","ARBUSDT","LTCUSDT","HBARUSDT","WBTCUSDT","XLMUSDT","SHIBUSDT"
]

def _map_to_yf(sym: str) -> str:
    s = sym.strip()
    if s.endswith("USDT") and len(s) > 5:
        return f"{s[:-4]}-USD"  # BTCUSDT -> BTC-USD
    if s.upper() == "UKOIL":
        return "BZ=F"
    if s.upper() in {"^BIST100","^XU030"}:
        return ""  # Yahoo desteklemiyor
    return s

DEFAULT_SYMBOLS = (
    LIST_BIST + LIST_FX + LIST_IDX + LIST_COM +
    [_map_to_yf(s) for s in LIST_CR_USDT]
)
SYMBOLS = [s for s in DEFAULT_SYMBOLS if s]

# ==== Debounce ====
STATE_FILE = "state.json"
def _load_state():
    try:
        if os.path.exists(STATE_FILE):
            return json.load(open(STATE_FILE,"r",encoding="utf-8"))
    except: pass
    return {}
def _save_state(st):
    try:
        json.dump(st, open(STATE_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    except: pass
STATE = _load_state()

def can_send(symbol, tf, label, now):
    key = f"{symbol}|{tf}|{label}"
    last = STATE.get(key)
    if last is None: return True
    last_dt = datetime.fromtimestamp(last, tz=timezone.utc).astimezone(TZ)
    return (now - last_dt) >= timedelta(minutes=DEBOUNCE_MIN)

def touch(symbol, tf, label, now):
    key = f"{symbol}|{tf}|{label}"
    STATE[key] = now.astimezone(timezone.utc).timestamp()
    _save_state(STATE)

# ==== Telegram ====
def tg_send(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("[FATAL] TELEGRAM_TOKEN/CHAT_ID eksik")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id":CHAT_ID,"text":text,"parse_mode":"Markdown"}, timeout=20)
    except Exception as e:
        print("[TG ERROR]", e)

# ==== Göstergeler ====
def _ema(s,n): return pd.Series(pd.to_numeric(s, errors="coerce")).ewm(span=n, adjust=False, min_periods=n).mean()
def rsi(s,n=14):
    s = pd.to_numeric(s, errors="coerce")
    d = s.diff(); up = d.clip(lower=0); dn = (-d).clip(upper=0)
    au = up.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = au / ad.replace(0, np.nan)
    return 100 - (100/(1+rs))
def stoch(h,l,c,k=9,d=6):
    ll = l.rolling(k, min_periods=k).min(); hh = h.rolling(k, min_periods=k).max()
    kf = (c-ll)/(hh-ll)*100; ds = kf.rolling(d, min_periods=d).mean()
    return kf, ds
def stoch_rsi(c,n=14):
    r = rsi(c,n); ll = r.rolling(n, min_periods=n).min(); hh = r.rolling(n, min_periods=n).max()
    return (r-ll)/(hh-ll)
def macd(c,fast=12,slow=26,signal=9):
    ef = _ema(c,fast); es = _ema(c,slow)
    line = ef - es; sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = line - sig; return line,sig,hist
def adx(h,l,c,n=14):
    plus_dm = (h.diff()).clip(lower=0); minus_dm = (-l.diff()).clip(lower=0)
    tr1 = (h-l); tr2 = (h-c.shift()).abs(); tr3 = (l-c.shift()).abs()
    tr = pd.concat([tr1,tr2,tr3],axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    plus_di = 100*(plus_dm.ewm(alpha=1/n, adjust=False, min_periods=n).mean()/atr)
    minus_di= 100*(minus_dm.ewm(alpha=1/n, adjust=False, min_periods=n).mean()/atr)
    dx = 100*(plus_di-minus_di).abs()/(plus_di+minus_di)
    adx_ = dx.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    return adx_, plus_di, minus_di
def williams_r(h,l,c,n=14):
    hh = h.rolling(n, min_periods=n).max(); ll = l.rolling(n, min_periods=n).min()
    return (hh-c)/(hh-ll)*-100
def cci(h,l,c,n=14):
    tp = (h+l+c)/3; ma = tp.rolling(n, min_periods=n).mean(); md = (tp-ma).abs().rolling(n, min_periods=n).mean()
    return (tp-ma)/(0.015*md)
def atr(h,l,c,n=14):
    tr1=(h-l); tr2=(h-c.shift()).abs(); tr3=(l-c.shift()).abs()
    tr=pd.concat([tr1,tr2,tr3],axis=1).max(axis=1); return tr.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
def highs_lows_osc(h,l,c,n=14):
    ll=l.rolling(n, min_periods=n).min(); hh=h.rolling(n, min_periods=n).max()
    return (c-ll)/(hh-ll)*100
def ultimate_osc(h,l,c,s1=7,s2=14,s3=28):
    pc=c.shift(1); bp = c - pd.concat([l,pc],axis=1).min(axis=1)
    tr = pd.concat([h,pc],axis=1).max(axis=1) - pd.concat([l,pc],axis=1).min(axis=1)
    a1 = bp.rolling(s1, min_periods=s1).sum() / tr.rolling(s1, min_periods=s1).sum()
    a2 = bp.rolling(s2, min_periods=s2).sum() / tr.rolling(s2, min_periods=s2).sum()
    a3 = bp.rolling(s3, min_periods=s3).sum() / tr.rolling(s3, min_periods=s3).sum()
    return 100*(4*a1 + 2*a2 + a3)/7
def roc(c,n=12): return (c/c.shift(n)-1)*100
def bull_bear_power(h,l,c,n=13):
    ema=_ema(c,n); return h-ema, l-ema

# ==== Veri çekme ====
def fetch(symbol, tf):
    tfmap = {"5m":("5m","10d"), "15m":("15m","30d"), "30m":("30m","60d"), "1h":("60m","60d"), "4h":("60m","60d")}
    interval, period = tfmap.get(tf, ("60m","60d"))
    try:
        df = yf.download(sdef fetch(symbol, tf):
    tfmap = {"5m":("5m","10d"), "15m":("15m","30d"), "30m":("30m","60d"), "1h":("60m","60d"), "4h":("60m","60d")}
    interval, period = tfmap.get(tf, ("60m","60d"))

    try:
        df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=False, threads=True)
        if df is None or df.empty:
            print(f"[INFO] Veri yok: {symbol} {tf}")
            return pd.DataFrame()

        # 1) Kolonları normalize et (MultiIndex dahil)
        cols = []
        for c in df.columns:
            if isinstance(c, tuple):
                # ('Open', 'SYMB') -> 'open'
                parts = [str(x).strip().lower() for x in c if str(x).strip()]
                # 'open', 'high', 'low', 'close', 'adj close', 'volume' gibi anahtarları yakala
                if any(p in ("open","high","low","close","adj close","volume") for p in parts):
                    cols.append(parts[0])
                else:
                    cols.append("_".join(parts))
            else:
                cols.append(str(c).strip().lower())
        df.columns = cols

        # 2) Sadece gereken kolonları güvenle topla
        need = {}
        for key in ["open","high","low","close"]:
            if key in df.columns:
                need[key] = pd.to_numeric(df[key], errors="coerce")
            else:
                # bazı sembollerde 'adj close' tek geliyor, 'close' yoksa onu kullan
                if key == "close" and "adj close" in df.columns:
                    need["close"] = pd.to_numeric(df["adj close"], errors="coerce")
        df = pd.DataFrame(need)
        if df.empty or df[["close"]].dropna().empty:
            print(f"[INFO] Veri yok/eksik: {symbol} {tf}")
            return pd.DataFrame()

        # 3) Zaman bölgesi & 4H resample
        if getattr(df.index, "tz", None) is not None:
            df.index = df.index.tz_localize(None)
        if tf == "4h":
            df = df.resample("4H").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna(how="any")

        # 4) Temizlik
        df = df.dropna(subset=["close","high","low"])
        return df

    except Exception as e:
        print(f"[FETCH ERR] {symbol} {tf}: {e}")
        return pd.DataFrame()

# ==== Skor & Özet ====
def score_indicators(df):
    h,l,c = df["high"], df["low"], df["close"]
    out = {}
    rsi14 = rsi(c,14); out["RSI(14)"] = ("Al" if rsi14.iloc[-1] <= 30 else ("Sat" if rsi14.iloc[-1] >= 70 else "Nötr"), float(rsi14.iloc[-1]))
    kf,ds = stoch(h,l,c,9,6); stv = float(kf.iloc[-1]); out["STOCH(9,6)"] = ("Aşırı Alış" if stv >= 80 else ("Aşırı Satış" if stv <= 20 else "Nötr"), stv)
    srs = float(stoch_rsi(c,14).iloc[-1]*100); out["STOCHRSI(14)"] = ("Aşırı Alış" if srs >= 80 else ("Aşırı Satış" if srs <= 20 else "Nötr"), srs)
    ml,ms,mh = macd(c,12,26,9); mhh = float(mh.iloc[-1]); out["MACD(12,26)"] = ("Al" if mhh > 0 else ("Sat" if mhh < 0 else "Nötr"), mhh)
    ad, pdi, mdi = adx(h,l,c,14); adl = float(ad.iloc[-1]); p=float(pdi.iloc[-1]); m=float(mdi.iloc[-1])
    out["ADX(14)"] = ("Al" if (adl >= 25 and p > m) else ("Sat" if (adl >= 25 and p < m) else "Nötr"), adl)
    wr = float(williams_r(h,l,c,14).iloc[-1]); out["Williams %R"] = ("Aşırı Alış" if wr >= -20 else ("Aşırı Satış" if wr <= -80 else "Nötr"), wr)
    cci14 = float(cci(h,l,c,14).iloc[-1]); out["CCI(14)"] = ("Al" if cci14 >= 100 else ("Sat" if cci14 <= -100 else "Nötr"), cci14)
    atr14 = float(atr(h,l,c,14).iloc[-1]); atr_ratio = (atr14 / max(float(c.iloc[-1]), 1e-9))*100
    out["ATR(14)"] = ("Düşük Hareketli" if atr_ratio < 1.0 else "Yüksek Hareketli", atr14)
    hlosc = float(highs_lows_osc(h,l,c,14).iloc[-1]); out["Highs/Lows(14)"] = ("Al" if hlosc >= 80 else ("Sat" if hlosc <= 20 else "Nötr"), hlosc)
    uo = float(ultimate_osc(h,l,c,7,14,28).iloc[-1]); out["Ultimate Oscillator"] = ("Aşırı Alış" if uo >= 70 else ("Aşırı Satış" if uo <= 30 else "Nötr"), uo)
    rc = float(roc(c,12).iloc[-1]); out["ROC(12)"] = ("Al" if rc > 0 else ("Sat" if rc < 0 else "Nötr"), rc)
    bull, bear = bull_bear_power(h,l,c,13); bb = float(bull.iloc[-1]) - float(bear.iloc[-1])
    out["Bull/Bear Power(13)"] = ("Al" if (bull.iloc[-1] > 0 and bear.iloc[-1] > 0) else ("Sat" if (bull.iloc[-1] < 0 and bear.iloc[-1] < 0) else "Nötr"), bb)
    return out

def summarize(sc):
    buy = sell = 0
    labels = []
    for name,(sig,val) in sc.items():
        labels.append(f"{name}: {val:.3f} → {sig}")
        if sig in ("Al","Aşırı Satış"): buy += 1
        elif sig in ("Sat","Aşırı Alış"): sell += 1
    summary = "Güçlü Al" if buy - sell >= 4 else ("Al" if buy - sell >= 2 else ("Güçlü Sat" if sell - buy >= 4 else ("Sat" if sell - buy >= 2 else "Nötr")))
    return summary, buy, sell, labels

def analyze_symbol(symbol, tf):
    df = fetch(symbol, tf)
    if df.empty or len(df) < 60:
        print(f"[INFO] Skip {symbol} {tf}: not enough data")
        return None
    sc = score_indicators(df)
    summary,buy,sell,labels = summarize(sc)
    price = float(df["close"].iloc[-1])
    return summary,buy,sell,labels,price

def run_tf(tf):
    now = datetime.now(TZ)
    for s in SYMBOLS:
        try:
            res = analyze_symbol(s, tf)
            if not res: continue
            summary,buy,sell,labels,price = res
            if not can_send(s, tf, summary, now): continue
            header = f"⏱ *TRADER60 — {tf}* | *{s}* | Fiyat: `{price:.4f}`"
            body   = "\n".join([f"• {ln}" for ln in labels])
            footer = f"*Özet:* {summary}  |  Al:{buy}  Sat:{sell}  Nötr:{max(0,12-buy-sell)}\n_Zaman: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}_"
            msg    = "\n".join([header, body, footer])
            tg_send(msg)
            touch(s, tf, summary, now)
            print("[OK]", s, tf, summary, now)
        except Exception as e:
            print("[ERR]", s, tf, e)

def schedule():
    scheduler = BackgroundScheduler(
        jobstores={"default":MemoryJobStore()},
        executors={"default":ThreadPoolExecutor(10), "processpool":ProcessPoolExecutor(2)},
        job_defaults={"coalesce":True,"max_instances":3},
        timezone=TZ
    )
    for tf in TIMEFRAMES:
        if tf=="5m": trig=CronTrigger(minute="*/5")
        elif tf=="15m": trig=CronTrigger(minute="*/15")
        elif tf=="30m": trig=CronTrigger(minute="*/30")
        elif tf=="1h": trig=CronTrigger(minute="0")
        elif tf=="4h": trig=CronTrigger(minute="0", hour="0,4,8,12,16,20")
        else: trig=CronTrigger(minute="0")
        scheduler.add_job(run_tf, trig, args=[tf], name=f"tf_{tf}")
    scheduler.start()
    return scheduler

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[FATAL] TELEGRAM_TOKEN/CHAT_ID eksik")
        return

    # Başlangıç testi: Telegram’a mesaj
    tg_send("✅ TRADER60 PREMIUM aktif — başlangıç testi (Telegram OK).")

    print("=== TRADER60 PREMIUM start ===")
    print("TFs:", TIMEFRAMES)
    print("Symbols:", len(SYMBOLS))
    print("TZ:", TZ)

    scheduler = schedule()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()

if __name__=="__main__":
    main()
