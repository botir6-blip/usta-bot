import sqlite3
import sys

# UTF-8 kodlashini o'rnatish
sys.stdout.reconfigure(encoding='utf-8')

def cleanup_orphaned_ratings():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    print("=" * 60)
    print("🗑️ О'ЧИРИЛГАН УСТАЛАРНИНГ РЕЙТИНГЛАРINI TOZALASH")
    print("=" * 60)
    
    # O'chirilgan ustalarning reytinglarini topish
    c.execute("""
    SELECT r.master_id, COUNT(*) as count
    FROM ratings r
    LEFT JOIN masters m ON r.master_id = m.id
    WHERE m.id IS NULL
    GROUP BY r.master_id
    """)
    orphaned = c.fetchall()
    
    if orphaned:
        print(f"\n📊 {len(orphaned)} ta o'chirilgan ustaning reytinglari topildi:")
        total_deleted = 0
        
        for master_id, count in orphaned:
            print(f"   Master ID: {master_id} - {count} ta reyting")
            c.execute("DELETE FROM ratings WHERE master_id=?", (master_id,))
            total_deleted += count
        
        print(f"\n🗑️ Jami {total_deleted} ta reyting o'chirildi")
        conn.commit()
    else:
        print("\n✅ O'chirilgan ustalarning reytinglari yo'q")
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ TOZALASH TUGADI!")
    print("=" * 60)

if __name__ == "__main__":
    cleanup_orphaned_ratings()
