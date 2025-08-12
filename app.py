import os, datetime, requests, asyncio
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import yfinance as yf
from fastapi import FastAPI

# ===== ENV =====
TOKEN   = (os.getenv("TELEGRAM_TOKEN") or "").strip().strip('"').strip("'")
CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip().strip('"').strip("'")
TZ_NAME = os.getenv("TIMEZONE", "Europe/Istanbul")
RUN_HOUR   = int(os.getenv("RUN_HOUR", 9))
RUN_MINUTE = int(os.getenv("RUN_MINUTE", 30))

STOCKS  = [s.strip() for s in (os.getenv("STOCKS_CSV",
          "THYAO.IS,TOASO.IS,GUBRF.IS,ENKAI.IS,TUPRS.IS,ULKER.IS,KCHOL.IS,ASELS.IS")).split(",") if s.strip()]
# BIST100 için Yahoo'da XU100.IS daha stabil
INDICES = [s.strip() for s in (os.getenv("INDICES_CSV",
          "XU100.IS,^GSPC,^NDX,^DJI")).split(",") if s.strip()]
# Altın, gümüş, brent, WTI, doğalgaz + FX/kripto
COMMS   = [s.strip() for s in (os.getenv("COMMODS_CSV",
          "XAU=X,XAG=X,BZ=F,CL=F,NG=F,BTC-USD,EURUSD=X,USDTRY=X")).split(",") if s.strip()]

app = FastAPI()

# ===== Telegram =====
def tg_send(text: str) -> bool:
    if not TOKEN or not CHAT_ID:
        print("[TG] missing env"); return False
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": text[:3900]}, timeout=20)
    try:
        ok = r.json().get("ok", False)
    except Exception:
        ok = False
    print(f"[TG] status={r.status_code} ok={ok}")
    if not ok:
        print("[TG] body:", r.text)
    return ok

# ===== Helpers =====
def last_scalar(series) -> float | None:
    """Son değeri güvenli biçimde float döndür (Series/np scalar olabilir)."""
    if series is None or len(series) == 0:
        return None
    v = series.iloc[-1]
    if pd.isna(v):
        return None
    try:
        # np scalar ise .item(), değilse direkt float
        return float(getattr(v, "item", lambda: v)())
    except Exception:
        return None

def fetch_df(ticker: str) -> pd.DataFrame | None:
    """1 yıllık günlük veri + SMA20/50/200 + RSI14 hesapla."""
    try:
        df = yf.download(ticker, period="1y", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        close = df["Close"].astype(float)

        df["SMA20"]  = close.rolling(20).mean()
        df["SMA50"]  = close.rolling(50).mean()
        df["SMA200"] = close.rolling(200).mean()

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss.replace(0, np.nan))
        df["RSI14"] = 100 - (100 / (1 + rs))
        return df
    except Exception as e:
        print(f"[ERR] fetch {ticker}: {e}")
        return None

def signal_from(c, s20, s50, s200, rsi):
    """Güçlü Al / Al / Nötr / Sat / Güçlü Sat kuralları (float giriş!)"""
    def ok(x): return x is not None
    tag = "Nötr"
    if ok(s50) and ok(s200) and ok(c):
        if s50 > s200:
            if ok(s20) and c > s50 and c > s20:
                tag = "Güçlü Al"
            elif c > s50 or (ok(s20) and c > s20):
                tag = "Al"
        elif s50 < s200:
            if ok(s20) and c < s50 and c < s20:
                tag = "Güçlü Sat"
            elif c < s50 or (ok(s20) and c < s20):
                tag = "Sat"
    if rsi is not None:
        if rsi >= 70: tag += " · RSI↑70"
        elif rsi <= 30: tag += " · RSI↓30"
    return tag

def analyze_block(title: str, tickers: list[str]) -> str:
    """Seri hatalarını tamamen önleyen, okunaklı blok mesajı üretir."""
    lines = [f"📊 {title}"]
    for t in tickers:
        df = fetch_df(t)
        if df is None or df.empty or len(df) < 50:
            lines.append(f"{t}: 📛 Veri yok/az")
            continue

        c    = last_scalar(df["Close"])
        s20  = last_scalar(df["SMA20"])
        s50  = last_scalar(df["SMA50"])
        s200 = last_scalar(df["SMA200"])
        rsi  = last_scalar(df["RSI14"])

        if c is None:
            lines.append(f"{t}: 📛 Veri yok")
            continue

        prev = last_scalar(df["Close"].shift(1).dropna())
        chg = (c / prev - 1.0) * 100.0 if prev else 0.0

        sig = signal_from(c, s20, s50, s200, rsi)
        lines.append(f"{t}: {c:.2f} ({chg:+.2f}%) — {sig}")
    return "\n".join(lines)

async def run_daily():
    ts = datetime.datetime.now(ZoneInfo(TZ_NAME)).strftime("%Y-%m-%d %H:%M")
    tg_send(f"📈 TRADER60 — Günlük Analiz ({ts} {TZ_NAME})")
    tg_send(analyze_block("Hisseler", STOCKS))
    tg_send(analyze_block("Endeksler", INDICES))
    tg_send(analyze_block("Emtia/FX/Kripto", COMMS))
    tg_send("✅ TRADER60 — Günlük Analiz bitti.")

# ===== Routes =====
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

# ===== Basit zamanlayıcı (harici cron yoksa) =====
async def scheduler():
    while True:
        now = datetime.datetime.now(ZoneInfo(TZ_NAME))
        if now.hour == RUN_HOUR and now.minute == RUN_MINUTE:
            await run_daily()
            await asyncio.sleep(60)  # aynı dakikada iki kez çalışmasın
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    tg_send("✅ TRADER60 — Worker aktif...")
    asyncio.create_task(scheduler())

