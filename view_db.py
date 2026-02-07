import sqlite3
import sys

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

def view_database():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    print("=== USTALAR RO'YXATI ===")
    c.execute("SELECT id, name, phone, service, region, district FROM masters")
    masters = c.fetchall()
    
    for master in masters:
        print(f"ID: {master[0]}")
        print(f"Ismi: {master[1]}")
        print(f"Telefon: {master[2]}")
        print(f"Kasbi: {master[3]}")
        print(f"Viloyat: {master[4]}")
        print(f"Tuman: {master[5]}")
        print("-" * 30)
    
    print(f"\nJami ustalar soni: {len(masters)}")
    
    print("\n=== BAHOLAR ===")
    c.execute("SELECT COUNT(*) FROM ratings")
    rating_count = c.fetchone()[0]
    print(f"Jami baholar soni: {rating_count}")
    
    conn.close()

if __name__ == "__main__":
    view_database()
