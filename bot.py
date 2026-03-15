import psycopg2
import os
import requests
from location_utils import find_region, find_district
from services import SERVICES
from regions import REGIONS
from languages import LANGUAGES, get_texts, LANGUAGE_NAMES
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters)

def get_connection():
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        sslmode="require"
    )
    
ADMIN_ID = 1970756498

TOKEN = os.getenv("TOKEN")

def ensure_code_column():
    print("🔍 ensure_code_column ишлаяпти...")

    conn = get_connection()
    c = conn.cursor()

    # code устуни борми текшириш
    c.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='masters' AND column_name='code';
    """)

    exists = c.fetchone()

    if exists:
        print("✅ code устуни аллақачон бор")
    else:
        print("⚙ code устуни яратиляпти...")
        c.execute("ALTER TABLE masters ADD COLUMN code VARCHAR(4);")
        c.execute("ALTER TABLE masters ADD CONSTRAINT unique_master_code UNIQUE (code);")
        print("✅ code устуни яратилди")

    conn.commit()
    conn.close()

import random

def generate_unique_code(cursor):
    for _ in range(1000):
        code = str(random.randint(1000, 9999))
        cursor.execute("SELECT 1 FROM masters WHERE code = %s", (code,))
        if not cursor.fetchone():
            return code

    raise Exception("Бўш код топилмади")
    
# ================= DATABASE =================
def init_db():
    conn = get_connection()
    c = conn.cursor()

    # ====== USTALAR ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS masters(id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE,
        name TEXT,
        phone TEXT,
        service TEXT,
        region TEXT,
        district TEXT,
        age TEXT,
        experience TEXT,
        education TEXT,
        skills TEXT,
        code VARCHAR(4) UNIQUE
    )
    """)

    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS vip BOOLEAN DEFAULT FALSE")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS vip_until TIMESTAMP")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS service_description VARCHAR(300)")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS is_busy BOOLEAN DEFAULT FALSE")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS busy_until DATE")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS points INTEGER DEFAULT 0")
       
    # ====== BAHOLAR ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS ratings (
        id SERIAL PRIMARY KEY,
        master_id INTEGER,
        user_id BIGINT,
        rating INTEGER
    )
    """)
    c.execute("ALTER TABLE ratings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    c.execute("ALTER TABLE ratings ADD COLUMN IF NOT EXISTS comment TEXT")
    c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_rating ON ratings(master_id, user_id)""")

    # ====== FOYDALANUVCHILAR ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        telegram_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TIMESTAMP,
        last_active TIMESTAMP,
        message_count INTEGER DEFAULT 0
    )
    """)

    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS points INTEGER DEFAULT 0")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT")

    # ====== BUYURTMALAR ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        master_id INTEGER,
        status TEXT DEFAULT 'new',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("ALTER TABLE masters ALTER COLUMN telegram_id TYPE BIGINT")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT")
    
    # ====== POINT TRADES ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS point_trades(
        id SERIAL PRIMARY KEY,
        seller_id BIGINT,
        buyer_id BIGINT,
        points INTEGER,
        status TEXT DEFAULT 'open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# ================= USTA QO‘SHISH =================
def add_master(telegram_id, name, phone, service, region, district, age=None, experience=None, service_description=None):
    import psycopg2, os

    conn = get_connection()
    c = conn.cursor()

    # 🔎 Аввал код борми текшириш
    c.execute("SELECT code FROM masters WHERE telegram_id = %s", (telegram_id,))
    existing = c.fetchone()

    if existing:
        code = existing[0]  # эски кодни оламиз
    else:
        code = generate_unique_code(c)  # янги код яратамиз

    c.execute("""
    INSERT INTO masters 
    (telegram_id, name, phone, service, region, district, age, experience, code, service_description)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (telegram_id)
    DO UPDATE SET
        name = EXCLUDED.name,
        phone = EXCLUDED.phone,
        service = EXCLUDED.service,
        region = EXCLUDED.region,
        district = EXCLUDED.district,
        age = EXCLUDED.age,
        experience = EXCLUDED.experience,
        service_description = EXCLUDED.service_description,
        is_active = TRUE
    """, (
        telegram_id, name, phone, service, region, district, age, experience, code, service_description
    ))

    conn.commit()
    conn.close()

# ================= RO‘YXATDAN CHIQАРИШ (SOFT DELETE) =================
def delete_master(telegram_id):
    conn = get_connection()
    c = conn.cursor()

    # Уста мавжудми текширамиз
    c.execute("SELECT id FROM masters WHERE telegram_id=%s", (telegram_id,))
    master = c.fetchone()

    if master:
        master_id = master[0]

        # ❗ Энди ўчирмаймиз, фақат фаол эмас қиламиз
        c.execute("""
            UPDATE masters
            SET is_active = FALSE
            WHERE telegram_id = %s
        """, (telegram_id,))

        print(f"Usta {master_id} soft delete qilindi (is_active=FALSE)")

    conn.commit()
    conn.close()
    return master is not None

def get_service_counts():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT service, COUNT(*)
        FROM masters
        WHERE is_active = TRUE
        GROUP BY service
    """)

    rows = c.fetchall()
    conn.close()

    return dict(rows)


def get_region_counts(service):

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT region, COUNT(*)
        FROM masters
        WHERE service = %s
        AND is_active = TRUE
        GROUP BY region
    """, (service,))

    rows = c.fetchall()
    conn.close()

    return dict(rows)

def get_district_counts(region, service):

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT district, COUNT(*)
        FROM masters
        WHERE region = %s
        AND service = %s
        AND is_active = TRUE
        GROUP BY district
    """, (region, service))

    rows = c.fetchall()
    conn.close()

    return dict(rows)

def build_service_menu(language="uz_kr", sort_by_count=True):

    services = SERVICES.get(language, SERVICES["uz_kr"])
    counts = get_service_counts()

    services_with_counts = []

    for service in services:
        uz_service = map_service_to_uzkr(service)
        count = counts.get(uz_service, 0)

        services_with_counts.append((service, count))

    # 🔥 Фақат FIND режимда сортировка
    if sort_by_count:
        services_with_counts.sort(key=lambda x: x[1], reverse=True)

    keyboard = []
    row = []

    for i, (service, count) in enumerate(services_with_counts, 1):

        row.append(f"{service} ({count})")

        if i % 2 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    back_text = "Орқага" if language == "uz_kr" else "Orqaga" if language == "uz_lt" else "Назад"
    keyboard.append([back_text])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
def build_region_menu(service, language="uz_kr", hide_empty=False):

    regions = REGIONS.get(language, REGIONS["uz_kr"])

    uz_service = map_service_to_uzkr(service)

    counts = get_region_counts(uz_service)

    region_list = []

    for region in regions.keys():

        uz_region = map_region_to_uzkr(region)

        count = counts.get(uz_region, 0)

        # 🔥 фақат hide_empty бўлса яширади
        if hide_empty and count == 0:
            continue

        region_list.append((region, count))

    region_list.sort(key=lambda x: x[1], reverse=True)

    keyboard = []
    row = []

    for i, (region, count) in enumerate(region_list, 1):

        row.append(f"{region} ({count})")

        if i % 3 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    back_text = "Орқага" if language == "uz_kr" else "Orqaga" if language == "uz_lt" else "Назад"

    keyboard.append([back_text])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
# ================= MAPPING =================
def map_region_to_uzkr(selected_region):
    # agar allaqachon uz kr bo‘lsa
    if selected_region in REGIONS["uz_kr"]:
        return selected_region

    # boshqa tillardan qidiramiz
    for uz_region in REGIONS["uz_kr"]:
        for lang in ["uz_lt", "ru"]:
            if selected_region == list(REGIONS[lang].keys())[list(REGIONS["uz_kr"].keys()).index(uz_region)]:
                return uz_region

    return selected_region


def map_district_to_uzkr(selected_region, selected_district):
    uz_region = map_region_to_uzkr(selected_region)

    uz_districts = REGIONS["uz_kr"].get(uz_region, [])

    # agar allaqachon uz kr bo‘lsa
    if selected_district in uz_districts:
        return selected_district

    for lang in ["uz_lt", "ru"]:
        other_region = list(REGIONS[lang].keys())[list(REGIONS["uz_kr"].keys()).index(uz_region)]
        other_districts = REGIONS[lang].get(other_region, [])

        if selected_district in other_districts:
            index = other_districts.index(selected_district)
            return uz_districts[index]

    return selected_district
def map_service_to_uzkr(selected_service):
    uz_services = SERVICES["uz_kr"]

    if selected_service in uz_services:
        return selected_service

    for lang in ["uz_lt", "ru"]:
        other_services = SERVICES.get(lang, [])
        if selected_service in other_services:
            index = other_services.index(selected_service)
            return uz_services[index]

    return selected_service
    
# ===========================================
def build_city_menu(region, service, language="uz_kr", hide_empty=False):

    regions_data = REGIONS.get(language, REGIONS["uz_kr"])
    cities = regions_data.get(region, [])

    uz_region = map_region_to_uzkr(region)
    uz_service = map_service_to_uzkr(service)

    counts = get_district_counts(uz_region, uz_service)

    # 🔥 CITY + COUNT LIST
    city_list = []

    for city in cities:
        uz_city = map_district_to_uzkr(region, city)
        count = counts.get(uz_city, 0)

        # 🔥 0 та устали туманни чиқармаймиз
        if hide_empty and count == 0:
            continue

        city_list.append((city, count))

    # 🔥 ENG KO‘P USTADAN BOSHLAB SORT
    city_list.sort(key=lambda x: x[1], reverse=True)

    keyboard = []
    row = []

    for i, (city, count) in enumerate(city_list, 1):

        row.append(f"{city} ({count})")

        if i % 3 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    back_text = "Орқага" if language == "uz_kr" else "Orqaga" if language == "uz_lt" else "Назад"
    keyboard.append([back_text])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
