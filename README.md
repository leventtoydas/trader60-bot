# TRADER60_ANALYTICS_DAILY

Günlük (09:30 Europe/Istanbul) teknik analiz üretir ve Telegram'a gönderir.
- SMA(8/20/50/200), RSI(14), MACD sinyalleri
- Hisse/Endeks/Emtia listeleri ENV'den özelleştirilebilir
- Manuel tetik: `/run-now`

## ENV
```
TELEGRAM_TOKEN=<zorunlu>
TELEGRAM_CHAT_ID=<zorunlu>
TIMEZONE=Europe/Istanbul
RUN_HOUR=9
RUN_MINUTE=30
STOCKS_CSV=THYAO.IS,TOASO.IS,GUBRF.IS,ENKAI.IS,TUPRS.IS,ULKER.IS,KCHOL.IS,ASELS.IS
INDICES_CSV=^XU100,^BIST30,^GSPC,^NDX,^DJI
COMMODS_CSV=XAUUSD=X,EURUSD=X,USDTRY=X,BZ=F,CL=F,BTC-USD
```

## Deploy
1) Repo'ya yükleyin, Railway'de env'leri girin.
2) Rebuild without cache.
3) Telegram'da deploy bildirimi görünür.
4) Hemen test için `.../run-now` çağırın.
