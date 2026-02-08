import sqlite3
import json
import csv
import sys
from datetime import datetime

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

def backup_masters_to_json():
    """Ustalarni JSON fayliga saqlash"""
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    # Barcha ustalarni olish
    c.execute("""
    SELECT m.id, m.telegram_id, m.name, m.phone, m.service, 
           m.region, m.district, m.description,
           COUNT(r.rating) as rating_count,
           IFNULL(AVG(r.rating), 0) as avg_rating
    FROM masters m
    LEFT JOIN ratings r ON m.id = r.master_id
    GROUP BY m.id
    ORDER BY m.id
    """)
    
    masters = []
    for row in c.fetchall():
        master = {
            'id': row[0],
            'telegram_id': row[1],
            'name': row[2],
            'phone': row[3],
            'service': row[4],
            'region': row[5],
            'district': row[6],
            'description': row[7],
            'rating_count': row[8],
            'avg_rating': float(row[9])
        }
        masters.append(master)
    
    # Reytinglarni alohida olish
    ratings_data = {}
    c.execute("SELECT master_id, user_id, rating FROM ratings")
    for master_id, user_id, rating in c.fetchall():
        if master_id not in ratings_data:
            ratings_data[master_id] = []
        ratings_data[master_id].append({
            'user_id': user_id,
            'rating': rating
        })
    
    # JSON faylga saqlash
    backup_data = {
        'backup_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'total_masters': len(masters),
        'masters': masters,
        'ratings': ratings_data
    }
    
    filename = f"masters_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    
    conn.close()
    print(f"✅ {len(masters)} ta usta {filename} fayliga saqlandi")
    return filename

def backup_masters_to_csv():
    """Ustalarni CSV fayliga saqlash"""
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    # Barcha ustalarni olish
    c.execute("""
    SELECT m.id, m.telegram_id, m.name, m.phone, m.service, 
           m.region, m.district, m.description,
           COUNT(r.rating) as rating_count,
           IFNULL(AVG(r.rating), 0) as avg_rating
    FROM masters m
    LEFT JOIN ratings r ON m.id = r.master_id
    GROUP BY m.id
    ORDER BY m.id
    """)
    
    filename = f"masters_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header
        writer.writerow(['ID', 'Telegram ID', 'Ism', 'Telefon', 'Kasb', 
                        'Viloyat', 'Tuman', 'Izoh', 'Reytinglar soni', 'O\'rtacha reyting'])
        
        # Data
        for row in c.fetchall():
            writer.writerow(row)
    
    conn.close()
    print(f"✅ {c.rowcount} ta usta {filename} fayliga saqlandi")
    return filename

def restore_masters_from_json(filename):
    """JSON fayldan ustalarni tiklash"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        conn = sqlite3.connect("usta.db")
        c = conn.cursor()
        
        # Eski ma'lumotlarni o'chirish (ixtiyoriy)
        print("⚠️ Eski ma'lumotlar o'chirilmoqda...")
        c.execute("DELETE FROM ratings")
        c.execute("DELETE FROM masters")
        
        # Ustalarni tiklash
        masters = backup_data['masters']
        for master in masters:
            c.execute("""
            INSERT INTO masters (telegram_id, name, phone, service, region, district, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (master['telegram_id'], master['name'], master['phone'], 
                  master['service'], master['region'], master['district'], master['description']))
        
        # Reytinglarni tiklash
        ratings = backup_data['ratings']
        for master_id, rating_list in ratings.items():
            for rating_data in rating_list:
                # Yangi master_id ni topish
                c.execute("SELECT id FROM masters WHERE telegram_id=?", (rating_data['user_id'],))
                new_master_id = c.fetchone()[0]
                
                c.execute("INSERT INTO ratings (master_id, user_id, rating) VALUES (?, ?, ?)",
                         (new_master_id, rating_data['user_id'], rating_data['rating']))
        
        conn.commit()
        conn.close()
        
        print(f"✅ {len(masters)} ta usta va ularning reytinglari tiklandi")
        print(f"📅 Backup sanasi: {backup_data['backup_date']}")
        
    except Exception as e:
        print(f"❌ Xatolik: {e}")

def show_backup_info():
    """Backup fayllari haqida ma'lumot"""
    import os
    
    json_files = [f for f in os.listdir('.') if f.startswith('masters_backup_') and f.endswith('.json')]
    csv_files = [f for f in os.listdir('.') if f.startswith('masters_backup_') and f.endswith('.csv')]
    
    print("=" * 60)
    print("📁 BACKUP FAYLLARI")
    print("=" * 60)
    
    if json_files:
        print("\n📄 JSON fayllari:")
        for file in sorted(json_files):
            size = os.path.getsize(file) / 1024  # KB
            print(f"   {file} ({size:.1f} KB)")
    
    if csv_files:
        print("\n📊 CSV fayllari:")
        for file in sorted(csv_files):
            size = os.path.getsize(file) / 1024  # KB
            print(f"   {file} ({size:.1f} KB)")
    
    if not json_files and not csv_files:
        print("   Hech qanday backup fayli topilmadi")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    print("=" * 60)
    print("💾 УСТАЛАР БАЗАСИНИ BACKUP QILISH")
    print("=" * 60)
    
    print("\n1. JSON formatida backup qilish...")
    json_file = backup_masters_to_json()
    
    print("\n2. CSV formatida backup qilish...")
    csv_file = backup_masters_to_csv()
    
    print("\n3. Backup fayllari ro'yxati:")
    show_backup_info()
    
    print(f"\n✅ Backup tugadi!")
    print(f"📄 JSON: {json_file}")
    print(f"📊 CSV: {csv_file}")
    print("\n📝 Tiklash uchun: python backup_masters.py restore <filename.json>")