# ================= TIL TANLASH =================
def build_language_menu():
    keyboard = []

    for lang in LANGUAGES:
        keyboard.append([LANGUAGES[lang]])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Til tanlash"""

    text = update.message.text

    language = None
    for lang_code, lang_name in LANGUAGES.items():
        if text == lang_name:
            language = lang_code
            break

    if language:

        # 🔹 Контекстни тозалаймиз
        context.user_data.pop("flow", None)
        context.user_data.pop("step", None)
        context.user_data.pop("page", None)
        context.user_data["language"] = language

        texts = get_texts(language)

        # 🔹 Базага сақлаймиз
        conn = get_connection()
        c = conn.cursor()

        c.execute("""
            UPDATE users
            SET language=%s
            WHERE telegram_id=%s
        """, (language, update.effective_user.id))

        # 🔹 Устами ёки мижоз
        c.execute("""
            SELECT 1 FROM masters
            WHERE telegram_id=%s AND is_active=TRUE
        """, (update.effective_user.id,))

        is_master = c.fetchone() is not None

        conn.commit()
        conn.close()

        menu, mode = build_main_menu(texts, is_master, context.user_data.get("mode"))
        context.user_data["mode"] = mode

        await update.message.reply_text(texts["welcome"], reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True))

    else:
        await update.message.reply_text("Илтимос, тилни танланг:", reply_markup=build_language_menu())
        
# ================= FOYDALANUVCHI QO'SHISH =================
def log_user(user):
    from datetime import datetime, timezone

    print("LOGGING USER:", user.id)

    conn = get_connection()
    c = conn.cursor()

    now = datetime.now(timezone.utc)

    c.execute("""
    INSERT INTO users (telegram_id, username, first_name, last_name, join_date, last_active, message_count)
    VALUES (%s, %s, %s, %s, %s, %s, 1)
    ON CONFLICT (telegram_id)
    DO UPDATE SET
        last_active = EXCLUDED.last_active,
        message_count = users.message_count + 1
    """, (
        user.id,
        user.username,
        user.first_name,
        user.last_name,
        now,
        now
    ))

    conn.commit()
    conn.close()

    print("USER SAVED")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user(update.effective_user)

    user_id = update.effective_user.id

    # 🌐 Агар тил бўлмаса default қиламиз
    language = context.user_data.get("language", "uz_kr")
    context.user_data["language"] = language
    texts = get_texts(language)

    # 🔥 РЕФЕРАЛ ЛОГИКА
    conn = get_connection()
    c = conn.cursor()

    # Фойдаланувчи бор-йўқлигини текшириш
    c.execute("SELECT referred_by FROM users WHERE telegram_id=%s", (user_id,))
    row = c.fetchone()

    if row and row[0] is None and context.args:
        # Янги фойдаланувчи
        referred_by = None

        if context.args:
            ref_code = context.args[0]

            if ref_code.isdigit():
                ref_id = int(ref_code)

                if ref_id != user_id:
                    referred_by = ref_id

                    # 🔎 таклиф қилган одам уста ёки йўқлигини текширамиз
                    c.execute("""
                        SELECT 1 FROM masters
                        WHERE telegram_id=%s AND is_active=TRUE
                    """, (ref_id,))

                    is_master = c.fetchone() is not None

                    bonus = 300 if is_master else 100

                    c.execute("""
                        UPDATE users
                        SET points = COALESCE(points,0) + %s
                        WHERE telegram_id=%s
                    """, (bonus, ref_id))

        # Янги фойдаланувчини қўшиш
        c.execute("""
            UPDATE users
            SET referred_by=%s
            WHERE telegram_id=%s
        """, (referred_by, user_id))

        conn.commit()

    conn.close()

    # 👇 МЕНЮ ТАНЛАШ
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT 1 FROM masters
        WHERE telegram_id=%s AND is_active=TRUE
    """, (user_id,))

    is_master = c.fetchone() is not None
    conn.close()

    menu, mode = build_main_menu(texts, is_master, context.user_data.get("mode"))

    context.user_data["mode"] = mode
        
    await update.message.reply_text(texts["welcome"], reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    # 🔥 message ni aniqlaymiz
    if update.callback_query:
        message = update.callback_query.message
    else:
        message = update.message

    conn = get_connection()
    c = conn.cursor()

    # 🔧 Усталар тури
    c.execute("""
    SELECT service, COUNT(*)
    FROM masters
    WHERE is_active = TRUE 
    AND service IS NOT NULL
    GROUP BY service
    ORDER BY COUNT(*) DESC
    """)

    services = c.fetchall()

    service_stats = "\n🔧 Усталар тури:\n\n"

    if not services:
        service_stats += "Маълумот йўқ\n"
    else:
        for s in services:
            service_stats += f"{s[0]} — {s[1]}\n"

    # 📍 Вилоятлар бўйича фойдаланувчилар
    c.execute("""
    SELECT region, COUNT(*)
    FROM masters
    WHERE is_active = TRUE
    GROUP BY region
    ORDER BY COUNT(*) DESC
    """)

    regions = c.fetchall()

    region_stats = "\n📍 Усталар (вилоят):\n\n"

    for r in regions:
        region_stats += f"{r[0]} — {r[1]}\n"

    # ====== УМУМИЙ ======
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM masters WHERE is_active=TRUE")
    total_masters = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM masters WHERE vip=TRUE AND is_active=TRUE")
    vip_masters = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM ratings")
    total_ratings = c.fetchone()[0]

    # ====== 24 СОАТ ======
    c.execute("SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '24 HOURS'")
    new_users_24h = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM orders WHERE created_at >= NOW() - INTERVAL '24 HOURS'")
    orders_24h = c.fetchone()[0]

    # ====== ЭНГ ФАОЛ УСТА ======
    c.execute("""
        SELECT m.name, m.code, COUNT(o.id) as total
        FROM masters m
        LEFT JOIN orders o ON m.id = o.master_id
        WHERE m.is_active=TRUE
        GROUP BY m.name, m.code
        ORDER BY total DESC
        LIMIT 1
    """)
    top_master = c.fetchone()

    conn.close()

    text = f"""
    🔥 <b>PRO ADMIN PANEL</b>

    👥 Жами фойдаланувчи: {total_users}
    👷 Актив усталар: {total_masters}
    ⭐ VIP усталар: {vip_masters}

    📦 Жами буюртма: {total_orders}
    ⭐ Жами рейтинг: {total_ratings}

    📈 24 соат:
    👥 Янги фойдаланувчи: {new_users_24h}
    📦 Янги буюртма: {orders_24h}
    """

    text += service_stats
    text += region_stats

    if top_master:
        text += f"\n🥇 Энг фаол уста:\n{top_master[0]} (🆔 {top_master[1]}) — {top_master[2]} та\n"
    else:
        text += "\n🥇 Энг фаол уста: Йўқ\n"
        
    keyboard = [
        [InlineKeyboardButton("🔄 Янгилаш", callback_data="admin_refresh")],
        [InlineKeyboardButton("📊 Топ усталар", callback_data="admin_top")],
        [InlineKeyboardButton("⭐ VIP бериш", callback_data="admin_vip")],
        [InlineKeyboardButton("📋 VIP рўйхати", callback_data="admin_vip_list")]
    ]

    if update.callback_query:
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    conn = get_connection()
    c = conn.cursor()

    # Жами фойдаланувчи
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    # Бугунги янги
    c.execute("""
        SELECT COUNT(*) FROM users
        WHERE join_date::timestamp >= NOW() - INTERVAL '1 DAY'
    """)
    today_users = c.fetchone()[0]

    # Жами buyurtma
    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]

    # VIP усталар
    c.execute("SELECT COUNT(*) FROM masters WHERE vip=TRUE")
    vip_count = c.fetchone()[0]

    # Энг кўп чақирилган уста
    c.execute("""
        SELECT m.name, COUNT(o.id) as order_count
        FROM masters m
        JOIN orders o ON m.id=o.master_id
        GROUP BY m.name
        ORDER BY order_count DESC
        LIMIT 1
    """)
    top_master = c.fetchone()

    conn.close()

    text = f"""
    📊 КЕНГАЙТИРИЛГАН АНАЛИТИКА

    👥 Жами фойдаланувчилар: {total_users}
    📅 Бугунги янги: {today_users}
    📦 Жами buyurtmalar: {total_orders}
    ⭐ VIP усталар: {vip_count}

    🏆 Энг фаол уста:
    {top_master[0] if top_master else "Йўқ"}
    """

    await query.message.reply_text(text)

async def admin_vip_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    context.user_data["step"] = "vip_input"

    await query.message.reply_text("⭐ VIP бериш учун устанинг кодини киритинг:")

async def admin_vip_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT name, telegram_id, vip_until
        FROM masters
        WHERE vip = TRUE
        ORDER BY vip_until DESC NULLS LAST
    """)

    vip_masters = c.fetchall()
    conn.close()

    if not vip_masters:
        await query.message.reply_text("⭐ VIP усталар йўқ.")
        return

    text = "⭐ VIP УСТАЛАР РЎЙХАТИ:\n\n"

    for i, master in enumerate(vip_masters, start=1):
        name, telegram_id, vip_until = master

        if vip_until:
            text += f"{i}. {name}\n🆔 {telegram_id}\n⏳ {vip_until.strftime('%Y-%m-%d')}\n\n"
        else:
            text += f"{i}. {name}\n🆔 {telegram_id}\n\n"

    await query.message.reply_text(text)

async def give_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Фойдаланиш: /vip 1234")
        return

    code = context.args[0]

    if not code.isdigit() or len(code) != 4:
        await update.message.reply_text("❌ Код 4 хоналик рақам бўлиши керак.")
        return

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        UPDATE masters
        SET vip = TRUE,
            vip_until = COALESCE(vip_until, NOW()) + INTERVAL '30 days'
        WHERE code = %s
        RETURNING telegram_id
    """, (code,))

    result = c.fetchone()
    conn.commit()
    conn.close()

    if not result:
        await update.message.reply_text("❌ Бундай кодли уста топилмади.")
        return

    master_tg_id = result[0]

    await update.message.reply_text(f"✅ Уста (🆔 {code}) 30 кунга VIP қилинди.")

    # Устага хабар бериш
    await context.bot.send_message(
        chat_id=master_tg_id,
        text="🌟 Табриклаймиз! Сиз 30 кунга VIP уста бўлдингиз!"
    )
# ================= SO'ZLARNI TOZALASH =================
def clean_text(text):
    """Noto'g'ri so'zlarni filtrlash"""
    import re
    
    # Lotin harflari, kirill harflari, raqamlar va belgilardan tashqari hamma narsani olib tashlash
    text = re.sub(r"[^\w\s\u0400-\u04FF'ʼ\-.,()]", "", text)
    
    # Ko'p bo'shliqlarni bitta bo'shliqqa almashtirish
    text = re.sub(r'\s+', ' ', text)
    
    # Boshlanish va oxiridagi bo'shliqlarni olib tashlash
    text = text.strip()
    
    # Minimal uzunlikni tekshirish
    if len(text) < 2:
        return ""
    
    return text

# ================= REGISTER FLOW =================
async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Tilni saqlab qolish
    language = context.user_data.get("language", "uz_kr")
    context.user_data.pop("flow", None)
    context.user_data.pop("step", None)
    context.user_data.pop("page", None)
    context.user_data["language"] = language
    context.user_data["flow"] = "register"
    context.user_data["step"] = "phone"
    
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    # Tilga mos telefon tugmasi
    if language == "uz_kr":
        phone_text = "📞 Телефон юбориш"
    elif language == "uz_lt":
        phone_text = "📞 Telefon yuborish"
    else:  # ru
        phone_text = "📞 Отправить телефон"
    
    kb = [[KeyboardButton(phone_text, request_contact=True)]]
    await update.message.reply_text(texts["send_phone"], reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact

    if not contact:
        return

    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    phone = contact.phone_number
    user_id = update.message.from_user.id

    # ⭐ БАЗАГА САҚЛАЙМИЗ
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        "UPDATE users SET phone=%s WHERE telegram_id=%s",
        (phone, user_id)
    )

    conn.commit()
    conn.close()

    # context ham qoladi
    context.user_data["phone"] = phone
    context.user_data["name"] = clean_text(
        f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    )
    context.user_data["step"] = "service"

    await update.message.reply_text(
        texts["choose_service"],
        reply_markup=build_service_menu(language)
    )

