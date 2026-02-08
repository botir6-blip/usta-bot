import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    print("1. Bot modulini yuklash...")
    from bot import init_db, main
    print("✅ Modul yuklandi")
    
    print("2. Bazani ishga tushirish...")
    init_db()
    print("✅ Baza tayyor")
    
    print("3. Botni ishga tushirish...")
    main()
    
except Exception as e:
    print(f"❌ Xatolik: {e}")
    import traceback
    traceback.print_exc()
