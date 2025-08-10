import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def get_signal(symbol, interval):
    df = yf.download(symbol, period="7d", interval=interval)
    if df.empty or len(df) < 14:
        return None

    df['RSI'] = compute_rsi(df['Close'], 14)
    last_rsi = df['RSI'].iloc[-1]

    if last_rsi > 70:
        return f"{symbol} ({interval}) → **Aşırı Alış** (RSI: {last_rsi:.2f})"
    elif last_rsi < 30:
        return f"{symbol} ({interval}) → **Aşırı Satış** (RSI: {last_rsi:.2f})"
    else:
        return f"{symbol} ({interval}) → Nötr (RSI: {last_rsi:.2f})"

def compute_rsi(series, period):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def main():
    symbol = "BTC-USD"
    intervals = ["5m", "15m", "30m", "1h", "4h"]

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    message = f"⏱ *BTC Sinyal Raporu* — {now}\n\n"

    for interval in intervals:
        signal = get_signal(symbol, interval)
        if signal:
            message += f"{signal}\n"

    send_telegram_message(message)

if __name__ == "__main__":
    main()