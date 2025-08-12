# TRADER60_DEPLOY_NOTIFY

Deploy olduğunda Telegram'a bildirim atar.

## Kurulum
1) Deploy from GitHub Repo veya Upload
2) Variables:
```
TELEGRAM_TOKEN = <yeni token>
TELEGRAM_CHAT_ID = <doğru chat_id>
```
3) Rebuild without cache
4) Deploy biter bitmez Telegram'da "✅ TRADER60 — Deploy OK" mesajını görmelisiniz.

## Manuel Test
`/notify` endpoint'ini açarak manuel bildirim gönderebilirsiniz.