async def ask_region(update: Update, context: ContextTypes.DEFAULT_TYPE):

    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    regions_data = REGIONS.get(language, REGIONS["uz_kr"])

    region = context.user_data.get("region")

    regions_data = REGIONS.get(language, REGIONS["uz_kr"])

    # uz_kr region индексини топамиз
    if not region:
        return

    try:
        index = list(REGIONS["uz_kr"].keys()).index(region)
    except ValueError:
        return

    # user тилидаги region
    display_region = list(regions_data.keys())[index]

    hide_empty = context.user_data.get("flow") == "find"

    base_markup = build_city_menu(
        display_region,
        context.user_data["service"],
        language,
        hide_empty
    )
    keyboard = [row[:] for row in base_markup.keyboard]

    if context.user_data.get("flow") == "find":
        keyboard.insert(0, ["📍 Фақат вилоят бўйича қидириш"])

    await update.message.reply_text(
        texts["choose_district"],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    
async def write_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")

    if language == "uz_kr":
        text = "Админ билан боғланиш учун тугмани босинг:"
        btn = "📩 Админга ёзиш"

    elif language == "uz_lt":
        text = "Admin bilan bog'lanish uchun tugmani bosing:"
        btn = "📩 Adminga yozish"

    else:
        text = "Нажмите кнопку для связи с админом:"
        btn = "📩 Написать админу"

    keyboard = [[InlineKeyboardButton(btn, url="https://t.me/botir_support")]]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    if update.message.contact:
        return

    raw_text = update.message.text or ""
    text = raw_text.split(" (")[0].strip()
    user_id = update.effective_user.id

    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    flow = context.user_data.get("flow")
    step = context.user_data.get("step")

    # ================= BACK =================
    if text in ["Орқага", "Orqaga", "Назад"]:

        if flow == "find":
            if step == "district":
                context.user_data["step"] = "region"
                await update.message.reply_text(
                    texts["choose_region"],
                    reply_markup=build_region_menu(
                        context.user_data["service"],
                        language,
                        hide_empty=True
                    )
                )
                return

            if step == "region":
                context.user_data["step"] = "service"
                await update.message.reply_text(
                    texts["choose_service"],
                    reply_markup=build_service_menu(language, sort_by_count=True)
                )
                return

        if flow == "register":
            if step == "district":
                context.user_data["step"] = "region"
                await update.message.reply_text(
                    texts["choose_region"],
                    reply_markup=build_region_menu(
                        context.user_data["service"],
                        language
                    )
                )
                return

            if step == "region":
                context.user_data["step"] = "service"
                await update.message.reply_text(
                    texts["choose_service"],
                    reply_markup=build_service_menu(language)
                )
                return

        context.user_data.pop("flow", None)
        context.user_data.pop("step", None)
        context.user_data.pop("waiting_for_code", None)

        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT 1 FROM masters
            WHERE telegram_id=%s AND is_active=TRUE
        """, (user_id,))
        is_master = c.fetchone() is not None
        conn.close()

        menu, mode = build_main_menu(texts, is_master, context.user_data.get("mode"))
        context.user_data["mode"] = mode

        await update.message.reply_text(
            texts["welcome"],
            reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
        )
        return

    # ================= MAIN SIMPLE BUTTONS =================
    if text in ["🪙 Танга", "🪙 Tanga", "🪙 Монеты", "💰 Балларим", "💰 Ballarim", "💰 Мои баллы"]:
        await show_points(update, context)
        return

    if text in ["🏆 Топ тангалар", "🏆 Top tangalar", "🏆 Топ монет"]:
        await show_top_coins(update, context)
        return

    # ================= REGISTER FLOW =================
    if flow == "register":

        if step == "service":
            services = SERVICES.get(language, SERVICES["uz_kr"])
            if text in services:
                context.user_data["service"] = map_service_to_uzkr(text)
                context.user_data["step"] = "region"

                await update.message.reply_text(
                    texts["choose_region"],
                    reply_markup=build_region_menu(
                        context.user_data["service"],
                        language
                    )
                )
                return

        if step == "region":
            regions = REGIONS.get(language, REGIONS["uz_kr"])
            if text in regions:
                context.user_data["region"] = map_region_to_uzkr(text)
                context.user_data["step"] = "district"
                await ask_region(update, context)
                return

        if step == "district":
            selected_region = context.user_data.get("region")
            uz_region = map_region_to_uzkr(selected_region)
            uz_district = map_district_to_uzkr(selected_region, text)
            uz_service = map_service_to_uzkr(context.user_data.get("service"))

            if uz_district not in REGIONS["uz_kr"].get(uz_region, []):
                await update.message.reply_text("❌ Илтимос тугмани босинг.")
                return

            context.user_data["district"] = uz_district
            context.user_data["service"] = uz_service

            add_master(
                telegram_id=user_id,
                name=context.user_data.get("name"),
                phone=context.user_data.get("phone"),
                service=context.user_data.get("service"),
                region=context.user_data.get("region"),
                district=context.user_data.get("district"),
                age=None,
                experience=None,
                service_description=None
            )

            context.user_data["mode"] = "master"
            menu, mode = build_main_menu(texts, True, "master")
            context.user_data["mode"] = mode

            await update.message.reply_text(
                "✅ Сиз муваффақиятли рўйхатдан ўтдингиз!\n\n"
                "👤 Қолган маълумотларни 'Менинг профилим' орқали тўлдиришингиз мумкин.",
                reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
            )

            context.user_data.pop("flow", None)
            context.user_data.pop("step", None)
            return

    # ================= FIND FLOW =================
    if flow == "find":

        if step == "service":
            services = SERVICES.get(language, SERVICES["uz_kr"])
            if text in services:
                context.user_data["service"] = map_service_to_uzkr(text)

                if context.user_data.get("after_find_action") == "order":
                    context.user_data["step"] = "location"

                    location_button = KeyboardButton("📍 Локация юбориш", request_location=True)
                    back_button = KeyboardButton(texts["back"])

                    await update.message.reply_text(
                        "📍 Илтимос, локациянгизни юборинг:",
                        reply_markup=ReplyKeyboardMarkup(
                            [[location_button], [back_button]],
                            resize_keyboard=True,
                            one_time_keyboard=True
                        )
                    )
                    return

                context.user_data["step"] = "region"

                await update.message.reply_text(
                    texts["choose_region"],
                    reply_markup=build_region_menu(
                        context.user_data["service"],
                        language,
                        hide_empty=True
                    )
                )
                return
        
        if step == "region":
            regions = REGIONS.get(language, REGIONS["uz_kr"])
            if text in regions:
                context.user_data["region"] = map_region_to_uzkr(text)
                context.user_data["step"] = "district"
                await ask_region(update, context)
                return

        if step == "district":
            if text == "📍 Фақат вилоят бўйича қидириш":
                context.user_data["district"] = None

                if context.user_data.get("after_find_action") == "order":
                    context.user_data["after_find_action"] = None
                    context.user_data["waiting_for_order"] = True
                    context.user_data["flow"] = None
                    context.user_data["step"] = None

                    await update.message.reply_text(
                        "✏️ Муаммони қисқача ёзинг\n"
                        "(масалан: кран ишламай қолди)"
                    )
                    return

                await show_masters(update, context)
                return

            await get_district(update, context)

            if context.user_data.get("after_find_action") == "order":
                context.user_data["after_find_action"] = None
                context.user_data["waiting_for_order"] = True
                context.user_data["flow"] = None
                context.user_data["step"] = None

                await update.message.reply_text(
                    "✏️ Муаммони қисқача ёзинг\n"
                    "(масалан: кран ишламай қолди)"
                )
                return

            return

    # ================= CODE SEARCH =================
    if context.user_data.get("waiting_for_code"):

        if not text.isdigit() or len(text) != 4:
            context.user_data["waiting_for_code"] = False
            await update.message.reply_text("❌ Код 4 хоналик рақам бўлиши керак.")
            return

        code = text

        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT id, name, phone, service, district, age, experience, vip
            FROM masters
            WHERE code=%s AND is_active=TRUE
        """, (code,))
        master = c.fetchone()
        conn.close()

        if not master:
            context.user_data["waiting_for_code"] = False
            await update.message.reply_text("❌ Код топилмади.")
            return

        mid, name, phone, service, district, age, experience, vip = master
        badge = f"👑 VIP УСТА • 🆔 {code}" if vip else f"👷 УСТА • 🆔 {code}"

        msg = f"""
══════════════════════════
<b>{badge}</b>

👤 <b>{name}</b>
🛠 {service}
📍 {district}
🎂 {age if age else '-'} ёш
🧰 {experience if experience else '-'} тажриба
📞 <b>+{phone}</b>
══════════════════════════
"""

        keyboard = [[
            InlineKeyboardButton("📞 Қўнғироқ", callback_data=f"call_{phone}"),
            InlineKeyboardButton("✅ Чақирдим", callback_data=f"order_{mid}"),
            InlineKeyboardButton("⭐ Баҳо", callback_data=f"rate_{mid}")
        ]]

        await update.message.reply_text(
            msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        context.user_data["waiting_for_code"] = False
        return

    # ================= ORDER TEXT =================
    if context.user_data.get("waiting_for_order"):
        problem = text.strip()

        if len(problem) < 5:
            await update.message.reply_text("❌ Муаммони тўлиқроқ ёзинг.")
            return

        service = context.user_data.get("service")
        district = context.user_data.get("district")
        customer_name = update.effective_user.first_name or "Мижоз"
        customer_id = update.effective_user.id

        if not service or not district:
            context.user_data["waiting_for_order"] = False
            await update.message.reply_text(
                "❌ Аввал хизмат тури ва туманни танланг."
            )
            return

        conn = get_connection()
        c = conn.cursor()

        c.execute("""
            SELECT telegram_id, name, phone, vip
            FROM masters
            WHERE service=%s
              AND district=%s
              AND is_active=TRUE
              AND telegram_id IS NOT NULL
        """, (service, district))

        matched_masters = c.fetchall()
        conn.close()

        context.user_data["waiting_for_order"] = False

        if not matched_masters:
            await update.message.reply_text(
                "❌ Бу хизмат ва туманда ҳозирча фаол уста топилмади."
            )
            return

        order_message = f"""📢 <b>Янги буюртма</b>

    👤 Мижоз: {customer_name}
    🛠 Хизмат: {service}
    📍 Туман: {district}
    📝 Муаммо: {problem}
    """

        sent_count = 0

        for master_user_id, master_name, master_phone, vip in matched_masters:
            try:
                keyboard = [[
                    InlineKeyboardButton(
                        "✅ Қабул қилиш",
                        callback_data=f"accept_order_{customer_id}"
                    )
                ]]

                await context.bot.send_message(
                    chat_id=master_user_id,
                    text=order_message,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                sent_count += 1

            except Exception as e:
                print(f"Устага юборишда хатолик: {master_user_id} -> {e}")

        if sent_count == 0:
            await update.message.reply_text(
                "❌ Усталар топилди, лекин уларга хабар юбориб бўлмади."
            )
            return

        await update.message.reply_text(
            f"✅ Буюртмангиз қабул қилинди.\n\n"
            f"📨 {sent_count} та устага юборилди."
        )
        return
    
    # ================= MAIN MENU =================
    if text in ["🔎 Уста топиш", "🔎 Usta topish", "🔎 Найти мастера",
                "Уста топиш", "Usta topish", "Найти мастера"]:
        await start_find(update, context)
        return

    if text in ["👨‍🔧 Уста бўлиш", "👨‍🔧 Usta bo'lish", "👨‍🔧 Стать мастером",
                "Уста бўлиш", "Usta bo'lish", "Стать мастером"]:
        await start_register(update, context)
        return

    if text in ["📨 Буюртма қолдириш", "📨 Buyurtma qoldirish", "📨 Оставить заявку"]:
        context.user_data["flow"] = "find"
        context.user_data["step"] = "service"
        context.user_data["after_find_action"] = "order"

        await update.message.reply_text(
            texts["choose_service"],
            reply_markup=build_service_menu(language)
        )
        return
    
    if text in ["👤 Менинг профилим", "👤 Mening profilim", "👤 Мой профиль",
                "Менинг профилим", "Mening profilim", "Мой профиль"]:
        await my_profile(update, context)
        return

    if text in ["🎁 Таклиф қилиш", "🎁 Taklif qilish", "🎁 Пригласить"]:
        await show_referral(update, context)
        return

    if text in ["🌐 Тилни ўзгартириш", "🌐 Tilni o'zgartirish", "🌐 Изменить язык"]:
        await change_language(update, context)
        return

async def location_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if not update.message.location:
        return

    lat = update.message.location.latitude
    lon = update.message.location.longitude

    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
    headers = {"User-Agent": "usta-bot/1.0"}
    data = requests.get(url, headers=headers).json()

    address = data.get("address", {})

    raw_region = (
        address.get("state")
        or address.get("region")
        or address.get("province")
        or ""
    )

    raw_district = (
        address.get("city")
        or address.get("county")
        or address.get("town")
        or address.get("municipality")
        or address.get("state_district")
        or ""
    )

    region = find_region(raw_region)
    district = find_district(region, raw_district)

    context.user_data["region"] = region
    context.user_data["district"] = district
    context.user_data["district"] = district
    context.user_data["waiting_for_order"] = True
    context.user_data["step"] = None
    context.user_data["flow"] = None

    await update.message.reply_text(
        "✏️ Муаммони қисқача ёзинг\n"
        "(масалан: кран ишламай қолди)"
    )
           
async def show_referral(update, context):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    language = context.user_data.get("language", "uz_kr")

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT points FROM users WHERE telegram_id=%s", (user_id,))
    row = c.fetchone()
    points = row[0] if row else 0

    c.execute("SELECT COUNT(*) FROM users WHERE referred_by=%s", (user_id,))
    referrals = c.fetchone()[0]

    c.execute("SELECT 1 FROM masters WHERE telegram_id=%s AND is_active=TRUE", (user_id,))
    is_master = c.fetchone() is not None

    conn.close()

    if points >= 10000:
        level = "💎 DIAMOND"
        next_level = "MAX"
        remaining = 0
    elif points >= 5000:
        level = "👑 GOLD"
        next_level = "💎 DIAMOND"
        remaining = 10000 - points
    elif points >= 2000:
        level = "🥈 SILVER"
        next_level = "👑 GOLD"
        remaining = 5000 - points
    elif points >= 500:
        level = "🥉 BRONZE"
        next_level = "🥈 SILVER"
        remaining = 2000 - points
    else:
        level = "👤 START"
        next_level = "🥉 BRONZE"
        remaining = 500 - points

    ref_link = f"https://t.me/{bot_username}?start={user_id}"

    if language == "uz_kr":
        share_text = (
            f"🏠 Уйда иш чиқдими?\n\n"
            f"👷 Мардикор\n"
            f"🪓 Ер қазиш / ер ағдариш\n"
            f"🧱 Қурилиш ишлари\n"
            f"🛠 Таъмирчи\n"
            f"🚰 Сантехник\n"
            f"🔌 Электрик\n"
            f"🧹 Хона тозалаш\n"
            f"🚛 Юк ташиш\n\n"
            f"Қидириб юриш шарт эмас!\n\n"
            f"🎁 Қўшилганларга бонус бор!\n\n"
            f"Ишончли устани шу ердан топинг 👇\n"
            f"{ref_link}"
        )

        text = (
            f"🎁 Дўст таклиф қилинг ва 100 танга олинг!\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👥 Таклиф қилганлар: {referrals}\n"
            f"🪙 Жами танга: {points}\n"
            f"🎖 Даража: {level}\n"
            f"━━━━━━━━━━━━━━━\n\n"
            + (
                f"🚀 {next_level} даражага чиқиш учун яна {remaining} танга керак!"
                if remaining > 0
                else "🏆 Табриклаймиз! Сиз энг юқори даражадасиз!"
            )
        )
        send_btn = "📤 Дўстларга юбориш"

    elif language == "uz_lt":
        share_text = (
            f"🏠 Uyda ish chiqdimi?\n\n"
            f"👷 Mardikor\n"
            f"🪓 Yer qazish / yer ag'darish\n"
            f"🧱 Qurilish ishlari\n"
            f"🛠 Ta'mirchi\n"
            f"🚰 Santexnik\n"
            f"🔌 Elektrik\n"
            f"🧹 Xona tozalash\n"
            f"🚛 Yuk tashish\n\n"
            f"Qidirib yurish shart emas!\n\n"
            f"🎁 Qo'shilganlarga bonus bor!\n\n"
            f"Ishonchli ustani shu yerdan toping 👇\n"
            f"{ref_link}"
        )

        text = (
            f"🎁 Do'st taklif qiling va 100 tanga oling!\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👥 Taklif qilganlar: {referrals}\n"
            f"🪙 Jami tanga: {points}\n"
            f"🎖 Daraja: {level}\n"
            f"━━━━━━━━━━━━━━━\n\n"
            + (
                f"🚀 {next_level} darajaga chiqish uchun yana {remaining} tanga kerak!"
                if remaining > 0
                else "🏆 Tabriklaymiz! Siz eng yuqori darajadasiz!"
            )
        )
        send_btn = "📤 Do'stlarga yuborish"

    else:
        share_text = (
            f"🏠 Нужен мастер?\n\n"
            f"👷 Разнорабочий\n"
            f"🪓 Земляные работы\n"
            f"🧱 Строительные работы\n"
            f"🛠 Ремонт\n"
            f"🚰 Сантехник\n"
            f"🔌 Электрик\n"
            f"🧹 Уборка\n"
            f"🚛 Грузоперевозка\n\n"
            f"Не нужно долго искать!\n\n"
            f"🎁 За приглашённых есть бонус!\n\n"
            f"Найдите надёжного мастера здесь 👇\n"
            f"{ref_link}"
        )

        text = (
            f"🎁 Приглашайте друзей и получайте 100 монет!\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👥 Приглашено: {referrals}\n"
            f"🪙 Всего монет: {points}\n"
            f"🎖 Уровень: {level}\n"
            f"━━━━━━━━━━━━━━━\n\n"
            + (
                f"🚀 До уровня {next_level} осталось ещё {remaining} монет!"
                if remaining > 0
                else "🏆 Поздравляем! У вас максимальный уровень!"
            )
        )
        send_btn = "📤 Отправить друзьям"

    keyboard = [[InlineKeyboardButton(send_btn, switch_inline_query=share_text)]]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
       
# ================= POINTS =================
async def show_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    language = context.user_data.get("language", "uz_kr")

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT points FROM users WHERE telegram_id=%s", (user_id,))
    row = c.fetchone()
    points = row[0] if row else 0

    c.execute("SELECT 1 FROM masters WHERE telegram_id=%s AND is_active=TRUE", (user_id,))
    is_master = c.fetchone() is not None

    conn.close()

    if language == "uz_kr":
        text = f"🪙 Сизнинг тангаларингиз: {points}"
        vip7 = "👑 VIP 7 кун — 1000 танга"
        vip30 = "👑 VIP 30 кун — 4000 танга"
        buy_btn = "🛒 Танга сотиб олиш"
        sell_btn = "📈 Танга сотиш"
    elif language == "uz_lt":
        text = f"🪙 Sizning tangalaringiz: {points}"
        vip7 = "👑 VIP 7 kun — 1000 tanga"
        vip30 = "👑 VIP 30 kun — 4000 tanga"
        buy_btn = "🛒 Tanga sotib olish"
        sell_btn = "📈 Tanga sotish"
    else:
        text = f"🪙 Ваши монеты: {points}"
        vip7 = "👑 VIP 7 дней — 1000 монет"
        vip30 = "👑 VIP 30 дней — 4000 монет"
        buy_btn = "🛒 Купить монеты"
        sell_btn = "📈 Продать монеты"

    if is_master:
        keyboard = [
            [InlineKeyboardButton(vip7, callback_data="buy_vip_7")],
            [InlineKeyboardButton(vip30, callback_data="buy_vip_30")],
            [InlineKeyboardButton(buy_btn, callback_data="buy_points")],
            [InlineKeyboardButton(sell_btn, callback_data="sell_points")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(sell_btn, callback_data="sell_points")]
        ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_top_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT
            COALESCE(NULLIF(first_name, ''), username, 'User') as display_name,
            points
        FROM users
        WHERE COALESCE(points, 0) > 0
        ORDER BY points DESC, created_at ASC
        LIMIT 10
    """)

    rows = c.fetchall()
    conn.close()

    if language == "uz_kr":
        title = "🏆 <b>ТОП 10 ТАНГА ЭГАЛАРИ</b>\n\n"
        empty_text = "Ҳозирча рейтингда ҳеч ким йўқ."
        suffix = "танга"
    elif language == "uz_lt":
        title = "🏆 <b>TOP 10 TANGA EGALARI</b>\n\n"
        empty_text = "Hozircha reytingda hech kim yo'q."
        suffix = "tanga"
    else:
        title = "🏆 <b>ТОП 10 ПО МОНЕТАМ</b>\n\n"
        empty_text = "Пока в рейтинге никого нет."
        suffix = "монет"

    if not rows:
        await update.message.reply_text(empty_text)
        return

    medals = ["🥇", "🥈", "🥉"]
    text = title

    for i, (name, points) in enumerate(rows, start=1):
        icon = medals[i - 1] if i <= 3 else f"{i}."
        text += f"{icon} {name} — {points} {suffix}\n"

    await update.message.reply_text(text, parse_mode="HTML")
    
def is_user_master(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM masters WHERE telegram_id=%s AND is_active=TRUE", (user_id,))
    result = c.fetchone()
    conn.close()
    return result
    
async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE):

    selected_region = context.user_data.get("region")
    selected_district = update.message.text.split(" (")[0].strip()

    uz_region = map_region_to_uzkr(selected_region)
    uz_district = map_district_to_uzkr(selected_region, selected_district)
    uz_service = map_service_to_uzkr(context.user_data.get("service"))

    if uz_district not in REGIONS["uz_kr"].get(uz_region, []):
        await update.message.reply_text("❌ Илтимос тугмани босинг.")
        return

    context.user_data["region"] = uz_region
    context.user_data["district"] = uz_district
    context.user_data["service"] = uz_service

    # ===== FIND =====
    if context.user_data.get("flow") == "find":
        await show_masters(update, context)
        return
        
async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    if context.user_data.get("flow") != "register":
        return
    
    if context.user_data.get("step") != "age":
        return

    age = clean_text(update.message.text)
    
    if not age or not age.isdigit() or len(age) > 2:
        await update.message.reply_text(texts["enter_age"])
        return

    context.user_data["age"] = age

    # ⭐ ТАЖРИБА КНОПКАСИ
    keyboard = [
        ["1-3 йил"],
        ["3-5 йил"],
        ["5-10 йил"],
        ["10+ йил"]
    ]

    await update.message.reply_text(
        "🧰 Неча йиллик тажрибага эгасиз?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

    context.user_data["step"] = "experience"
    
async def get_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")

    # фақат register flow да ишлайди
    if context.user_data.get("flow") != "register":
        return
    
    if context.user_data.get("step") != "experience":
        return

    experience = update.message.text.strip()

    valid = ["1-3 йил", "3-5 йил", "5-10 йил", "10+ йил"]

    if experience not in valid:
        await update.message.reply_text("❌ Илтимос тугмани босинг.")
        return

    # сақлаймиз
    context.user_data["experience"] = experience

    # кейинги қадам
    context.user_data["step"] = "description"

    await update.message.reply_text(
        "📝 Қандай ишлар қиласиз?\n\n"
        "Ихтиёрий (300 белгидан оширманг).\n"
        "Ўтказиб юбориш учун '-' юборинг.",
        reply_markup=ReplyKeyboardRemove()
    )
 
async def save_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "rating":
        return

    rating = update.message.text

    if rating not in ["1","2","3","4","5"]:
        await update.message.reply_text("1 дан 5 гача ёзинг.")
        return

    user_id = update.effective_user.id
    master_id = context.user_data.get("rating_master")

    if not can_rate(update.effective_user.id, master_id):
        await update.message.reply_text("❌ Сиз бу уста билан ишламагансиз.")

        context.user_data.pop("step", None)
        context.user_data.pop("rating_master", None)

        return

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        INSERT INTO ratings(master_id, user_id, rating)
        VALUES (%s,%s,%s)
        ON CONFLICT (master_id, user_id) DO NOTHING
    """, (master_id, user_id, rating))

    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Раҳмат! Баҳо сақланди.")

    context.user_data["step"] = None

# ================= FIND FLOW =================
async def start_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Tilni saqlab qolish
    language = context.user_data.get("language", "uz_kr")
    context.user_data.pop("flow", None)
    context.user_data.pop("step", None)
    context.user_data.pop("page", None)
    context.user_data["language"] = language
    context.user_data["flow"] = "find"
    context.user_data["step"] = "service"
    context.user_data["page"] = 0
    
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    await update.message.reply_text(texts["choose_service"], reply_markup=build_service_menu(language, sort_by_count=True))


async def find_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    services_list = SERVICES.get(language, SERVICES["uz_kr"])
    
    if update.message.text not in services_list:
        return

    context.user_data["service"] = update.message.text
    context.user_data["step"] = "region"

    await update.message.reply_text(
        texts["choose_region"],
        reply_markup=build_region_menu(context.user_data["service"], language, hide_empty=True)
    )

async def show_masters(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.callback_query:
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        message = update.message

    service = context.user_data.get("service")
    region = context.user_data.get("region")
    district = context.user_data.get("district")

    # 🔥 mapping
    service = map_service_to_uzkr(service)
    region = map_region_to_uzkr(region)

    if district:
        district = map_district_to_uzkr(region, district)
        
    print("SERVICE:", service)
    print("REGION:", region)
    print("DISTRICT:", district)

    page = context.user_data.get("page", 0)
    limit = 5
    offset = page * limit

    conn = get_connection()
    c = conn.cursor()

    from datetime import date
    today = date.today()

    # 🔄 Автоматик равишда муддати ўтган бандликни тозалаш
    c.execute("""
        UPDATE masters
        SET is_busy = FALSE,
            busy_until = NULL
        WHERE is_busy = TRUE
          AND busy_until IS NOT NULL
          AND busy_until < %s
          AND is_active = TRUE
    """, (today,))

    line = "══════════════════════════"

    # ⭐ VIP + NORMAL битта JOIN билан
    query = """
    SELECT 
        m.id,
        m.name,
        m.phone,
        m.service,
        m.district,
        m.age,
        m.experience,
        m.vip,
        m.code,
        m.service_description,
        m.is_busy,
        m.busy_until,
        COALESCE(AVG(r.rating), 0) as avg_rating,
        COUNT(r.rating) as votes
    FROM masters m
    LEFT JOIN ratings r ON m.id = r.master_id
    WHERE m.service = %s
      AND m.region = %s
      AND m.is_active = TRUE
    """

    params = [service, region]

    if district:
        query += " AND m.district = %s"
        params.append(district)
    
    query += """    
    GROUP BY 
        m.id,
        m.name,
        m.phone,
        m.service,
        m.district,
        m.age,
        m.experience,
        m.vip,
        m.code,
        m.service_description,
        m.is_busy,
        m.busy_until
    ORDER BY 
        m.vip DESC,
        avg_rating DESC
    LIMIT %s OFFSET %s
    """
 
    params.extend([limit, offset])

    c.execute(query, params)
    
    rows = c.fetchall()

    if not rows:
        conn.close()
        texts = get_texts(context.user_data.get("language", "uz_kr"))

        await message.reply_text(texts["no_masters"])
        return

    for mid, name, phone, service, dist, age, experience, vip, code, desc, is_busy, busy_until, avg_rating, votes in rows:
        
        rating_text = (
            f"{round(avg_rating,1)} ({votes})"
            if votes > 0 else "Рейтинг йўқ"
        )
        
        print("DEBUG:", is_busy, busy_until)
        
        badge = f"👑 VIP УСТА • 🆔 {code}" if vip else f"👷 УСТА • 🆔 {code}"
       
        if is_busy and busy_until and busy_until >= today:
            status_text = f"🔴 Банд ({busy_until})"
        else:
            status_text = "🟢 Бўш"
        card = f"""
        {line}
        <b>{badge}</b>
        <b>{status_text}</b>
        👤 <b>{name}</b>
        🛠 {service}
        📍 {dist}
        """

        if age:
            card += f"\n🎂 {age} ёш"

        if experience:
            card += f"\n🧰 {experience} тажриба"

        card += f"""
        📞 <b>+{phone}</b>
        ⭐ {rating_text}
        """
        # 🔥 Description алоҳида қўшилади
        if desc:
            short_desc = desc[:150]
            if len(desc) > 150:
                short_desc += "..."
            card += f"\n📝 {short_desc}\n"

        # 🔥 СЎНГГИ 3 ТА ИЗОҲ
        c.execute("""
            SELECT rating, comment
            FROM ratings
            WHERE master_id=%s AND comment IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 3
        """, (mid,))

        comments = c.fetchall()

        if comments:
            card += "\n🗣 Фикрлар:\n"
            for r, com in comments:
                card += f"⭐ {r} — {com}\n"

        card += f"\n{line}"
        keyboard = [[
            InlineKeyboardButton("📞 Қўнғироқ", callback_data=f"call_{phone}"),
            InlineKeyboardButton("✅ Чақирдим", callback_data=f"order_{mid}"),
            InlineKeyboardButton("⭐ Баҳо", callback_data=f"rate_{mid}")
        ]]

        await message.reply_text(card, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    

    # 🔁 Pagination
    nav = []

    if page > 0:
        nav.append(InlineKeyboardButton("⬅ Олдингиси", callback_data=f"prev_{page-1}"))

    if len(rows) == limit:
        nav.append(InlineKeyboardButton("➡ Кейингиси", callback_data=f"next_{page+1}"))

    if nav:
        await message.reply_text(
            "📄 Саҳифалар:",
            reply_markup=InlineKeyboardMarkup([nav])
        )

    conn.close()

async def call_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("CALL HANDLER ISHLADI")  # 👈
    query = update.callback_query
    await query.answer()

    phone = query.data.split("_", 1)[1]

    await query.message.reply_text(f"📞 +{phone}")

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    print("CALLBACK:", data)

    # 📞 telefonni ko'rsatish
    if data.startswith("call_"):
        phone = data.replace("call_", "")
        await query.message.reply_text(f"📞 Устанинг телефони:\n+{phone}")

    # ================= DELETE PROFILE =================
    elif data == "delete_profile":

        conn = get_connection()
        c = conn.cursor()

        c.execute("""
            UPDATE masters
            SET is_active = FALSE
            WHERE telegram_id = %s
        """, (query.from_user.id,))

        conn.commit()
        conn.close()

        await query.message.reply_text("❌ Сиз рўйхатдан чиқдингиз.")
        return

    # ================= REF LINK =================
    elif data == "my_ref_link":

        user_id = query.from_user.id
        bot_username = (await context.bot.get_me()).username

        ref_link = f"https://t.me/{bot_username}?start={user_id}"

        await query.message.reply_text(f"🔗 Сизнинг таклиф линкингиз:\n\n{ref_link}\n\n" "👥 Ҳар бир қўшилган одам учун 100 танга оласиз!")
        return
        
    # ================= ORDER =================
    elif data.startswith("order_"):
        mid = int(data.replace("order_", ""))
        user = query.from_user
        user_id = user.id
        user_name = user.first_name

        conn = get_connection()
        c = conn.cursor()

        # buyurtma yozamiz va ID ni olamiz
        c.execute(
            "INSERT INTO orders (user_id, master_id) VALUES (%s, %s) RETURNING id",
            (user_id, mid)
        )

        order_id = c.fetchone()[0]

        # ustaning telegram id sini olamiz
        c.execute("SELECT telegram_id, name FROM masters WHERE id=%s", (mid,))
        master = c.fetchone()

        # klient telefonini olamiz
        c.execute("SELECT phone FROM users WHERE telegram_id=%s", (user_id,))
        user_phone = c.fetchone()

        conn.commit()
        conn.close()

        await query.message.reply_text("✅ Буюртма қабул қилинди. Уста сиз билан боғланади.")

        # ⭐ usta mavjud bo'lsa habar yuboramiz
        if master:
            master_tg_id = master[0]
            master_name = master[1]

            if user_phone:
                user_phone = user_phone[0]
            else:
                user_phone = "Телефон йўқ"

            keyboard = [[
                InlineKeyboardButton(
                    "✅ Иш тугади",
                    callback_data=f"complete_{order_id}_{user_id}"
                )
            ]]

            await context.bot.send_message(
                chat_id=master_tg_id,
                text=(
                    f"📢 Янги буюртма!\n\n"
                    f"👤 Исм: {user_name}\n"
                    f"📞 Телефон: {user_phone}\n"
                    f"🆔 ID: {user_id}\n\n"
                    f"Иш тугаганда тугмани босинг:"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif data == "buy_vip_7":

        user_id = query.from_user.id

        # ⭐ Фақат уста VIP олиши мумкин
        if not is_user_master(user_id):
            await query.message.reply_text("❌ Фақат усталар VIP сотиб олиши мумкин.")
            return

        conn = get_connection()
        c = conn.cursor()

        c.execute("SELECT points FROM users WHERE telegram_id=%s", (user_id,))
        row = c.fetchone()
        points = row[0] if row else 0

        if points < 1000:
            await query.message.reply_text("❌ Тангалар етарли эмас.")
            conn.close()
            return

        # ⭐ баллни users таблицадан айирамиз
        c.execute("""
            UPDATE users
            SET points = points - 1000
            WHERE telegram_id = %s
        """, (user_id,))

        # ⭐ VIP ни masters да ёқамиз
        c.execute("""
            UPDATE masters
            SET vip = TRUE,
                vip_until = COALESCE(vip_until, NOW()) + INTERVAL '7 days'
            WHERE telegram_id = %s
        """, (user_id,))

        conn.commit()
        conn.close()

        await query.message.reply_text("👑 Табриклаймиз! Сиз 7 кунга VIP бўлдингиз.")

    elif data == "buy_vip_30":

        user_id = query.from_user.id

        # ⭐ Фақат уста VIP олиши мумкин
        if not is_user_master(user_id):
            await query.message.reply_text("❌ Фақат усталар VIP сотиб олиши мумкин.")
            return

        conn = get_connection()
        c = conn.cursor()

        c.execute("SELECT points FROM users WHERE telegram_id=%s", (user_id,))
        row = c.fetchone()
        points = row[0] if row else 0

        if points < 4000:
            await query.message.reply_text("❌ Тангалар етарли эмас.")
            conn.close()
            return

        # ⭐ баллни айирамиз
        c.execute("""
            UPDATE users
            SET points = points - 4000
            WHERE telegram_id = %s
        """, (user_id,))

        # ⭐ VIP 30 кун
        c.execute("""
            UPDATE masters
            SET vip = TRUE,
                vip_until = COALESCE(vip_until, NOW()) + INTERVAL '30 days'
            WHERE telegram_id = %s
        """, (user_id,))

        conn.commit()
        conn.close()

        await query.message.reply_text("👑 Табриклаймиз! Сиз 30 кунга VIP бўлдингиз.")

    elif data == "sell_points":

        context.user_data["step"] = "enter_sell_points"

        await query.message.reply_text(
            "💰 Нечта танга сотмоқчисиз?\n\nМасалан: 1000"
        )

    elif data == "sell_1000":

        user_id = query.from_user.id

        conn = get_connection()
        c = conn.cursor()

        c.execute("SELECT points FROM users WHERE telegram_id=%s", (user_id,))
        row = c.fetchone()
        points = row[0] if row else 0

        if points < 1000:
            await query.message.reply_text("❌ Сотиш учун 1000 танга керак.")
            conn.close()
            return

        c.execute("""
            UPDATE users
            SET points = points - 1000
            WHERE telegram_id=%s
        """, (user_id,))

        conn.commit()
        conn.close()

        await query.message.reply_text(
            "✅ Сўров қабул қилинди.\n"
            "Админ тез орада сиз билан боғланади."
        )

        # админга хабар
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💰 Танга сотиш сўрови\n\nUser ID: {user_id}\n1000 танга = 10000 сўм"
        )
    
    # ================= COMPLETE ORDER =================
    elif data.startswith("complete_"):

        parts = data.split("_")
        order_id = parts[1]
        user_id = parts[2]

        conn = get_connection()
        c = conn.cursor()

        c.execute("""
            UPDATE orders
            SET status='completed'
            WHERE id=%s AND status!='completed'
            RETURNING id
        """, (order_id,))

        updated = c.fetchone()

        if not updated:
            conn.close()
            return

        # ⭐ МИЖОЗГА БАЛЛ
        c.execute("""
            UPDATE users
            SET points = COALESCE(points,0) + 100
            WHERE telegram_id = %s
        """, (user_id,))

        # qaysi usta ekanini olamiz
        c.execute("SELECT master_id FROM orders WHERE id=%s", (order_id,))
        mid = c.fetchone()[0]

        # ⭐ УСТАГА БАЛЛ
        c.execute("""
            UPDATE users
            SET points = COALESCE(points,0) + 50
            WHERE telegram_id = (
                SELECT telegram_id FROM masters WHERE id = %s
            )
        """, (mid,))

        # ⭐ УСТАНИНГ ЖАМИ ИШЛАРИ
        c.execute("""
            SELECT COUNT(*)
            FROM orders
            WHERE master_id=%s AND status='completed'
        """, (mid,))

        total_completed = c.fetchone()[0]

        if total_completed % 10 == 0:
            c.execute("""
                UPDATE users
                SET points = COALESCE(points,0) + 500
                WHERE telegram_id = (
                    SELECT telegram_id FROM masters WHERE id = %s
                )
            """, (mid,))

        conn.commit()
        conn.close()

        await query.message.reply_text("✅ Иш тугади деб белгиланди.")

        # ⭐ мижозга рейтинг юбориш
        keyboard = [[
            InlineKeyboardButton("⭐ Баҳо бериш", callback_data=f"rate_{mid}")
        ]]

        await context.bot.send_message(
            chat_id=user_id,
            text="🧰 Уста ишни тугатди.\n\nИлтимос, устага баҳо беринг:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "buy_points":

        user_id = query.from_user.id

        # ⭐ Фақат усталар сотиб олади
        if not is_user_master(user_id):
            await query.message.reply_text("❌ Фақат усталар танга сотиб олиши мумкин.")
            return

        conn = get_connection()
        c = conn.cursor()

        c.execute("""
        SELECT id, seller_id, points
        FROM point_trades
        WHERE status='open'
        ORDER BY created_at DESC
        LIMIT 5
        """)

        trades = c.fetchall()
        conn.close()

        if not trades:
            await query.message.reply_text("❌ Ҳозир сотувда танга йўқ.")
            return

        for t in trades:

            trade_id, seller_id, points = t

            keyboard = [[
                InlineKeyboardButton(
                    "💰 Сотиб олиш",
                    callback_data=f"buytrade_{trade_id}"
                )
            ]]

            price = int((points/1000)*10000)

            await query.message.reply_text(
                f"💰 Танга сотуви\n\n"
                f"{points} танга\n"
                f"Тавсия нарх: {price} сўм",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif data.startswith("buytrade_"):

        trade_id = int(data.split("_")[1])
        buyer_id = query.from_user.id

        conn = get_connection()
        c = conn.cursor()

        # ❗ Бир уста фақат битта савдо олиши мумкин
        c.execute("""
        SELECT 1 FROM point_trades
        WHERE buyer_id=%s AND status='waiting_payment'
        """,(buyer_id,))

        if c.fetchone():
            await query.message.reply_text("❌ Аввал олган савдонгизни якунланг.")
            conn.close()
            return
            
        # 🔎 аввал сотувчини оламиз
        c.execute("""
        SELECT seller_id, points, status
        FROM point_trades
        WHERE id=%s
        """,(trade_id,))

        row = c.fetchone()

        if not row:
            await query.message.reply_text("❌ Савдо топилмади.")
            conn.close()
            return

        seller_id, points, status = row

        # ❌ ўз баллини сотиб олишни блоклаймиз
        if buyer_id == seller_id:
            await query.message.reply_text("❌ Ўз тангангизни сотиб ололмайсиз.")
            conn.close()
            return

        if status != "open":
            await query.message.reply_text("❌ Бу савдо аллақачон олинган.")
            conn.close()
            return

        # ✅ UPDATE
        c.execute("""
        UPDATE point_trades
        SET buyer_id=%s, status='waiting_payment'
        WHERE id=%s AND status='open'
        RETURNING id
        """,(buyer_id,trade_id))

        updated = c.fetchone()

        if not updated:
            await query.message.reply_text("❌ Бу савдо аллақачон олинган.")
            conn.close()
            return

        conn.commit()
        conn.close()

        keyboard = [[
            InlineKeyboardButton(
                "💸 Пул тўладим",
                callback_data=f"paid_{trade_id}"
            )
        ]]

        await query.message.reply_text(
            "💰 Сотувчига пул юборинг.\n\n"
            "Пул юборгандан кейин тугмани босинг.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("paid_"):

        trade_id = int(data.split("_")[1])

        conn = get_connection()
        c = conn.cursor()

        c.execute("""
        SELECT seller_id,buyer_id,points,status
        FROM point_trades
        WHERE id=%s
        """,(trade_id,))

        row = c.fetchone()

        if not row:
            await query.message.reply_text("❌ Савдо топилмади.")
            conn.close()
            return

        seller_id,buyer_id,points,status = row

        # 🔒 Фақат харидор босиши мумкин
        if query.from_user.id != buyer_id:
            await query.message.reply_text("❌ Бу операция сизга тегишли эмас.")
            conn.close()
            return
        
        if status != "waiting_payment":
            await query.message.reply_text("❌ Бу савдо ҳолати нотўғри.")
            conn.close()
            return
            
        conn.close()

        keyboard = [[
            InlineKeyboardButton(
                "✅ Пул олдим",
                callback_data=f"confirm_{trade_id}"
            )
        ]]

        await context.bot.send_message(
            chat_id=seller_id,
            text=f"💰 Уста {points} танга учун пул юборганини айтмоқда.\n\nПулни олдингизми?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("confirm_"):

        trade_id = int(data.split("_")[1])

        conn = get_connection()
        c = conn.cursor()

        c.execute("""
        SELECT seller_id,buyer_id,points,status
        FROM point_trades
        WHERE id=%s
        """,(trade_id,))

        row = c.fetchone()

        if not row:
            await query.message.reply_text("❌ Савдо топилмади.")
            conn.close()
            return

        seller_id,buyer_id,points,status = row

        c.execute("SELECT points FROM users WHERE telegram_id=%s",(seller_id,))
        row = c.fetchone()
        seller_points = row[0] if row else 0

        if seller_points < points:
            await query.message.reply_text("❌ Сотувчининг тангаси етарли эмас.")
            conn.close()
            return

        if status != "waiting_payment":
            await query.message.reply_text("❌ Бу савдо аллақачон якунланган.")
            conn.close()
            return

        if query.from_user.id != seller_id:
            await query.message.reply_text("❌ Фақат сотувчи тасдиқлаши мумкин.")
            conn.close()
            return

        # ⭐ сотувчидан балл айирамиз
        c.execute("""
        UPDATE users
        SET points = points - %s
        WHERE telegram_id=%s AND points >= %s
        """,(points,seller_id))

        # ⭐ баллни харидорга ўтказамиз
        c.execute("""
        UPDATE users
        SET points = points + %s
        WHERE telegram_id=%s
        """,(points,buyer_id))

        c.execute("""
        UPDATE point_trades
        SET status='completed'
        WHERE id=%s
        """,(trade_id,))

        conn.commit()
        conn.close()

        await context.bot.send_message(
            chat_id=buyer_id,
            text=f"✅ Савдо тугади.\n\n{points} танга сизга ўтказилди."
        )

        await query.message.reply_text("✅ Савдо муваффақиятли якунланди.")
    
    # ================= RATE =================
    elif data.startswith("rate_"):
        await start_rating(update, context)

    elif data == "admin_refresh":
        await admin_panel(update, context)

    elif data == "admin_top":
        await admin_top_masters(update, context)
        
    # ================= SET RATE =================
    elif data.startswith("setrate_"):
        parts = data.split("_")
        mid = int(parts[1])
        rating = int(parts[2])

        context.user_data["pending_rating_master"] = mid
        context.user_data["pending_rating_value"] = rating
        context.user_data["step"] = "write_comment"

        await query.message.reply_text(
            "📝 Изоҳ ёзинг (ихтиёрий).\n\n"
            "Ўтказиб юбориш учун '-' юборинг."
        )

    # ================= NEXT PAGE =================
    elif data.startswith("next_"):
        page = int(data.replace("next_", ""))
        context.user_data["page"] = page

        await show_masters(update, context)
        return

    # ================= PREV PAGE =================
    elif data.startswith("prev_"):
        page = int(data.replace("prev_", ""))
        context.user_data["page"] = page

        await show_masters(update, context)
        return

    # ================= EDIT PROFILE =================
    elif data == "edit_profile":

        print("EDIT PROFILE BLOCK ISHLADI")

        keyboard = [
            [InlineKeyboardButton("📝 Иш турлари", callback_data="edit_description")],
            [InlineKeyboardButton("📞 Телефон", callback_data="edit_phone")],
            [InlineKeyboardButton("🧰 Тажриба", callback_data="edit_experience")],
            [InlineKeyboardButton("🎂 Ёш", callback_data="edit_age")],
            [InlineKeyboardButton("🟢/🔴 Ҳолат", callback_data="edit_status")],
            [InlineKeyboardButton("⬅ Орқага", callback_data="back_to_profile")]
        ]

        await query.message.reply_text("Қайсини ўзгартирмоқчисиз?", reply_markup=InlineKeyboardMarkup(keyboard))
        return


    elif data == "edit_description":

        context.user_data["step"] = "edit_description"

        await query.message.reply_text("📝 Янги иш турларини ёзинг (300 белгидан оширманг):")
        return

    elif data == "edit_phone":

        context.user_data["step"] = "edit_phone"

        await query.message.reply_text("📞 Янги телефон рақамни ёзинг:")
        return

    elif data == "edit_experience":

        context.user_data["step"] = "edit_experience"

        await query.message.reply_text("🧰 Янги тажрибангиз (йилларда):")
        return

    elif data == "edit_age":

        context.user_data["step"] = "edit_age"

        await query.message.reply_text("🎂 Янги ёшингизни киритинг:")
        return

    elif data == "back_to_profile":

        await my_profile(update, context)
        return

    elif data == "edit_status":

        keyboard = [
            [InlineKeyboardButton("🟢 Бўш", callback_data="set_free")],
            [InlineKeyboardButton("🔴 Банд", callback_data="set_busy")]
        ]

        await query.message.reply_text("Ҳолатни танланг:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
        
    elif data == "set_free":

        conn = get_connection()
        c = conn.cursor()

        c.execute("""
            UPDATE masters
            SET is_busy = FALSE,
                busy_until = NULL
            WHERE telegram_id = %s
        """, (query.from_user.id,))

        conn.commit()
        conn.close()

        await query.message.reply_text("🟢 Сиз энди бўшсиз.")
        return

    elif data == "set_busy":

        context.user_data["step"] = "set_busy_date"

        await query.message.reply_text("📅 Қайси кунгача бандсиз?\n" "Формат: YYYY-MM-DD\n" "Масалан: 2026-02-25")
        return

# ================= STATISTIKA =================
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["waiting_for_code"] = False
    message = update.effective_message

    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users WHERE last_active IS NOT NULL AND last_active >= NOW() - INTERVAL '24 HOURS'")
    today_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM masters WHERE is_active=TRUE")
    total_masters = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM ratings")
    total_ratings = c.fetchone()[0]

    c.execute("SELECT 1 FROM masters WHERE telegram_id=%s AND is_active=TRUE", (update.effective_user.id,))
    is_master = c.fetchone() is not None

    conn.close()

    if language == "uz_kr":
        text = (
            f"📊 БОТ СТАТИСТИКАСИ:\n\n"
            f"👥 Жами фойдаланувчилар: {total_users}\n"
            f"📅 Бугунги фаоллар: {today_users}\n"
            f"👷 Жами усталар: {total_masters}\n"
            f"⭐ Жами баҳолар: {total_ratings}\n"
        )
    elif language == "uz_lt":
        text = (
            f"📊 BOT STATISTIKASI:\n\n"
            f"👥 Jami foydalanuvchilar: {total_users}\n"
            f"📅 Bugungi faollar: {today_users}\n"
            f"👷 Jami ustalar: {total_masters}\n"
            f"⭐ Jami baholar: {total_ratings}\n"
        )
    else:
        text = (
            f"📊 СТАТИСТИКА БОТА:\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"📅 Активные сегодня: {today_users}\n"
            f"👷 Всего мастеров: {total_masters}\n"
            f"⭐ Всего оценок: {total_ratings}\n"
        )

    menu, mode = build_main_menu(texts, is_master, context.user_data.get("mode"))
    context.user_data["mode"] = mode

    await message.reply_text(text)
    await message.reply_text(texts["welcome"], reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True))
    
# ================= PROFILE =================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user_id = update.effective_user.id

    conn = get_connection()
    c = conn.cursor()

    # 1) Асосий маълумот
    c.execute("""
        SELECT
            id,
            name,
            phone,
            service,
            region,
            district,
            age,
            experience,
            education,
            skills,
            code,
            service_description,
            is_busy,
            busy_until
        FROM masters
        WHERE telegram_id = %s AND is_active = TRUE
    """, (user_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        await message.reply_text("❌ Профил топилмади.")
        return

    (
        master_id,
        name,
        phone,
        service,
        region,
        district,
        age,
        experience,
        education,
        skills,
        code,
        service_description,
        is_busy,
        busy_until
    ) = row

    # 2) Жами буюртма
    c.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE master_id = %s
    """, (master_id,))
    total_orders = c.fetchone()[0]

    # 3) Рейтинг
    c.execute("""
        SELECT COALESCE(AVG(rating), 0), COUNT(*)
        FROM ratings
        WHERE master_id = %s
    """, (master_id,))
    avg_rating, total_votes = c.fetchone()

    conn.close()

    if is_busy and busy_until:
        status_text = f"🔴 Банд ({busy_until})"
    else:
        status_text = "🟢 Бўш"

    profile_text = (
        f"👷 {name or '-'}\n"
        f"🆔 Код: {code or '-'}\n"
        f"📞 {phone or '-'}\n"
        f"🛠 {service or '-'}\n"
        f"📍 {region or '-'} / {district or '-'}\n"
        f"{status_text}"
    )

    if age:
        profile_text += f"\n🎂 Ёш: {age}"
    if experience:
        profile_text += f"\n💼 Тажриба: {experience}"
    if education:
        profile_text += f"\n🎓 Маълумот: {education}"
    if skills:
        profile_text += f"\n🔧 Кўникмалар: {skills}"
    if service_description:
        profile_text += f"\n📝 Иш турлари: {service_description}"

    profile_text += (
        f"\n\n📊 СТАТИСТИКА:\n"
        f"📞 Жами чақирилган: {total_orders}\n"
        f"⭐ Ўртача рейтинг: {round(float(avg_rating), 1)}\n"
        f"🗳 Жами баҳолар: {total_votes}"
    )

    keyboard = [
        [InlineKeyboardButton("🔗 Менинг таклиф линким", callback_data="my_ref_link")],
        [InlineKeyboardButton("⚙ Профилни таҳрир қилиш", callback_data="edit_profile")],
        [InlineKeyboardButton("❌ Рўйхатдан чиқиш", callback_data="delete_profile")]
    ]

    await message.reply_text(
        profile_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
# ================= DELETE =================
async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    user = update.effective_user.id
    print(f"Unregister called by user: {user}, language: {language}")

    success = delete_master(user)
    print(f"Delete master result: {success}")

    menu, mode = build_main_menu(texts, False, "customer")
    context.user_data["mode"] = mode

    if success:
        await update.message.reply_text(
            texts["unregistered_success"],
            reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            texts["not_registered"],
            reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
        )
        
async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tilni o'zgartirish"""
    await update.message.reply_text(
        "🌐 Tilni tanlang / Выберите язык:\nChoose language:",
        reply_markup=build_language_menu()
    )

async def backup_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bazani backup qilish"""
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    print(f"Backup called by user: {update.effective_user.id}, language: {language}")

    menu, mode = build_main_menu(texts, False, "customer")
    context.user_data["mode"] = mode

    try:
        import json
        from datetime import datetime

        conn = get_connection()
        c = conn.cursor()

        c.execute("""
        SELECT m.id, m.telegram_id, m.name, m.phone, m.service, 
               m.region, m.district,
               COUNT(r.rating) as rating_count,
               COALESCE(AVG(r.rating), 0)
        FROM masters m
        LEFT JOIN ratings r ON m.id = r.master_id
        GROUP BY m.id
        ORDER BY m.id
        """)

        masters = []
        for row in c.fetchall():
            master = {
                "id": row[0],
                "telegram_id": row[1],
                "name": row[2],
                "phone": row[3],
                "service": row[4],
                "region": row[5],
                "district": row[6],
                "rating_count": row[7],
                "avg_rating": float(row[8])
            }
            masters.append(master)

        ratings_data = {}
        c.execute("SELECT master_id, user_id, rating FROM ratings")
        for master_id, user_id, rating in c.fetchall():
            if master_id not in ratings_data:
                ratings_data[master_id] = []
            ratings_data[master_id].append({
                "user_id": user_id,
                "rating": rating
            })

        conn.close()

        backup_data = {
            "backup_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_masters": len(masters),
            "masters": masters,
            "ratings": ratings_data
        }

        filename = f"masters_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        if language == "uz_kr":
            message = (
                f"✅ Backup муваффақиятли яратилди!\n"
                f"📁 Файл: {filename}\n"
                f"👤 Усталар: {len(masters)} та\n"
                f"⭐ Рейтинглар: {sum(len(r) for r in ratings_data.values())} та"
            )
        elif language == "uz_lt":
            message = (
                f"✅ Backup muvaffaqiyatli yaratildi!\n"
                f"📁 Fayl: {filename}\n"
                f"👤 Ustalar: {len(masters)} ta\n"
                f"⭐ Reytinglar: {sum(len(r) for r in ratings_data.values())} ta"
            )
        else:
            message = (
                f"✅ Backup успешно создан!\n"
                f"📁 Файл: {filename}\n"
                f"👤 Мастеров: {len(masters)}\n"
                f"⭐ Оценок: {sum(len(r) for r in ratings_data.values())}"
            )

        await update.message.reply_text(
            message,
            reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
        )

    except Exception as e:
        await update.message.reply_text(
            texts["backup_error"] + f" {str(e)}",
            reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
        )
        
# ================= DB HELPERS =================

def can_rate(user_id, master_id):
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT 1 FROM orders
        WHERE user_id=%s AND master_id=%s AND status='completed'
    """, (user_id, master_id))

    result = c.fetchone()
    conn.close()

    return result is not None

# ================= LEVEL SYSTEM =================
def get_user_level(points):
    if points >= 1000:
        return "👑 GOLD"
    elif points >= 500:
        return "🥈 SILVER"
    elif points >= 100:
        return "🥉 BRONZE"
    else:
        return "👤 START"

# ================= MAIN MENU BUILDER =================
def build_main_menu(texts, is_master, mode=None):
    if is_master:
        return [row[:] for row in texts["master_menu"]], "master"
    else:
        return [row[:] for row in texts["customer_menu"]], "customer"
    
async def start_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    mid = data.replace("rate_", "")

    keyboard = [
        [
            InlineKeyboardButton("⭐", callback_data=f"setrate_{mid}_1"),
            InlineKeyboardButton("⭐⭐", callback_data=f"setrate_{mid}_2"),
            InlineKeyboardButton("⭐⭐⭐", callback_data=f"setrate_{mid}_3"),
        ],
        [
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"setrate_{mid}_4"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"setrate_{mid}_5"),
        ],
    ]

    await query.message.reply_text("Устага нечта юлдуз берасиз?", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 Сизнинг Telegram ID: {user_id}")

async def admin_master_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Фойдаланиш: /mstat 1234")
        return

    code = context.args[0]

    if not code.isdigit():
        await update.message.reply_text("Код рақам бўлиши керак.")
        return

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT 
            m.name,
            m.phone,
            m.service,
            m.region,
            m.district,
            COUNT(DISTINCT o.id) as total_orders,
            COALESCE(AVG(r.rating), 0) as avg_rating,
            COUNT(DISTINCT r.id) as total_votes,
            m.is_busy,
            m.busy_until,
            m.is_active
        FROM masters m
        LEFT JOIN orders o ON m.id = o.master_id
        LEFT JOIN ratings r ON m.id = r.master_id
        WHERE m.code=%s
        GROUP BY 
            m.name, m.phone, m.service, m.region, m.district,
            m.is_busy, m.busy_until, m.is_active
    """, (code,))

    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("Уста топилмади.")
        return

    name, phone, service, region, district, total_orders, avg_rating, total_votes, is_busy, busy_until, is_active = row

    # статус
    if not is_active:
        active_status = "❌ НОАКТИВ"
    else:
        active_status = "✅ АКТИВ"

    if is_busy:
        busy_status = f"🔴 Банд ({busy_until})"
    else:
        busy_status = "🟢 Бўш"

    text = f"""
👷 УСТА СТАТИСТИКАСИ

🆔 Код: {code}
👤 {name}
📞 {phone}
🛠 {service}
📍 {region} / {district}

📊 Статистика:
📞 Жами буюртма: {total_orders}
⭐ Ўртача рейтинг: {round(avg_rating,1)}
🗳 Жами баҳолар: {total_votes}

{busy_status}
{active_status}
"""

    message = update.effective_message
    await message.reply_text(text)

async def admin_top_masters(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    # 👇 универсал message оламиз
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT m.name, m.code, COUNT(o.id) as total_orders
        FROM masters m
        LEFT JOIN orders o ON m.id = o.master_id
        WHERE m.is_active=TRUE
        GROUP BY m.name, m.code
        ORDER BY total_orders DESC
        LIMIT 10
    """)

    rows = c.fetchall()
    conn.close()

    if not rows:
        text = "🏆 Топ усталар йўқ."
    else:
        text = "🏆 <b>ТОП 10 УСТА</b>\n\n"
        for i, row in enumerate(rows, 1):
            text += f"{i}. {row[0]} (🆔 {row[1]}) — {row[2]} та\n"

    await message.reply_text(text, parse_mode="HTML")
    
async def admin_week_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    conn = get_connection()
    c = conn.cursor()

    # 📦 7 кундаги буюртмалар
    c.execute("""
        SELECT COUNT(*) 
        FROM orders
        WHERE created_at >= NOW() - INTERVAL '7 days'
    """)
    week_orders = c.fetchone()[0]

    # ⭐ 7 кундаги рейтинглар
    c.execute("""
        SELECT COUNT(*)
        FROM ratings
        WHERE created_at >= NOW() - INTERVAL '7 days'
    """)
    week_ratings = c.fetchone()[0]

    # 👥 7 кундаги янги фойдаланувчилар
    c.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE created_at >= NOW() - INTERVAL '7 days'
    """)
    week_users = c.fetchone()[0]

    # 👷 7 кундаги янги усталар
    c.execute("""
        SELECT COUNT(*)
        FROM masters
        WHERE created_at >= NOW() - INTERVAL '7 days'
    """)
    week_masters = c.fetchone()[0]

    # 🥇 Энг фаол уста (7 кунда)
    c.execute("""
        SELECT m.name, m.code, COUNT(o.id) as total
        FROM masters m
        JOIN orders o ON m.id = o.master_id
        WHERE o.created_at >= NOW() - INTERVAL '7 days'
        GROUP BY m.name, m.code
        ORDER BY total DESC
        LIMIT 1
    """)
    top_master = c.fetchone()

    conn.close()

    text = "📊 ПРО 7 КУНЛИК АНАЛИТИКА\n\n"
    text += f"📦 Буюртмалар: {week_orders}\n"
    text += f"⭐ Рейтинглар: {week_ratings}\n"
    text += f"👥 Янги фойдаланувчилар: {week_users}\n"
    text += f"👷 Янги усталар: {week_masters}\n\n"

    if top_master:
        text += f"🥇 Энг фаол уста:\n{top_master[0]} (🆔 {top_master[1]}) — {top_master[2]} та\n"
    else:
        text += "🥇 Энг фаол уста йўқ\n"

    message = update.effective_message
    await message.reply_text(text)

async def show_news(update: Update, context: ContextTypes.DEFAULT_TYPE):

    language = context.user_data.get("language", "uz_kr")

    if language == "uz_kr":
        text = (
            "📢 <b>БОТ ЯНГИЛИКЛАРИ</b>\n\n"

            "🆕 <b>08.03.2026</b>\n"
            "🪙 Ботда янги <b>ТАНГА</b> тизими ишга тушди!\n\n"
            "Энди фойдаланувчилар бот ичида танга йиғишлари мумкин.\n\n"
            "🎁 Танга йиғиш усуллари:\n"
            "• Дўстларни таклиф қилиш\n"
            "• Ботдан фаол фойдаланиш\n\n"
            "🚀 Келгусида ушбу тангаларни:\n"
            "💰 Бот ичидаги ички биржа орқали сотиш\n"
            "👑 VIP уста мақомини олиш\n"
            "🎁 Турли бонус ва имтиёзларга алмаштириш\n\n"
            "мумкин бўлади.\n\n"
            "🏆 Энг кўп танга тўплаган фойдаланувчилар учун махсус бонуслар ҳам жорий қилинади.\n\n"
            "⚡ Шунинг учун ҳозирдан танга йиғишни бошланг!\n\n"

            "🆕 <b>23.02.2026</b>\n"
            "🚀 Усталар учун катта янгилик!\n"
            "➕ Қўшимча хизмат турларини белгилаш имконияти қўшилди.\n"
            "🔎 Энди устани махсус 4 хонали код орқали тез топиш мумкин.\n"
            "🟢🔴 Профилда банд ёки бўш ҳолатни кўрсатиш имконияти яратилди.\n"
            "✏️ Профил маълумотларини таҳрирлаш мумкин.\n"
            "⚠️ Илтимос, профилингизни янгилаб чиқинг!\n\n"

            "🆕 <b>23.02.2026</b>\n"
            "🔥 Пайвандчи хизмати қўшилди\n\n"

            "🆕 <b>15.02.2026</b>\n"
            "🚀 Уста топиш боти расман ишга тушди!\n"
            "🔎 Турли соҳа усталарини осон ва тез топиш мумкин.\n"
            "📞 Бевосита қўнғироқ қилиш имконияти мавжуд.\n"
            "⭐ Усталарни баҳолаш тизими жорий қилинди.\n\n"
        )

    elif language == "uz_lt":
        text = (
            "📢 <b>BOT YANGILIKLARI</b>\n\n"

            "🆕 <b>08.03.2026</b>\n"
            "🪙 Botda yangi <b>TANGA</b> tizimi ishga tushdi!\n\n"
            "Endi foydalanuvchilar bot ichida tanga yig'ishlari mumkin.\n\n"
            "🎁 Tanga yig'ish usullari:\n"
            "• Do'stlarni taklif qilish\n"
            "• Botdan faol foydalanish\n\n"
            "🚀 Kelgusida ushbu tangalarni:\n"
            "💰 Bot ichidagi ichki birja orqali sotish\n"
            "👑 VIP usta maqomini olish\n"
            "🎁 Turli bonus va imtiyozlarga almashtirish\n\n"
            "mumkin bo'ladi.\n\n"
            "🏆 Eng ko'p tanga to'plagan foydalanuvchilar uchun maxsus bonuslar ham joriy qilinadi.\n\n"
            "⚡ Shuning uchun hozirdan tanga yig'ishni boshlang!\n\n"

            "🆕 <b>23.02.2026</b>\n"
            "🚀 Ustalar uchun katta yangilik!\n"
            "➕ Qo'shimcha xizmat turlarini belgilash imkoniyati qo'shildi.\n"
            "🔎 Endi ustani maxsus 4 xonali kod orqali tez topish mumkin.\n"
            "🟢🔴 Profilda band yoki bo'sh holatni ko'rsatish imkoniyati yaratildi.\n"
            "✏️ Profil ma'lumotlarini tahrirlash mumkin.\n"
            "⚠️ Iltimos, profilingizni yangilab chiqing!\n\n"

            "🆕 <b>23.02.2026</b>\n"
            "🔥 Payvandchi xizmati qo'shildi\n\n"

            "🆕 <b>15.02.2026</b>\n"
            "🚀 Usta topish boti rasman ishga tushdi!\n"
            "🔎 Turli soha ustalarini oson va tez topish mumkin.\n"
            "📞 Bevosita qo'ng'iroq qilish imkoniyati mavjud.\n"
            "⭐ Ustalarni baholash tizimi joriy qilindi.\n\n"
        )

    else:
        text = (
            "📢 <b>НОВОСТИ БОТА</b>\n\n"

            "🆕 <b>08.03.2026</b>\n"
            "🪙 В боте появилась новая <b>система монет</b>!\n\n"
            "Теперь пользователи могут накапливать монеты внутри бота.\n\n"
            "🎁 Как получать монеты:\n"
            "• Приглашать друзей\n"
            "• Активно пользоваться ботом\n\n"
            "🚀 В будущем эти монеты можно будет:\n"
            "💰 Продавать через внутреннюю биржу бота\n"
            "👑 Получать VIP статус мастера\n"
            "🎁 Обменивать на различные бонусы и привилегии\n\n"
            "🏆 Пользователи с наибольшим количеством монет будут получать специальные бонусы.\n\n"
            "⚡ Начинайте собирать монеты уже сейчас!\n\n"

            "🆕 <b>23.02.2026</b>\n"
            "🚀 Важное обновление для мастеров!\n"
            "➕ Добавлена возможность указывать дополнительные виды услуг.\n"
            "🔎 Теперь мастера можно быстро найти по специальному 4-значному коду.\n"
            "🟢🔴 Добавлена возможность указывать статус: занят или свободен.\n"
            "✏️ Появилась возможность редактировать профиль.\n"
            "⚠️ Рекомендуем обновить свой профиль!\n\n"

            "🆕 <b>23.02.2026</b>\n"
            "🔥 Добавлена услуга: Сварщик\n\n"

            "🆕 <b>15.02.2026</b>\n"
            "🚀 Бот для поиска мастеров официально запущен!\n"
            "🔎 Теперь можно быстро находить мастеров разных сфер.\n"
            "📞 Есть возможность напрямую позвонить мастеру.\n"
            "⭐ Введена система рейтингов.\n\n"
        )

    await update.message.reply_text(text, parse_mode="HTML")

async def broadcast_news(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT telegram_id, language FROM users")
    users = c.fetchall()

    conn.close()

    sent = 0

    for user_id, language in users:

        if language == "uz_kr":
            text = (
                "📢 <b>БОТ ЯНГИЛИКЛАРИ</b>\n\n"

                "🪙 Ботда янги <b>ТАНГА</b> тизими ишга тушди!\n\n"
                "Энди фойдаланувчилар бот ичида танга йиғишлари мумкин.\n\n"

                "🎁 Танга йиғиш усуллари:\n"
                "• Дўстларни таклиф қилиш\n"
                "• Ботдан фаол фойдаланиш\n\n"

                "🚀 Келгусида ушбу тангаларни:\n"
                "💰 Бот ичидаги ички биржа орқали сотиш\n"
                "👑 VIP уста мақомини олиш\n"
                "🎁 Турли бонус ва имтиёзларга алмаштириш\n\n"

                "мумкин бўлади.\n\n"

                "🏆 Энг кўп танга тўплаган фойдаланувчилар учун махсус бонуслар ҳам жорий қилинади.\n\n"

                "⚡ Шунинг учун ҳозирдан танга йиғишни бошланг!"
            )

        elif language == "uz_lt":
            text = (
                "📢 <b>BOT YANGILIKLARI</b>\n\n"

                "🪙 Botda yangi <b>TANGA</b> tizimi ishga tushdi!\n\n"
                "Endi foydalanuvchilar bot ichida tanga yig'ishlari mumkin.\n\n"

                "🎁 Tanga yig'ish usullari:\n"
                "• Do'stlarni taklif qilish\n"
                "• Botdan faol foydalanish\n\n"

                "🚀 Kelgusida ushbu tangalarni:\n"
                "💰 Bot ichidagi ichki birja orqali sotish\n"
                "👑 VIP usta maqomini olish\n"
                "🎁 Turli bonus va imtiyozlarga almashtirish\n\n"

                "mumkin bo'ladi.\n\n"

                "🏆 Eng ko'p tanga to'plagan foydalanuvchilar uchun maxsus bonuslar ham joriy qilinadi.\n\n"

                "⚡ Shuning uchun hozirdan tanga yig'ishni boshlang!"
            )

        else:
            text = (
                "📢 <b>НОВОСТИ БОТА</b>\n\n"

                "🪙 В боте появилась новая <b>система монет</b>!\n\n"
                "Теперь пользователи могут накапливать монеты внутри бота.\n\n"

                "🎁 Как получать монеты:\n"
                "• Приглашать друзей\n"
                "• Активно пользоваться ботом\n\n"

                "🚀 В будущем эти монеты можно будет:\n"
                "💰 Продавать через внутреннюю биржу бота\n"
                "👑 Получать VIP статус мастера\n"
                "🎁 Обменивать на различные бонусы и привилегии\n\n"

                "🏆 Пользователи с наибольшим количеством монет будут получать специальные бонусы.\n\n"

                "⚡ Начинайте собирать монеты уже сейчас!"
            )

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML"
            )
            sent += 1

        except:
            pass

    await update.message.reply_text(f"✅ Янгилик {sent} та фойдаланувчига юборилди.")
   
async def activestats(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Рухсат йўқ")
        return

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE last_active >= NOW() - INTERVAL '7 days'
    """)
    active = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]

    conn.close()

    percent = round((active / total) * 100, 1) if total > 0 else 0

    await update.message.reply_text(
        f"📊 7 кунлик актив: {active}\n"
        f"👥 Жами фойдаланувчи: {total}\n"
        f"📈 Активлик: {percent}%"
    )
    
def main():
    print("PRO VERSION STARTING...")
    init_db()
    ensure_code_column()

    app = ApplicationBuilder().token(TOKEN).build()

    # =========================
    # 🔹 COMMAND HANDLERS
    # =========================
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("vip", give_vip))
    app.add_handler(CommandHandler("broadcast", broadcast_news))

    # 📊 ADMIN ANALYTICS COMMANDS
    app.add_handler(CommandHandler("mstat", admin_master_stats))
    app.add_handler(CommandHandler("topmasters", admin_top_masters))
    app.add_handler(CommandHandler("weekstats", admin_week_stats))
    app.add_handler(CommandHandler("activestats", activestats))

    # =========================
    # 🔹 ADMIN CALLBACKS (Алоҳида!)
    # =========================
    app.add_handler(CallbackQueryHandler(admin_vip_menu, pattern="^admin_vip$"))
    app.add_handler(CallbackQueryHandler(admin_vip_list, pattern="^admin_vip_list$"))

    # =========================
    # 🔹 УНИВЕРСАЛ CALLBACK ROUTER
    # =========================
    app.add_handler(CallbackQueryHandler(callback_router))

    # =========================
    # 🔹 LANGUAGE SELECTION
    # =========================
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(Узбек \\(кирилл\\)|O'zbek \\(lotin\\)|Русский)$"), choose_language), group=0)

    # =========================
    # 🔹 REGISTER FLOW
    # =========================
    app.add_handler(MessageHandler(filters.CONTACT, get_phone))
    
    # =========================
    # 🔹 PROFILE
    # =========================
    
    app.add_handler(MessageHandler(filters.Regex("^(Рўйхатдан чиқиш|Ro'yxatdan chiqish|Выйти)$"), unregister))

    # =========================
    # 🔹 BACKUP
    # =========================
    app.add_handler(MessageHandler(filters.Regex("^(📢 Бот янгиликлари|📢 Bot yangiliklari|📢 Новости бота)$"), show_news))
    app.add_handler(MessageHandler(filters.Regex("^💾 Backup$"), backup_database))

    # =========================
    # 🔹 STATISTICS
    # =========================
    app.add_handler(MessageHandler(filters.Regex("^(Статистика|Statistika|Статистика)$"), show_stats))

    # =========================
    # 🔹 TEXT ROUTER (ЭНГ ОХИРИДА!)
    # =========================
    #app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router), group=1)

    # 🔹 LOCATION ROUTER
    app.add_handler(MessageHandler(filters.LOCATION, location_router), group=1)

    print("BOT IS RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()

































































































