import psycopg2
import os
import sqlite3
from services import SERVICES
from regions import REGIONS
from languages import LANGUAGES, get_texts, LANGUAGE_NAMES
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters)
ADMIN_ID = 1970756498

TOKEN = os.getenv("TOKEN")

def ensure_code_column():
    print("🔍 ensure_code_column ишлаяпти...")

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
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
    while True:
        code = str(random.randint(1000, 9999))
        cursor.execute("SELECT 1 FROM masters WHERE code = %s", (code,))
        if not cursor.fetchone():
            return code
    
# ================= DATABASE =================
def init_db():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
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
        skills TEXT
    )
    """)

    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS vip BOOLEAN DEFAULT FALSE")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS vip_until TIMESTAMP")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS service_description VARCHAR(300)")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS is_busy BOOLEAN DEFAULT FALSE")
    c.execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS busy_until DATE")

    # ====== BAHOLAR ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS ratings (
        id SERIAL PRIMARY KEY,
        master_id INTEGER,
        user_id BIGINT,
        rating INTEGER
    )
    """)

    c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_rating ON ratings(master_id, user_id)""")

    # ====== FOYDALANUVCHILAR ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        telegram_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TEXT,
        last_active TEXT,
        message_count INTEGER DEFAULT 0
    )
    """)

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
    
    conn.commit()
    conn.close()


