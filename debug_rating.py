import sqlite3
import sys

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

def debug_rating_restore():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    print("=" * 60)
    print("🔍 РЕЙТИНГЛАРНИ ТИКЛАШ ДЕБАГГИ")
    print("=" * 60)
    
    # Test uchun telegram ID
    test_telegram_id = 999999999
    
    # 1. Avval bazani tozalash
    print("1. Тест устани олиб ташлаш...")
    c.execute("DELETE FROM masters WHERE telegram_id=?", (test_telegram_id,))
    c.execute("DELETE FROM ratings WHERE master_id IN (SELECT id FROM masters WHERE telegram_id=?)", (test_telegram_id,))
    conn.commit()
    
    # 2. Birinchi marta ro'yxatdan o'tkazish
    print("2. Биринчи мартта рўйхатдан ўтказиш...")
    c.execute("""
        INSERT INTO masters (telegram_id, name, phone, service, region, district, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (test_telegram_id, "Тест Уста", "+998900000000", "Электрик", "Тошкент", "Мирабад", "Тест"))
    
    master_id_1 = c.lastrowid
    print(f"   1-usta ID: {master_id_1}")
    
    # 3. Reytinglar qo'shish
    print("3. Рейтиглар қўшиш...")
    c.execute("INSERT INTO ratings (master_id, user_id, rating) VALUES (?, ?, ?)", (master_id_1, 111, 5))
    c.execute("INSERT INTO ratings (master_id, user_id, rating) VALUES (?, ?, ?)", (master_id_1, 222, 4))
    c.execute("INSERT INTO ratings (master_id, user_id, rating) VALUES (?, ?, ?)", (master_id_1, 333, 3))
    conn.commit()
    
    # Reytinglarni tekshirish
    c.execute("SELECT COUNT(*), AVG(rating) FROM ratings WHERE master_id=?", (master_id_1,))
    rating_data = c.fetchone()
    print(f"   1-usta рейтиглари: {rating_data[0]} та, ортача: {rating_data[1]:.1f}")
    
    # 4. Ikkinchi marta ro'yxatdan o'tkazish (haqiqiy add_master funksiyasi)
    print("4. Иккинчи мартта рўйхатдан ўтказиш...")
    
    # clean_text funksiyasi
    def clean_text(text):
        import re
        text = re.sub(r'[^\w\s\u0400-\u04FF\-.,()]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    # Haqiqiy add_master funksiyasi
    def add_master(telegram_id, name, phone, service, region, district, description):
        name = clean_text(name) if name else ""
        phone = clean_text(phone) if phone else ""
        service = clean_text(service) if service else ""
        region = clean_text(region) if region else ""
        district = clean_text(district) if district else ""
        description = clean_text(description) if description else ""
        
        if not name or not phone or not service or not region or not district:
            return False
        
        # Avval eski ustani ID sini topamiz
        c.execute("SELECT id FROM masters WHERE telegram_id=?", (telegram_id,))
        old_master = c.fetchone()
        
        print(f"   Eski usta: {old_master}")
        
        # Yangi ustani qo'shamiz (yoki yangilaymiz)
        c.execute(""" 
        INSERT OR REPLACE INTO masters
        (telegram_id, name, phone, service, region, district, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (telegram_id, name, phone, service, region, district, description))
        
        new_master_id = c.lastrowid
        print(f"   Yangi usta ID: {new_master_id}")
        
        # Agar eski usta bo'lsa, reytinglarni yangi ID bilan bog'lash
        if old_master:
            old_master_id = old_master[0]
            print(f"   Eski ID: {old_master_id} -> Yangi ID: {new_master_id}")
            
            # UPDATE dan oldin reytinglarni ko'rish
            c.execute("SELECT COUNT(*) FROM ratings WHERE master_id=?", (old_master_id,))
            old_ratings = c.fetchone()[0]
            print(f"   Eski reytinglar soni: {old_ratings}")
            
            c.execute(""" 
            UPDATE ratings 
            SET master_id = ?
            WHERE master_id = ?
            """, (new_master_id, old_master_id))
            
            # UPDATE dan keyin reytinglarni ko'rish
            c.execute("SELECT COUNT(*) FROM ratings WHERE master_id=?", (new_master_id,))
            new_ratings = c.fetchone()[0]
            print(f"   Yangi reytinglar soni: {new_ratings}")
        
        conn.commit()
        return True
    
    # Ikkinchi marta ro'yxatdan o'tkazish
    success = add_master(test_telegram_id, "Тест Уста 2", "+998900000001", "Сантехник", "Тошкент", "Чилонзор", "Тест 2")
    print(f"   Ikkinchi ro'yxatdan o'tish: {success}")
    
    # 5. Natijalarni tekshirish
    print("5. НАТИЖАЛАРНИ ТЕКШИРИШ...")
    
    # Barcha test ustalarni ko'rish
    c.execute("SELECT id, telegram_id, name FROM masters WHERE telegram_id=? ORDER BY id", (test_telegram_id,))
    test_masters = c.fetchall()
    print("   Тест усталар:")
    for master in test_masters:
        c.execute("SELECT COUNT(*), AVG(rating) FROM ratings WHERE master_id=?", (master[0],))
        ratings = c.fetchone()
        avg_rating = f"{ratings[1]:.1f}" if ratings[1] else "0"
        print(f"     ID: {master[0]}, Ism: {master[2]}, Reytinglar: {ratings[0]} та, ортача: {avg_rating}")
    
    # 6. Tozalash
    print("6. Тозалаш...")
    c.execute("DELETE FROM masters WHERE telegram_id=?", (test_telegram_id,))
    c.execute("DELETE FROM ratings WHERE master_id IN (SELECT id FROM masters WHERE telegram_id=?)", (test_telegram_id,))
    conn.commit()
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ ДЕБАГ ТУГАТИ!")
    print("=" * 60)

if __name__ == "__main__":
    debug_rating_restore()
