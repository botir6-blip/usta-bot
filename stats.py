import sqlite3
import sys
from datetime import datetime

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

def show_detailed_stats():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    print("=" * 50)
    print("📊 БОТНИНГИ ТОЛИК СТАТИСТИКАСИ")
    print("=" * 50)
    
    # Jami foydalanuvchilar
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    print(f"👥 Жами фойдаланувчилар: {total_users}")
    
    # Bugungi faol foydalanuvchilar
    c.execute("SELECT COUNT(*) FROM users WHERE DATE(last_active) = DATE('now')")
    today_users = c.fetchone()[0]
    print(f"📅 Бугунги фаоллар: {today_users}")
    
    # Oxirgi 7 kunlik faol foydalanuvchilar
    c.execute("SELECT COUNT(*) FROM users WHERE DATE(last_active) >= DATE('now', '-7 days')")
    week_users = c.fetchone()[0]
    print(f"📆 Охирги 7 кун: {week_users} фаол")
    
    # Jami ustalar
    c.execute("SELECT COUNT(*) FROM masters")
    total_masters = c.fetchone()[0]
    print(f"👷 Жами усталар: {total_masters}")
    
    # Jami baholar
    c.execute("SELECT COUNT(*) FROM ratings")
    total_ratings = c.fetchone()[0]
    print(f"⭐ Жами бахолар: {total_ratings}")
    
    # Касблар бўйича усталар
    print("\n🛠️ Касблар бўйича усталар:")
    c.execute("""
        SELECT service, COUNT(*) as count 
        FROM masters 
        GROUP BY service 
        ORDER BY count DESC
    """)
    for service, count in c.fetchall():
        print(f"   • {service}: {count} та")
    
    # Вилоятлар бўйича усталар
    print("\n📍 Вилоятлар бўйича усталар:")
    c.execute("""
        SELECT region, COUNT(*) as count 
        FROM masters 
        GROUP BY region 
        ORDER BY count DESC
    """)
    for region, count in c.fetchall():
        print(f"   • {region}: {count} та")
    
    # Охирги 10 та фойдalanuvchi
    print("\n👤 Охирги 10 та фойдаланувчи:")
    c.execute("""
        SELECT username, first_name, last_name, join_date, last_active, message_count 
        FROM users 
        ORDER BY last_active DESC 
        LIMIT 10
    """)
    for i, (username, first_name, last_name, join_date, last_active, msg_count) in enumerate(c.fetchall(), 1):
        name = f"{first_name or ''} {last_name or ''}".strip()
        username = f"@{username}" if username else "username йўқ"
        print(f"   {i}. {name} ({username}) - {msg_count} хабар")
    
    # Охирги 10 та бахо
    print("\n⭐ Охирги 10 та бахо:")
    c.execute("""
        SELECT r.master_id, r.user_id, r.rating, u.first_name, m.name as master_name
        FROM ratings r
        JOIN users u ON r.user_id = u.telegram_id
        JOIN masters m ON r.master_id = m.id
        ORDER BY ROWID DESC
        LIMIT 10
    """)
    for i, (master_id, user_id, rating, user_name, master_name) in enumerate(c.fetchall(), 1):
        print(f"   {i}. {user_name} → {master_name}: {rating} ⭐")
    
    conn.close()
    print("\n" + "=" * 50)

if __name__ == "__main__":
    show_detailed_stats()