# ================= USTA QO‘SHISH =================
def add_master(telegram_id, name, phone, service, region, district, age=None, experience=None, service_description=None):
    import psycopg2, os

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
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
        service_description = EXCLUDED.service_description
    """, (
        telegram_id, name, phone, service, region, district, age, experience, code, service_description
    ))

    conn.commit()
    conn.close()

# ================= USTANI TOPISH =================
def find_masters(service, region, district):
    import psycopg2, os

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    c.execute("""
    SELECT id, name, phone, region, district, service, age, experience, vip, vip_until
    FROM masters
    WHERE service ILIKE %s
      AND region ILIKE %s
      AND district ILIKE %s
    ORDER BY 
        vip DESC,
        vip_until DESC NULLS LAST
    """, (
        "%" + service + "%",
        "%" + region + "%",
        "%" + district + "%"
    ))

    data = c.fetchall()
    conn.close()
    return data


# ================= RO‘YXATDAN CHIQARISH =================
def delete_master(telegram_id):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    # Avval ustani ID sini topamiz
    c.execute("SELECT id FROM masters WHERE telegram_id=%s", (telegram_id,))
    master = c.fetchone()
    
    if master:
        master_id = master[0]
        # AVVAL reytinglarni o'chiramiz
        c.execute("DELETE FROM ratings WHERE master_id=%s", (master_id,))
        # KEYIN ustani o'chiramiz
        c.execute("DELETE FROM masters WHERE telegram_id=%s", (telegram_id,))
        print(f"Usta {master_id} va uning {c.rowcount} ta reytingi ochirildi")
    
    conn.commit()
    conn.close()
    return master is not None


# ================= MENUS =================
MAIN_MENU = ReplyKeyboardMarkup([
    ["Уста топиш", "Уста бўлиш"],
    ["Менинг профилим", "Статистика"],
    ["Рўйхатдан чиқиш", "💾 Backup"]
], resize_keyboard=True)


def build_service_menu(language="uz_kr"):
    services = SERVICES.get(language, SERVICES["uz_kr"])

    keyboard = []
    row = []

    for i, service in enumerate(services, 1):
        row.append(service)
        if i % 2 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    back_text = "Орқага" if language == "uz_kr" else "Orqaga" if language == "uz_lt" else "Назад"
    keyboard.append([back_text])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
def build_region_menu(language="uz_kr"):
    regions = REGIONS.get(language, REGIONS["uz_kr"])

    keyboard = []
    row = []

    for i, region in enumerate(regions.keys(), 1):
        row.append(region)
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
def build_city_menu(region, language="uz_kr"):
    regions_data = REGIONS.get(language, REGIONS["uz_kr"])
    cities = regions_data.get(region, [])

    keyboard = []
    row = []

    for i, city in enumerate(cities, 1):
        row.append(city)
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
    keyboard = [[LANGUAGES[lang]] for lang in LANGUAGES.keys()]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Til tanlash"""
    text = update.message.text
    
    print(f"choose_language called with text: {text}")
    print(f"LANGUAGES dict: {LANGUAGES}")
    
    # Tilni topish
    language = None
    for lang_code, lang_name in LANGUAGES.items():
        print(f"Checking: {lang_code} -> {lang_name}")
        if text == lang_name:
            language = lang_code
            print(f"Found language: {language}")
            break
    
    print(f"Final language: {language}")
    
    if language:
        context.user_data["language"] = language
        texts = get_texts(language)
        
        # Asosiy menuni yangilash
        context.user_data.clear()
        context.user_data["language"] = language
        
        # Фикр-мулохазалар ва шикоятлар
        feedback_text = ""
        if language == "uz_kr":
            feedback_text = "💡 Фикр-мулохазалар ва шикоятлар:\n\n" "@botir_support"
        elif language == "uz_lt":
            feedback_text = "💡 Fikr-mulohazalar va shikoyatlar:\n\n" "@botir_support"
        else:  # ru
            feedback_text = "💡 Замечания и предложения:\n\n" "@botir_support"
        
        await update.message.reply_text(texts["welcome"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
    else:

        await update.message.reply_text(
            "Илтимос, тилни танланг:",
            reply_markup=build_language_menu()
        )

# ================= FOYDALANUVCHI QO'SHISH =================
def log_user(user):
    from datetime import datetime
    import psycopg2, os

    print("LOGGING USER:", user.id)

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

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
        datetime.now(),
        datetime.now()
    ))

    conn.commit()
    conn.close()

    print("USER SAVED")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user(update.effective_user)

    language = context.user_data.get("language", "uz_kr")
    context.user_data["language"] = language

    texts = get_texts(language)

    await update.message.reply_text(texts["welcome"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics")],
        [InlineKeyboardButton("⭐ VIP бериш", callback_data="admin_vip")],
        [InlineKeyboardButton("📋 VIP рўйхати", callback_data="admin_vip_list")]
    ]

    await update.message.reply_text("🛠 ADMIN PANEL", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
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

    await query.message.reply_text("VIP бериш учун устанинг telegram_id ни киритинг:")

async def admin_vip_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
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

    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Устанинг хабарини reply қилиб /vip ёзинг.")
        return

    master_tid = update.message.reply_to_message.from_user.id

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    # ⭐ Аввал текширамиз
    c.execute("SELECT id FROM masters WHERE telegram_id=%s", (master_tid,))
    if not c.fetchone():
        conn.close()
        await update.message.reply_text("❌ Бу фойдаланувчи уста эмас.")
        return

    # ⭐ Кейин VIP қиламиз
    c.execute("""
        UPDATE masters
        SET vip = TRUE,
            vip_until = NOW() + INTERVAL '30 days'
        WHERE telegram_id = %s
    """, (master_tid,))

    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Уста 30 кунга VIP қилинди.")

    await context.bot.send_message(chat_id=master_tid, text="🌟 Табриклаймиз! Сиз 30 кунга VIP уста бўлдингиз!")

# ================= SO'ZLARNI TOZALASH =================
def clean_text(text):
    """Noto'g'ri so'zlarni filtrlash"""
    import re
    
    # Lotin harflari, kirill harflari, raqamlar va belgilardan tashqari hamma narsani olib tashlash
    text = re.sub(r'[^\w\s\u0400-\u04FF\-.,()]', '', text)
    
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
    context.user_data.clear()
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
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
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
    
    region = update.message.text

    if region not in regions_data:
        return

    context.user_data["region"] = region
    context.user_data["step"] = "district"

    await update.message.reply_text(texts["choose_district"], reply_markup=build_city_menu(region, language))


async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    region = update.message.text
    context.user_data["region"] = region
    context.user_data["step"] = "district"
    
    # Tilga mos "Қайси шаҳар%s" matni
    if language == "uz_kr":
        question = "Қайси шаҳар%s"
    elif language == "uz_lt":
        question = "Qaysi shahar%s"
    else:  # ru
        question = "Какой город%s"
    
    await update.message.reply_text(question, reply_markup=build_city_menu(region, language))

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

    if not update.message or not update.message.text:
        return

    text = update.message.text
    log_user(update.effective_user)

    # 🌐 Тил
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    # 🔎 Код орқали қидиришни бошлаш
    if text in [
        "🔎 Код орқали қидириш",
        "🔎 Kod orqali qidirish",
        "🔎 Поиск по коду"
    ]:
        context.user_data["waiting_for_code"] = True

        await update.message.reply_text(
            "🆔 Уста кодини киритинг (4 рақам):\n\n"
            "❌ Бекор қилиш учун 'Орқага' деб ёзинг."
        )
        return

    # 🔢 Код киритиш режими
    if context.user_data.get("waiting_for_code"):

        # 🔙 Орқага
        if text in ["Орқага", "Orqaga", "Назад"]:
            context.user_data["waiting_for_code"] = False
            await update.message.reply_text(
                texts["welcome"],
                reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True)
            )
            return

        code = text.strip()

        if not code.isdigit() or len(code) != 4:
            await update.message.reply_text(
                "❌ Код 4 хоналик рақам бўлиши керак.\n\n"
                "Қайта киритинг ёки 'Орқага' деб ёзинг."
            )
            return

        # 🔍 БАЗАДАН ҚИДИРИШ
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        c = conn.cursor()

        c.execute("""
            SELECT id, name, phone, district, age, experience, vip
            FROM masters
            WHERE code = %s
        """, (code,))

        master = c.fetchone()
        conn.close()

        if master:
            mid, name, phone, district, age, experience, vip = master

            badge = f"👑 VIP УСТА • 🆔 {code}" if vip else f"👷 УСТА • 🆔 {code}"

            text_msg = f"""
    ══════════════════════════
    <b>{badge}</b>

    👤 <b>{name}</b>
    📍 {district}
    🎂 {age} ёш
    🧰 {experience} йил тажриба
    📞 <b>+{phone}</b>
    ══════════════════════════
    """

            keyboard = [[
                InlineKeyboardButton("📞 Қўнғироқ", callback_data=f"call_{phone}"),
                InlineKeyboardButton("✅ Чақирдим", callback_data=f"order_{mid}"),
                InlineKeyboardButton("⭐ Баҳо", callback_data=f"rate_{mid}")
            ]]

            await update.message.reply_text(
                text_msg,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            context.user_data["waiting_for_code"] = False

        else:
            await update.message.reply_text(
                "❌ Бундай код топилмади.\n\n"
                "Қайта киритинг ёки 'Орқага' деб ёзинг."
            )

        return
        
  
    # =====================================================
    # ⭐ ADMIN VIP INPUT
    # =====================================================
    if context.user_data.get("step") == "vip_input":

        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Рухсат йўқ")
            context.user_data.pop("step", None)
            return

        telegram_id = text.strip()

        if not telegram_id.isdigit():
            await update.message.reply_text("❌ Фақат рақам киритинг!")
            return

        telegram_id = int(telegram_id)

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        c = conn.cursor()

        c.execute("SELECT id FROM masters WHERE telegram_id=%s", (telegram_id,))
        master = c.fetchone()

        if not master:
            conn.close()
            await update.message.reply_text("❌ Бундай telegram_id топилмади!")
            return

        c.execute("""
            UPDATE masters
            SET vip = TRUE,
                vip_until = NOW() + INTERVAL '30 days'
            WHERE telegram_id = %s
        """, (telegram_id,))

        conn.commit()
        conn.close()

        await update.message.reply_text("✅ Уста 30 кунга VIP қилинди.")

        context.user_data.pop("step", None)
        return

    # =====================================================
    # ⭐ RATING
    # =====================================================
    if context.user_data.get("step") == "rating":
        await save_rating(update, context)
        return

    # =====================================================
    # 📩 ADMIN ЁЗИШ
    # =====================================================
    if "админ" in text.lower() or "yoz" in text.lower():
        await write_admin(update, context)
        return

    # =====================================================
    # 📊 Статистика
    # =====================================================
    if text == texts["statistics"]:
        await show_stats(update, context)
        return

    # =====================================================
    # 🔎 Уста топиш
    # =====================================================
    if text == texts["find_master"]:
        context.user_data["flow"] = "find"
        context.user_data["step"] = "service"

        await update.message.reply_text(
            texts["choose_service"],
            reply_markup=build_service_menu(language)
        )
        return

    # =====================================================
    # 🔙 Орқага
    # =====================================================
    if text in ["Орқага", "Orqaga", "Назад"]:
        context.user_data.pop("step", None)
        context.user_data.pop("flow", None)

        await update.message.reply_text(
            texts["welcome"],
            reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True)
        )
        return

    # =====================================================
    # 🔄 STEP логика
    # =====================================================
    step = context.user_data.get("step")
    
    # ================= EDIT PHONE =================
    if step == "edit_phone":

        phone = update.message.text.strip()

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        c = conn.cursor()

        c.execute("""
            UPDATE masters
            SET phone=%s
            WHERE telegram_id=%s
        """, (phone, update.effective_user.id))

        conn.commit()
        conn.close()

        await update.message.reply_text("✅ Телефон янгиланди.")
        context.user_data["step"] = None
        return

    # ================= EDIT EXPERIENCE =================
    if step == "edit_experience":

        exp = update.message.text.strip()

        if not exp.isdigit():
            await update.message.reply_text("❗ Фақат рақам киритинг.")
            return

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        c = conn.cursor()

        c.execute("""
            UPDATE masters
            SET experience=%s
            WHERE telegram_id=%s
        """, (exp, update.effective_user.id))

        conn.commit()
        conn.close()

        await update.message.reply_text("✅ Тажриба янгиланди.")
        context.user_data["step"] = None
        return
       
    # ================= EDIT AGE =================
    if step == "edit_age":

        age = update.message.text.strip()

        if not age.isdigit():
            await update.message.reply_text("❗ Фақат рақам киритинг.")
            return

        if int(age) < 16 or int(age) > 80:
            await update.message.reply_text("❗ Ёш нотўғри киритилди.")
            return

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        c = conn.cursor()

        c.execute("""
            UPDATE masters
            SET age=%s
            WHERE telegram_id=%s
        """, (age, update.effective_user.id))

        conn.commit()
        conn.close()

        await update.message.reply_text("✅ Ёш янгиланди.")
        context.user_data["step"] = None
        return
        
    # ================= EDIT DESCRIPTION =================
    if step == "edit_description":

        text_input = update.message.text.strip()

        if len(text_input) > 300:
            await update.message.reply_text("❗ 300 белгидан оширманг.")
            return

        description = clean_text(text_input)

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        c = conn.cursor()

        c.execute("""
            UPDATE masters
            SET service_description=%s
            WHERE telegram_id=%s
        """, (description, update.effective_user.id))

        conn.commit()
        conn.close()

        await update.message.reply_text("✅ Иш турлари янгиланди.")

        context.user_data["step"] = None
        return
            
    # ================= DESCRIPTION =================
    if step == "description":

        text_input = update.message.text.strip()

        if text_input == "-":
            description = None
        else:
            if len(text_input) > 300:
                await update.message.reply_text("❗ 300 белгидан оширманг.")
                return

            description = clean_text(text_input)

        telegram_id = update.effective_user.id

        add_master(
            telegram_id,
            context.user_data.get("name"),
            context.user_data.get("phone"),
            context.user_data.get("service"),
            context.user_data.get("region"),
            context.user_data.get("district"),
            context.user_data.get("age"),
            context.user_data.get("experience"),
            description
        )

        await update.message.reply_text(
            "✅ Муваффақият! Сиз уста сифатида рўйхатдан ўтдингиз.",
            reply_markup=ReplyKeyboardMarkup(get_texts(language)["main_menu"], resize_keyboard=True)
        )

        language = context.user_data.get("language", "uz_kr")
        context.user_data.clear()
        context.user_data["language"] = language

        return
    
    # AGE
    if step == "age":
        await get_age(update, context)
        return

    # EXPERIENCE
    if step == "experience":
        await get_experience(update, context)
        return

    # SERVICE
    if step == "service":

        if context.user_data.get("flow") == "find":
            await find_service(update, context)
            return
        else:
            services_list = SERVICES.get(language, SERVICES["uz_kr"])

            if text in services_list:
                context.user_data["service"] = text
                context.user_data["step"] = "region"

                await update.message.reply_text(
                    texts["choose_region"],
                    reply_markup=build_region_menu(language)
                )
                return

    # REGION
    if step == "region":
        await ask_region(update, context)
        return

    # DISTRICT
    if step == "district":
        await get_district(update, context)
        return

async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE):

    selected_region = context.user_data.get("region")
    selected_district = update.message.text

    # 🔥 Mapping аввал
    uz_region = map_region_to_uzkr(selected_region)
    uz_district = map_district_to_uzkr(selected_region, selected_district)
    uz_service = map_service_to_uzkr(context.user_data.get("service"))

    # 🔥 Текшириш фақат uz_kr бўйича
    if uz_district not in REGIONS["uz_kr"].get(uz_region, []):
        return

    context.user_data["region"] = uz_region
    context.user_data["district"] = uz_district
    context.user_data["service"] = uz_service

    # ===== FIND =====
    if context.user_data.get("flow") == "find":
        await show_masters(update, context)
        return

    # ===== REGISTER =====
    if context.user_data.get("flow") == "register":
        await update.message.reply_text(
            "Ёшингизни киритинг:",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data["step"] = "age"

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    if context.user_data.get("flow") != "register":
        return
    
    if context.user_data.get("step") != "age":
        return

    age = clean_text(update.message.text)
    
    # 🔥 МАНА ШУ ЕРГА return қўшамиз
    if not age or not age.isdigit() or len(age) > 2:
        await update.message.reply_text(texts["enter_age"])
        return   # 👈 МАНА ШУ ЕР МУҲИМ

    context.user_data["age"] = age
    
    await update.message.reply_text(texts["enter_experience"])
    
    context.user_data["step"] = "experience"

async def get_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    if context.user_data.get("flow") != "register":
        return
    
    if context.user_data.get("step") != "experience":
        return

    experience = update.message.text.strip()
    
    if not experience or not experience.isdigit() or len(experience) > 2:
        if language == "uz_kr":
            await update.message.reply_text("Илтимос, тажриба киритинг):", reply_markup=ReplyKeyboardRemove())
        elif language == "uz_lt":
            await update.message.reply_text("Iltimos, tajribangizni kiriting):", reply_markup=ReplyKeyboardRemove())
        else:  # ru
            await update.message.reply_text("Пожалуйста, введите ваш опыт):", reply_markup=ReplyKeyboardRemove())
        return
   
    context.user_data["experience"] = experience

    # 🔥 Янги қадам
    context.user_data["step"] = "description"

    await update.message.reply_text(
        "📝 Қандай ишлар қиласиз?\n\n"
        "Ихтиёрий (300 белгидан оширманг).\n"
        "Ўтказиб юбориш учун '-' юборинг.",
        reply_markup=ReplyKeyboardRemove()
    )

    return     
 
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

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
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
    context.user_data.clear()
    context.user_data["language"] = language
    context.user_data["flow"] = "find"
    context.user_data["step"] = "service"
    context.user_data["page"] = 0
    
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    await update.message.reply_text(texts["choose_service"], reply_markup=build_service_menu(language))


async def find_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    services_list = SERVICES.get(language, SERVICES["uz_kr"])
    
    if update.message.text not in services_list:
        return

    context.user_data["service"] = update.message.text
    context.user_data["step"] = "region"

    await update.message.reply_text(texts["choose_region"], reply_markup=build_region_menu(language))

async def show_masters(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.callback_query:
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        message = update.message

    service = context.user_data.get("service")
    region = context.user_data.get("region")
    district = context.user_data.get("district")

    page = context.user_data.get("page", 0)
    limit = 5
    offset = page * limit

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    line = "══════════════════════════"

    # ⭐ VIP + NORMAL битта JOIN билан
    c.execute("""
    SELECT 
        m.id,
        m.name,
        m.phone,
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
    WHERE m.service=%s 
      AND m.region=%s 
      AND m.district=%s
    GROUP BY 
        m.id,
        m.name,
        m.phone,
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
    """, (service, region, district, limit, offset))
    
    rows = c.fetchall()

    if not rows:
        conn.close()
        await message.reply_text("Усталар топилмади.")
        return

    for mid, name, phone, dist, age, experience, vip, code, desc, is_busy, busy_until, avg_rating, votes in rows:
        
        rating_text = (
            f"{round(avg_rating,1)} ({votes})"
            if votes > 0 else "Рейтинг йўқ"
        )
        
        print("DEBUG:", is_busy, busy_until)
        
        badge = f"👑 VIP УСТА • 🆔 {code}" if vip else f"👷 УСТА • 🆔 {code}"
        from datetime import date

        today = date.today()

        if is_busy and busy_until and busy_until >= today:
            status_text = f"🔴 Банд ({busy_until})"
        else:
            status_text = "🟢 Бўш"
        card = f"""
{line}
<b>{badge}</b>
<b>{status_text}</b>
👤 <b>{name}</b>
📍 {dist}
🎂 {age} ёш
🧰 {experience} йил тажриба
📞 <b>+{phone}</b>
⭐ {rating_text}
"""
        # 🔥 Description алоҳида қўшилади
        if desc:
            short_desc = desc[:150]
            if len(desc) > 150:
                short_desc += "..."
            card += f"\n📝 {short_desc}\n"

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

    # ================= ORDER =================
    elif data.startswith("order_"):
        mid = int(data.replace("order_", ""))
        user = query.from_user
        user_id = user.id
        user_name = user.first_name

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        c = conn.cursor()

        # buyurtma yozamiz
        c.execute("INSERT INTO orders (user_id, master_id) VALUES (%s, %s)", (user_id, mid))

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

            await context.bot.send_message(
                chat_id=master_tg_id,
                text=(
                    f"📢 Янги буюртма!\n\n"
                    f"👤 Исм: {user_name}\n"
                    f"📞 Телефон: {user_phone}\n"
                    f"🆔 ID: {user_id}"
                )
            )

    # ================= RATE =================
    elif data.startswith("rate_"):
        await start_rating(update, context)

    # ================= SET RATE =================
    elif data.startswith("setrate_"):
        parts = data.split("_")
        mid = int(parts[1])
        rating = int(parts[2])
        user_id = query.from_user.id

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        c = conn.cursor()

        c.execute("""
            INSERT INTO ratings (master_id, user_id, rating)
            VALUES (%s, %s, %s)
            ON CONFLICT (master_id, user_id)
            DO UPDATE SET rating = EXCLUDED.rating
        """, (mid, user_id, rating))

        conn.commit()
        conn.close()

        await query.message.reply_text(f"✅ Баҳо сақланди: {rating} ⭐")

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

    # ================= ADMIN VIP =================
    elif data == "admin_vip":
        context.user_data["state"] = "waiting_vip_id"
        await query.message.reply_text("⭐ VIP бериш учун устанинг telegram_id ни киритинг:")
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    state = context.user_data.get("state")

    if state == "waiting_vip_id":

        telegram_id = update.message.text.strip()

        if not telegram_id.isdigit():
            await update.message.reply_text("❌ Фақат рақам киритинг!")
            return

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        c = conn.cursor()

        c.execute("UPDATE masters SET vip = TRUE WHERE telegram_id = %s", (telegram_id,))
        conn.commit()
        conn.close()

        await update.message.reply_text("✅ Уста VIP қилинди!")

        context.user_data["state"] = None

# ================= STATISTIKA =================
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.effective_message   # ⭐ МАНА ШУ ЕТАРЛИ

    import psycopg2, os

    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users WHERE last_active::timestamp >= NOW() - INTERVAL '24 HOURS'")
    today_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM masters")
    total_masters = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM ratings")
    total_ratings = c.fetchone()[0]

    conn.close()

    if language == "uz_kr":
        text = (
            f"📊 БОТ СТАТИСТИКАСИ:\n\n"
            f"👥 Жами фойдаланувчилар: {total_users}\n"
            f"📅 Бугунги фаоллар: {today_users}\n"
            f"👷 Жами усталар: {total_masters}\n"
            f"⭐ Жами бахолар: {total_ratings}\n"
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

    await message.reply_text(text, reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))

# ================= PROFILE =================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message   # ⭐ МУҲИМ ҚАТОР

    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    user = update.effective_user.id

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()
    c.execute("""
        SELECT name, phone, service, region, district, age, experience, education, skills, code
        FROM masters
        WHERE telegram_id=%s
    """, (user,))
    row = c.fetchone()
    conn.close()

    if not row:
        await message.reply_text(
            texts["not_master"],
            reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True)
        )
        return

    name, phone, service, region, district, age, experience, education, skills, code = row

    profile_text = (
        f"👷 {name}\n"
        f"🆔 Код: {code}\n"
        f"📞 {phone}\n"
        f"🛠 {service}\n"
        f"📍 {region} / {district}"
    )

    if age:
        profile_text += f"\n🎂 Ёш: {age}"
    if experience:
        profile_text += f"\n💼 Тажриба: {experience}"
    if education:
        profile_text += f"\n🎓 Маълумот: {education}"
    if skills:
        profile_text += f"\n🔧 Кўникмалар: {skills}"

    keyboard = [
        [InlineKeyboardButton("⚙ Профилни таҳрир қилиш", callback_data="edit_profile")],
        [InlineKeyboardButton("❌ Рўйхатдан чиқиш", callback_data="delete_profile")]
    ]

    await message.reply_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= DELETE =================
async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    user = update.effective_user.id
    print(f"Unregister called by user: {user}, language: {language}")

    # delete_master funksiyasidan foydalanamiz
    success = delete_master(user)
    print(f"Delete master result: {success}")
    
    if success:
        await update.message.reply_text(texts["unregistered_success"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
    else:
        await update.message.reply_text(texts["not_registered"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))

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
    
    try:
        import json
        from datetime import datetime
        
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        c = conn.cursor()
        
        # Barcha ustalarni olish
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
                'id': row[0],
                'telegram_id': row[1],
                'name': row[2],
                'phone': row[3],
                'service': row[4],
                'region': row[5],
                'district': row[6],
                'rating_count': row[7],
                'avg_rating': float(row[8])
            }
            masters.append(master)
        
        # Reytinglarni olish
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
        
        # Tilga mos xabar
        if language == "uz_kr":
            message = f"✅ Backup муваффаққиятли яратildi!\n📁 Файл: {filename}\n👤 Усталар: {len(masters)} та\n⭐ Рейтиглар: {sum(len(r) for r in ratings_data.values())} та"
        elif language == "uz_lt":
            message = f"✅ Backup muvaffaqiyatli yaratildi!\n📁 Fayl: {filename}\n👤 Ustalar: {len(masters)} ta\n⭐ Reytinglar: {sum(len(r) for r in ratings_data.values())} ta"
        else:  # ru
            message = f"✅ Backup успешно создан!\n📁 Файл: {filename}\n👤 Мастеров: {len(masters)}\n⭐ Оценок: {sum(len(r) for r in ratings_data.values())}"
        
        await update.message.reply_text(message, reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
        
    except Exception as e:
        await update.message.reply_text(
            texts["backup_error"] + f" {str(e)}",
            reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True)
        )

# ================= DB HELPERS =================

def can_rate(user_id, master_id):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    c.execute("""
        SELECT 1 FROM orders
        WHERE user_id=%s AND master_id=%s AND status='completed'
    """, (user_id, master_id))

    result = c.fetchone()
    conn.close()

    return result is not None
    
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

def main():
    print("NEW VERSION 777")
    print("Bot is starting...")
    init_db()
    ensure_code_column()
    
    app = ApplicationBuilder().token(TOKEN).build()

    # start
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("vip", give_vip))
    
    # ⭐ БИТТА callback handler — ҳаммасини ушлайди
    app.add_handler(CallbackQueryHandler(callback_router))
    
    # til tanlash
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(Узбек \\(кирилл\\)|O'zbek \\(lotin\\)|Русский)$"),
        choose_language
    ))

    # register
    app.add_handler(MessageHandler(filters.Regex("^(Уста бўлиш|Usta bo'lish|Стать мастером)$"),
        start_register
    ))
    app.add_handler(MessageHandler(filters.CONTACT, get_phone))

    # find
    app.add_handler(MessageHandler(filters.Regex("^(Уста топиш|Usta topish|Найти мастера)$"),
        start_find
    ))

    # profile
    app.add_handler(MessageHandler(filters.Regex("^(Менинг профилим|Mening profilim|Мой профиль)$"),
        my_profile
    ))
    app.add_handler(MessageHandler(filters.Regex("^(Рўйхатдан чиқиш|Ro'yxatdan chiqish|Выйти)$"),
        unregister
    ))

    # backup
    app.add_handler(MessageHandler(filters.Regex("^💾 Backup$"), backup_database))

    # til o'zgartirish
    app.add_handler(MessageHandler(filters.Regex("^🌐 Тилни ўзгартиш$"), change_language))
    app.add_handler(MessageHandler(filters.Regex("^🌐 Tilni o'zgartirish$"), change_language))
    app.add_handler(MessageHandler(filters.Regex("^🌐 Изменить язык$"), change_language))

    # stats
    app.add_handler(MessageHandler(filters.Regex("^(Статистика|Statistika|Статистика)$"), show_stats))

    # ⭐ оддий текстлар
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()


































































