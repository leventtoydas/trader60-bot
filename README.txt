# TRADER60_DEBUG_Railway_v2

Bu paket Railway'e yüklediğinizde otomatik olarak Telegram hattını test eder.

## Railway Yükleme Adımları
1) Railway -> New Project -> Deploy from Repo veya Upload ile bu klasörün içeriğini yükleyin.
2) Variables:
```
TELEGRAM_TOKEN = 8294179459:AAH9416Z8a1U2xIORX8hJixGtixEDewYc7g
TELEGRAM_CHAT_ID = 7881664904
```
3) Rebuild without cache yapın.
4) Deploy log'larının son 30 satırında aşağıdaki çıktıları kontrol edin:
```
[BOOT] CHAT_ID: 7881664904
[BOOT] TOKEN tail: ********
[TG DEBUG] getMe status: 200 ve ok: true
[TG DEBUG] status: 200 ve ok: true (sendMessage)
```
Telegram'da şu mesajı görmelisiniz:
✅ TRADER60 DEBUG — başlangıç testi (Markdown OFF).
