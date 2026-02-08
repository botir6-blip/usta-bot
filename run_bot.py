import sys
import time
import os

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

print("🤖 Botni ishga tushirish...")

# Barcha jarayonlarni o'chirish
os.system("taskkill /f /im python.exe >nul 2>&1")
time.sleep(2)

print("✅ Barcha jarayonlar o'chirildi")

# Botni ishga tushirish
try:
    from bot import main
    print("🚀 Bot ishga tushirilmoqda...")
    main()
except KeyboardInterrupt:
    print("\n⏹️ Bot to'xtatildi")
except Exception as e:
    print(f"❌ Xatolik: {e}")
