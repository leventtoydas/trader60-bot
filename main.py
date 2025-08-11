import os, requests, sys, json

TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def die(msg):
    print(msg)
    sys.exit(1)

# 1) Env doğrula (maskeli yazdır)
if not TOKEN or not CHAT_ID:
    die("[FATAL] TELEGRAM_TOKEN veya TELEGRAM_CHAT_ID boş!")
print("[INFO] TOKEN: ****" + (TOKEN[-8:] if len(TOKEN) >= 8 else TOKEN))
print("[INFO] CHAT_ID:", CHAT_ID)

# 2) /getMe ile token geçerli mi?
r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=20)
print("[DEBUG] getMe status:", r.status_code)
try:
    print("[DEBUG] getMe resp:", r.json())
except Exception:
    print("[DEBUG] getMe text:", r.text)

if r.status_code != 200 or not r.json().get("ok"):
    die("[FATAL] Token geçersiz görünüyor (getMe ok=false).")

# 3) Test mesajı gönder
payload = {
    "chat_id": CHAT_ID,
    "text": "✅ Telegram testi: TRADER60 bot Railway'de aktif.",
    "parse_mode": "Markdown"
}
s = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json=payload, timeout=20)
print("[DEBUG] sendMessage status:", s.status_code)
try:
    print("[DEBUG] sendMessage resp:", json.dumps(s.json(), ensure_ascii=False))
except Exception:
    print("[DEBUG] sendMessage text:", s.text)

if s.status_code != 200 or not s.json().get("ok"):
    die("[FATAL] sendMessage başarısız. CHAT_ID doğru mu? Bota /start attın mı?")

print("[OK] Telegram testi başarılı. Artık ana bota geçebiliriz.")
