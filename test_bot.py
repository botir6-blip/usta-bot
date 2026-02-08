import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    from telegram import Update
    from telegram.ext import ApplicationBuilder
    print("✅ Telegram kutubxonasi o'rnatilgan")
except ImportError as e:
    print(f"❌ Telegram kutubxonasi xatolik: {e}")

try:
    import sqlite3
    conn = sqlite3.connect("usta.db")
    conn.close()
    print("✅ SQLite bazasi ishlaydi")
except Exception as e:
    print(f"❌ SQLite xatolik: {e}")

try:
    from services import SERVICES
    print(f"✅ Xizmatlar yuklandi: {len(SERVICES)} ta")
except Exception as e:
    print(f"❌ Services xatolik: {e}")

try:
    from regions import REGIONS
    print(f"✅ Viloyatlar yuklandi: {len(REGIONS)} ta")
except Exception as e:
    print(f"❌ Regions xatolik: {e}")

# Token tekshirish
TOKEN = "8561942994:AAE9L5BnSpyo5H5FVYQJQZpIP4Bt_K-YFO4"
print(f"🔑 Token: {TOKEN[:10]}...")

# Botni ishga tushirishga harakat
try:
    print("\n🤖 Botni ishga tushirishga harakat...")
    app = ApplicationBuilder().token(TOKEN).build()
    print("✅ Bot muvaffaqiyatli yaratildi!")
except Exception as e:
    print(f"❌ Bot yaratish xatolik: {e}")
    print("🔍 Token noto'g'ri bo'lishi mumkin!")

print("\n" + "="*50)
print("✅ TEST TUGADI")
print("="*50)
