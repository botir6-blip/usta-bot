import sqlite3
import sys

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

def debug_ratings():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    print("=" * 60)
    print("🔍 РЕЙТИНГЛАРНИ ТЕКШИРИШ")
    print("=" * 60)
    
    # Barcha reytinglarni ko'rish
    print("\n📊 БАРЧА РЕЙТИНГЛАР:")
    c.execute("""
    SELECT r.master_id, m.name, r.user_id, r.rating
    FROM ratings r
    JOIN masters m ON r.master_id = m.id
    ORDER BY r.master_id
    """)
    all_ratings = c.fetchall()
    
    for rating in all_ratings:
        master_id, master_name, user_id, rating_value = rating
        print(f"   Master ID: {master_id}, Ism: {master_name}, User ID: {user_id}, Rating: {rating_value}")
    
    # Top-10 ustalarni tekshirish
    print("\n🏆 ТОП-10 УСТАЛАР:")
    c.execute("""
    SELECT m.id, m.name, COUNT(r.rating) as rating_count, AVG(r.rating) as avg_rating
    FROM masters m
    LEFT JOIN ratings r ON m.id = r.master_id
    GROUP BY m.id
    HAVING COUNT(r.rating) > 0
    ORDER BY avg_rating DESC, rating_count DESC
    LIMIT 10
    """)
    top_masters = c.fetchall()
    
    for i, master in enumerate(top_masters, 1):
        master_id, master_name, rating_count, avg_rating = master
        print(f"   {i}. ID: {master_id}, Ism: {master_name}, Reytinglar: {rating_count}, Ortacha: {avg_rating:.1f}")
    
    # O'chirilgan ustalarni tekshirish
    print("\n🗑️ О'ЧИРИЛГАН УСТАЛАРНИНГ РЕЙТИНГЛАРИ:")
    c.execute("""
    SELECT r.master_id, r.user_id, r.rating
    FROM ratings r
    LEFT JOIN masters m ON r.master_id = m.id
    WHERE m.id IS NULL
    """)
    orphaned_ratings = c.fetchall()
    
    if orphaned_ratings:
        print("   О'CHIRILGAN USTALARNING REYTINGLARI:")
        for rating in orphaned_ratings:
            master_id, user_id, rating_value = rating
            print(f"   Master ID: {master_id} (usta o'chirilgan), User ID: {user_id}, Rating: {rating_value}")
    else:
        print("   О'chirilgan ustalarning reytinglari yo'q")
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ ТЕКШИРУВ ТУГАТИ!")
    print("=" * 60)

if __name__ == "__main__":
    debug_ratings()
