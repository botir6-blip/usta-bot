import sqlite3
import sys

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

def test_unregister():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    print("=" * 60)
    print("🗑️ UNREGISTER FUNKSIYASINI TEST")
    print("=" * 60)
    
    # Test uchun telegram ID
    test_telegram_id = 999999999
    
    # 1. Test usta yaratamiz
    print("1. Test usta yaratamiz...")
    c.execute("""
        INSERT INTO masters (telegram_id, name, phone, service, region, district, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (test_telegram_id, "Test Usta", "+998900000000", "Электрик", "Тошкент", "Мирабад", "Test"))
    
    master_id = c.lastrowid
    print(f"   Usta ID: {master_id}")
    
    # 2. Reytinglar qo'shamiz
    print("2. Reytinglar qo'shamiz...")
    c.execute("INSERT INTO ratings (master_id, user_id, rating) VALUES (?, ?, ?)", (master_id, 111, 5))
    c.execute("INSERT INTO ratings (master_id, user_id, rating) VALUES (?, ?, ?)", (master_id, 222, 4))
    conn.commit()
    
    # Reytinglarni tekshirish
    c.execute("SELECT COUNT(*) FROM ratings WHERE master_id=?", (master_id,))
    rating_count = c.fetchone()[0]
    print(f"   Reytinglar: {rating_count} ta")
    
    # 3. delete_master funksiyasini chaqiramiz
    print("3. delete_master funksiyasini chaqiramiz...")
    
    def delete_master(telegram_id):
        conn = sqlite3.connect("usta.db")
        c = conn.cursor()

        # Avval ustani ID sini topamiz
        c.execute("SELECT id FROM masters WHERE telegram_id=?", (telegram_id,))
        master = c.fetchone()
        
        if master:
            master_id = master[0]
            # AVVAL reytinglarni o'chiramiz
            c.execute("DELETE FROM ratings WHERE master_id=?", (master_id,))
            deleted_ratings = c.rowcount
            # KEYIN ustani o'chiramiz
            c.execute("DELETE FROM masters WHERE telegram_id=?", (telegram_id,))
            deleted_master = c.rowcount
            print(f"   Usta o'chirildi: {deleted_master}, Reytinglar o'chirildi: {deleted_ratings}")
        
        conn.commit()
        conn.close()
        return master is not None
    
    success = delete_master(test_telegram_id)
    print(f"   Muvaffaqiyat: {success}")
    
    # 4. Natijani tekshirish
    print("4. Natijani tekshirish...")
    c.execute("SELECT COUNT(*) FROM masters WHERE telegram_id=?", (test_telegram_id,))
    master_exists = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM ratings WHERE master_id=?", (master_id,))
    ratings_exist = c.fetchone()[0]
    
    print(f"   Usta mavjud: {master_exists > 0}")
    print(f"   Reytinglar mavjud: {ratings_exist > 0}")
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ TEST TUGADI!")
    print("=" * 60)

if __name__ == "__main__":
    test_unregister()
