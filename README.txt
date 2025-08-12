# TRADER60_DEBUG_Railway_v2

Bu paket Railway'e yüklediğinizde otomatik olarak Telegram hattını test eder.

## İçindekiler
- `app.py`: FastAPI uygulaması. Startup anında Telegram `getMe` ve `sendMessage` testlerini çalıştırır.
- `requirements.txt`
- `Procfile`
- `README.txt` (bu dosya)

## Çalışma Mantığı
Uygulama boot olur olmaz log'lara aşağıdaki satırları yazmaya çalışır:

```
[BOOT] CHAT_ID: 7881664904
[BOOT] TOKEN tail: ********
[TG DEBUG] getMe status: 200 ve ok: true
[TG DEBUG] status: 200 ve ok: true (sendMessage)
```

Telegram'da göreceğiniz mesaj:
```
✅ TRADER60 DEBUG — başlangıç testi (Markdown OFF).
```

## Railway Yükleme Adımları
1) Railway -> New Project -> Deploy from Repo **veya** `Upload` ile bu klasörün içeriğini yükle.
2) Variables:
```
TELEGRAM_TOKEN = 8294179459:AAGYg8wlZ0yz0YLAbBUGvT0kOBoJzHuq   # (pakete gömülü, isterseniz burada override edebilirsiniz)
TELEGRAM_CHAT_ID = 7881664904
```
3) **Rebuild without cache**.
4) Deploy log'larının son 30 satırında yukarıdaki çıktıları kontrol edin.
5) `/health` endpoint'i için "Open App" tıklayıp `.../health` deneyebilirsiniz.

## Notlar
- Token env'den gelirse onu kullanır; yoksa paket içine gömülü token'ı kullanır.
- Log satırlarında token güvenliği için gerçek token gösterilmez; sadece `********` yazılır.
