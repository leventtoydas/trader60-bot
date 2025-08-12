# TRADER60_CLEAN_DEPLOY

Sıfırdan kurulum için temiz paket. Token gömülü değildir. Railway deploy olur olmaz Telegram'a bildirim atar.

## Dosyalar
- app.py
- requirements.txt
- Procfile
- README.md

## Kurulum (GitHub + Railway)
1) Bu dosyaları boş bir GitHub repo'ya yükleyin.
2) Railway → New Project → Deploy from GitHub Repo.
3) Variables ekleyin:
```
TELEGRAM_TOKEN = <yeni token>
TELEGRAM_CHAT_ID = <doğru chat_id>
```
4) Rebuild without cache.
5) Deploy biter bitmez Telegram'da "✅ TRADER60 — Deploy OK" mesajını görürsünüz.
6) Manuel test: `.../notify` → bir bildirim daha gönderir.

## Notlar
- chat_id'yi doğrulamak için Telegram'da bota "ping" yazıp ardından `getUpdates` ile `message.chat.id` değerini alın.
- Log'larda `sendMessage status/body` satırları her şeyi açıkça gösterir.
