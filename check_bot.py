import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    print("1. Modullarni tekshirish...")
    import sqlite3
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
    from services import SERVICES
    from regions import REGIONS
    print("✅ Barcha modullar yuklandi")
    
    print("2. Token tekshirish...")
    TOKEN = "7573364452:AAFW1F3ax2HwSGOiULbk0xAEhBs-_vqmOhE"
    app = ApplicationBuilder().token(TOKEN).build()
    print("✅ Token to'g'ri")
    
    print("3. Baza tekshirish...")
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM masters")
    masters_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM ratings")
    ratings_count = c.fetchone()[0]
    conn.close()
    print(f"✅ Baza: {masters_count} usta, {ratings_count} reyting")
    
    print("4. Bot modulini tekshirish...")
    from bot import main
    print("✅ Bot moduli yuklandi")
    
    print("\n🚀 Botni ishga tushirish...")
    main()
    
except Exception as e:
    print(f"❌ Xatolik: {e}")
    import traceback
    traceback.print_exc()
