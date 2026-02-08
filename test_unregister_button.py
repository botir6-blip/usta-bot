import sqlite3
import sys

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

def test_unregister_button():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    print("=" * 60)
    print("🗑️ РУЙХАТДАН ЧИҚИШ ТЕСТИ")
    print("=" * 60)
    
    # Sizning telegram ID ni topish (oxirgi usta)
    c.execute("SELECT telegram_id, name FROM masters ORDER BY id DESC LIMIT 1")
    last_master = c.fetchone()
    
    if last_master:
        telegram_id, name = last_master
        print(f"Текширилаётган usta: {name} (ID: {telegram_id})")
        
        # Avval reytinglarni ko'rish
        c.execute("SELECT id FROM masters WHERE telegram_id=?", (telegram_id,))
        master = c.fetchone()
        
        if master:
            master_id = master[0]
            c.execute("SELECT COUNT(*) FROM ratings WHERE master_id=?", (master_id,))
            rating_count = c.fetchone()[0]
            print(f"   Reytinglar: {rating_count} ta")
            
            # delete_master funksiyasini chaqirish
            def delete_master(telegram_id):
                conn = sqlite3.connect("usta.db")
                c = conn.cursor()

                c.execute("SELECT id FROM masters WHERE telegram_id=?", (telegram_id,))
                master = c.fetchone()
                
                if master:
                    master_id = master[0]
                    c.execute("DELETE FROM ratings WHERE master_id=?", (master_id,))
                    deleted_ratings = c.rowcount
                    c.execute("DELETE FROM masters WHERE telegram_id=?", (telegram_id,))
                    deleted_master = c.rowcount
                    print(f"   Уста о'чирилди: {deleted_master}, Reytinglar о'чирилди: {deleted_ratings}")
                
                conn.commit()
                conn.close()
                return master is not None
            
            success = delete_master(telegram_id)
            print(f"   Muvaffaqiyat: {success}")
            
            # Natijani tekshirish
            c.execute("SELECT COUNT(*) FROM masters WHERE telegram_id=?", (telegram_id,))
            master_exists = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM ratings WHERE master_id=?", (master_id,))
            ratings_exist = c.fetchone()[0]
            
            print(f"   Уста мавжуд: {master_exists > 0}")
            print(f"   Reytinglar мавжуд: {ratings_exist > 0}")
        else:
            print("   Usta topilmadi")
    else:
        print("   Базада usta yo'q")
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ TEST TUGADI!")
    print("=" * 60)

if __name__ == "__main__":
    test_unregister_button()
