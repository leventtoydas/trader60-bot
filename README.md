# TRADER60_FAILSAFE

**Amaç:** Railway ister `Procfile` ile, ister yanlışlıkla `python main.py` ile başlatsın — her iki durumda da sorunsuz çalışsın.

## Dosyalar
- `app.py` : FastAPI uygulaması (deploy'da Telegram bildirimi atar, /notify ve /health endpoint'leri var)
- `main.py`: Uvicorn'i programatik başlatan failsafe runner
- `Procfile`: Railway için standart başlatma komutu
- `requirements.txt`

## Kurulum
1) Bu dosyaları **boş** bir GitHub reposuna yükleyin.
2) Railway → New Project → Deploy from GitHub Repo.
3) Variables ekleyin:
```
TELEGRAM_TOKEN = <yeni token>
TELEGRAM_CHAT_ID = <doğru chat_id>
```
4) Rebuild without cache.

## Beklenenler
- Telegram'da: **“✅ TRADER60 — Deploy OK”**
- Manuel test: `.../notify`
- Loglarda:
```
[TG DEBUG] sendMessage status: 200
[TG DEBUG] sendMessage body: {'ok': True, ...}
```

Her ihtimale karşı hem `Procfile` hem de `main.py` mevcut olduğu için, Railway yanlış start komutunda bile sorunsuz açılır.
