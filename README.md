# TRADER60_CLEAN_Railway (Env-only)

Bu repo *token gömmeden* çalışır. Tüm gizli bilgiler **environment variable** olarak geçilmeli.

## Gerekli Değişkenler
- TELEGRAM_TOKEN
- TELEGRAM_CHAT_ID

## Railway Adımları
1) New Project → Deploy from GitHub Repo
2) Variables:
```
TELEGRAM_TOKEN = <yeni token>
TELEGRAM_CHAT_ID = 7881664904
```
3) Rebuild without cache
4) Loglarda şu satırları gör:
```
[BOOT] CHAT_ID: 7881664904
[BOOT] TOKEN tail: ********
[TG DEBUG] getMe status: 200 ve ok: true
[TG DEBUG] status: 200 ve ok: true (sendMessage)
```
