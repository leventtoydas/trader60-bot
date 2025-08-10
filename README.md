# TRADER60 — Çoklu Varlık / Çoklu Periyot Telegram Sinyal Botu (Railway Ready)

Bu bot; **hisse, emtia, endeks, döviz, altın/gümüş, kripto** dahil çoklu varlıkları **5m, 15m, 30m, 1h, 4h** periyotlarında tarar.
Aşağıdaki sinyalleri üretir ve **Telegram** üzerinden gönderir:

- **AL**: *Kapanış ≤ Bollinger Alt Bandı* **ve** *RSI ≤ 30*
- **SAT**: *Kapanış ≥ Bollinger Üst Bandı* **ve** *RSI ≥ 70*
- Mesajda **EMA20/EMA50**, **MACD(12,26,9)**, **Bollinger(20,2)** bilgileri de yer alır.
- **Debounce**: Aynı (sembol, periyot, sinyal) kombinasyonu için varsayılan **60 dk** tekrar gönderim engeli.

> Varsayılan semboller: BIST (THYAO.IS, vb.), XU100, USDTRY, EURUSD, XAUUSD, XAGUSD, CL=F, BZ=F, ^GSPC, ^NDX, ^IXIC, ^GDAXI, ^FTSE, ^N225, BTC-USD, ETH-USD

---

## 1) Dosyalar
- `main.py` — Botun ana dosyası (APScheduler ile çoklu-periyot schedule)
- `requirements.txt` — Gerekli paketler
- `Procfile` — Railway başlatma komutu (`worker: python main.py`)
- `config.env` — Token/ID ve opsiyonel ayarlar (Railway ENV kullanmanız tavsiye edilir)

## 2) Hızlı Başlangıç (Lokal)
```bash
pip install -r requirements.txt
# config.env dosyasına TELEGRAM_TOKEN ve TELEGRAM_CHAT_ID yazın
python main.py
```

## 3) Railway’e Deploy (Adım Adım)
1. GitHub’da yeni bir repo açın ve bu dosyaları ekleyin (upload).
2. [railway.app](https://railway.app) → GitHub ile giriş → **New Project → Deploy from GitHub**.
3. Proje ayarlarında **Variables** kısmına aşağıdaki ortam değişkenlerini ekleyin:
   - `TELEGRAM_TOKEN` = (BotFather’dan aldığınız token)
   - `TELEGRAM_CHAT_ID` = (chat id’niz)
   - *(Opsiyonel)* `SYMBOLS` = Kendi sembolleriniz (virgülle)
   - *(Opsiyonel)* `TIMEFRAMES` = 5m,15m,30m,1h,4h
   - *(Opsiyonel)* `DEBOUNCE_MIN` = 60
4. **Deploy** butonuna basın. Loglarda `TRADER60 bot starting...` ve ardından `✅ TRADER60 bot başlatıldı.` göreceksiniz.
5. Telegram’da sinyaller gelmeye başlayacak. (İlk sinyal koşullar oluştuğunda gönderilir.)

## 4) Semboller ve Periyotlar
- Sembolleri `SYMBOLS` ENV değişkeninden yönetebilirsiniz (boşsa varsayılan set kullanılır).
- Periyotlar: `5m,15m,30m,1h,4h`. **4h** verisi için `60m` verisi çekilip 4 saatlik resampling yapılır.

## 5) Göstergeler ve Sinyal Kuralları
- RSI (14), Bollinger Bands (20, 2), EMA20/EMA50, MACD(12,26,9)
- **AL**: Close ≤ BB Lower AND RSI ≤ 30
- **SAT**: Close ≥ BB Upper AND RSI ≥ 70
- Ek güven puanı (⭐): EMA ve MACD uyuşursa artar (1–3 arası).

## 6) SSS
- **BIST sembolleri**: Yahoo Finance’da **.IS** uzantısı ile kullanılır (örn: `THYAO.IS`, `XU100.IS`).
- **Döviz/Metaller**: `USDTRY=X`, `EURUSD=X`, `XAUUSD=X`, `XAGUSD=X` vb.
- **Petrol**: WTI `CL=F`, Brent `BZ=F`.
- **Endeksler**: `^GSPC`, `^NDX`, `^IXIC`, `^GDAXI`, `^FTSE`, `^N225` vb.
- **Kripto**: `BTC-USD`, `ETH-USD`.
- **Zaman Dilimi**: Varsayılan `Europe/Istanbul`. `APP_TIMEZONE` ile değiştirebilirsiniz.

## 7) Notlar
- Railway’de Procfile zorunludur — bu repoda hazırdır.
- Aynı sinyalin spam olmaması için `DEBOUNCE_MIN` ile tekrar engeli mevcuttur.
- 4 saatlik periyot yfinance tarafından doğrudan sağlanmadığı için 60 dakikalık veriden **resample** edilir.

İyi kazançlar! 🚀
