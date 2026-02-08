import sqlite3
import sys

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

def test_rating_restore():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    print("=" * 50)
    print("🔄 РЕЙТИНГЛАРНИ ТИКЛАШ ТЕСТИРИ")
    print("=" * 50)
    
    # Test uchun usta ma'lumotlari
    test_telegram_id = 999999999
    test_name = "Тест Уста"
    test_phone = "+998900000000"
    test_service = "Электрик"
    test_region = "Тошкент"
    test_district = "Мирабад"
    test_description = "Тест устаси"
    
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
    """, (test_telegram_id, test_name, test_phone, test_service, test_region, test_district, test_description))
    
    master_id_1 = c.lastrowid
    print(f"   Yangi usta ID: {master_id_1}")
    
    # 3. Reytinglar qo'shish
    print("3. Рейтиглар қўшиш...")
    test_ratings = [(111, 5), (222, 4), (333, 3)]
    for user_id, rating in test_ratings:
        c.execute("INSERT INTO ratings (master_id, user_id, rating) VALUES (?, ?, ?)", (master_id_1, user_id, rating))
    conn.commit()
    
    # Reytinglarni tekshirish
    c.execute("SELECT COUNT(*), AVG(rating) FROM ratings WHERE master_id=?", (master_id_1,))
    rating_data = c.fetchone()
    print(f"   Рейтиглар: {rating_data[0]} та, ортача: {rating_data[1]:.1f}")
    
    # 4. Ikkinchi marta ro'yxatdan o'tkazish (test)
    print("4. Иккинчи мартта рўйхатдан ўтказиш (рейтигларни сақлаш)...")
    
    # add_master funksiyasini chaqirish
    def clean_text(text):
        import re
        text = re.sub(r'[^\w\s\u0400-\u04FF\-.,()]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    # add_master funksiyasini simulyatsiya qilish
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
        
        if old_master:
            old_master_id = old_master[0]
            # Eski ustani reytinglarini yangi ID bilan saqlab qolamiz
            c.execute(""" 
            UPDATE ratings 
            SET master_id = ?
            WHERE master_id = ?
            """, (old_master_id, old_master_id))
        
        # Yangi ustani qo'shamiz (yoki yangilaymiz)
        c.execute(""" 
        INSERT OR REPLACE INTO masters
        (telegram_id, name, phone, service, region, district, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (telegram_id, name, phone, service, region, district, description))
        
        # Agar eski usta bo'lsa, reytinglarni yangi ID bilan bog'lash
        if old_master:
            new_master_id = c.lastrowid  # Yangi qo'shilgan ustani ID si
            c.execute(""" 
            UPDATE ratings 
            SET master_id = ?
            WHERE master_id = ?
            """, (new_master_id, old_master_id))
        
        conn.commit()
        return True
    
    # Ikkinchi marta ro'yxatdan o'tkazish
    success = add_master(test_telegram_id, test_name + " 2", test_phone, test_service, test_region, test_district, test_description + " 2")
    print(f"   Ikkinchi ro'yxatdan o'tish muvaffaqiyati: {success}")
    
    # 5. Reytinglarni tekshirish
    print("5. Рейтигларни текшириш...")
    c.execute("SELECT COUNT(*), AVG(rating) FROM ratings WHERE master_id IN (SELECT id FROM masters WHERE telegram_id=?)", (test_telegram_id,))
    final_rating_data = c.fetchone()
    print(f"   Янги рейтиглар: {final_rating_data[0]} та, ортача: {final_rating_data[1]:.1f}")
    
    # 6. Tozalash
    print("6. Тест маълумотларини тозалаш...")
    c.execute("DELETE FROM masters WHERE telegram_id=?", (test_telegram_id,))
    c.execute("DELETE FROM ratings WHERE master_id IN (SELECT id FROM masters WHERE telegram_id=?)", (test_telegram_id,))
    conn.commit()
    
    conn.close()
    print("\n" + "=" * 50)
    print("✅ ТЕСТ ТУГАТИ!")
    print("=" * 50)

if __name__ == "__main__":
    test_rating_restore()
