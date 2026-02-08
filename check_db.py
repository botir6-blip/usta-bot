import sqlite3
import sys

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

def check_database():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    print("=" * 50)
    print("🔍 БАЗА ТУЗИЛИШИ")
    print("=" * 50)
    
    # Jadval tuzilishini tekshirish
    print("\n📋 MASTERS жадвали:")
    c.execute("PRAGMA table_info(masters)")
    columns = c.fetchall()
    for col in columns:
        print(f"   {col[1]} - {col[2]}")
    
    print("\n📋 RATINGS жадвали:")
    c.execute("PRAGMA table_info(ratings)")
    columns = c.fetchall()
    for col in columns:
        print(f"   {col[1]} - {col[2]}")
    
    # Oxirgi ustani ko'rish
    print("\n👤 Охирги 5 та уста:")
    c.execute("SELECT id, telegram_id, name FROM masters ORDER BY id DESC LIMIT 5")
    masters = c.fetchall()
    for master in masters:
        print(f"   ID: {master[0]}, Telegram ID: {master[1]}, Ism: {master[2]}")
    
    # Oxirgi reytinglarni ko'rish
    print("\n⭐ Охирги 5 та рейтиг:")
    c.execute("SELECT master_id, user_id, rating FROM ratings ORDER BY ROWID DESC LIMIT 5")
    ratings = c.fetchall()
    for rating in ratings:
        print(f"   Master ID: {rating[0]}, User ID: {rating[1]}, Rating: {rating[2]}")
    
    conn.close()
    print("\n" + "=" * 50)

if __name__ == "__main__":
    check_database()
