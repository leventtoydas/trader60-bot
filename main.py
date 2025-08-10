import os
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import time
import requests

# Varsayılan semboller — Railway'de SYMBOLS tanımlı değilse bunlar kullanılacak
DEFAULT_SYMBOLS = [
    # BIST Hisseleri
    "THYAO.IS", "ASELS.IS", "KCHOL.IS", "TOASO.IS", "TUPRS.IS", "ULKER.IS", "ENKAI.IS", "GUBRF.IS",
    # Döviz
    "USDTRY=X", "EURTRY=X", "EURUSD=X", "GBPUSD=X", "USDJPY=X",
    # Global Endeksler
    "^N225", "^IXIC", "^GSPC", "^FCHI", "^RUT", "^FTSE", "^GDAXI", "^SSMI", "^DJI", "^WIG20",
    # Emtia & Enerji
    "GC=F", "SI=F", "BZ=F", "CL=F",
    # Kripto
    "BTC-USD", "ETH-USD", "XRP-USD", "SOL-USD", "ADA-USD", "SUI-USD", "BCH-USD",
    "PEPE-USD", "AVAX-USD", "ARB-USD", "LTC-USD", "HBAR-USD", "WBTC-USD", "XLM-USD", "SHIB-USD"
]

# Environment variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SYMBOLS = os.getenv("SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(",")
TIMEFRAMES = os.getenv("TIMEFRAMES", "5m,15m,30m,1h,4h").split(",")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram mesaj hatası: {e}")

def analyze_symbol(symbol, interval):
    try:
        df = yf.download(symbol, period="7d", interval=interval)
        if df.empty:
            return None
        df["RSI"] = ta.rsi(df["Close"], length=14)
        bb = ta.bbands(df["Close"], length=20, std=2)
        df = pd.concat([df, bb], axis=1)
        last = df.iloc[-1]
        signal = None
        if last["RSI"] < 30 and last["Close"] <= last["BBL_20_2.0"]:
            signal = "📉 *ALIM FIRSATI* (RSI < 30 & Alt Bollinger)"
        elif last["RSI"] > 70 and last["Close"] >= last["BBU_20_2.0"]:
            signal = "📈 *SATIŞ FIRSATI* (RSI > 70 & Üst Bollinger)"
        return signal
    except Exception as e:
        print(f"{symbol} analiz hatası: {e}")
        return None

def main():
    while True:
        for tf in TIMEFRAMES:
            for symbol in SYMBOLS:
                signal = analyze_symbol(symbol, tf)
                if signal:
                    msg = f"⏱ *TRADER60 — {tf}*\n💹 *{symbol}*: {signal}"
                    send_telegram_message(msg)
                    print(msg)
        time.sleep(300)  # 5 dakika bekle

if __name__ == "__main__":
    main()
