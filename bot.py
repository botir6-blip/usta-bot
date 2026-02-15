import psycopg2
import os
import sqlite3
from services import SERVICES
from regions import REGIONS
from languages import LANGUAGES, get_texts, LANGUAGE_NAMES
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters,
)
ADMIN_ID = 1970756498

TOKEN = os.getenv("TOKEN")
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
    
    # ====== BAHOLAR ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS ratings(
        master_id INTEGER,
        user_id INTEGER,
        rating INTEGER,
        UNIQUE(master_id, user_id)
    )
    """)

    # ====== FOYDALANUVCHILAR ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        telegram_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TEXT,
        last_active TEXT,
        message_count INTEGER DEFAULT 0
    )
    """)
   
    c.execute("ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT")
    c.execute("ALTER TABLE masters ALTER COLUMN telegram_id TYPE BIGINT")

    conn.commit()
    conn.close()
    
# ================= USTA QO‘SHISH =================
def add_master(telegram_id, name, phone, service, region, district, age=None, experience=None):
    from datetime import datetime
    import psycopg2, os

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    c.execute("""
    INSERT INTO masters (telegram_id, name, phone, service, region, district, age, experience)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (telegram_id)
    DO UPDATE SET
        name = EXCLUDED.name,
        phone = EXCLUDED.phone,
        service = EXCLUDED.service,
        region = EXCLUDED.region,
        district = EXCLUDED.district,
        age = EXCLUDED.age,
        experience = EXCLUDED.experience
    """, (
        telegram_id, name, phone, service, region, district, age, experience
    ))

    conn.commit()
    conn.close()

# ================= USTANI TOPISH =================
def find_masters(service, region, district):
    import psycopg2, os

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    c.execute("""
    SELECT id, name, phone, region, district, service, age, experience
    FROM masters
    WHERE service ILIKE %s AND region ILIKE %s AND district ILIKE %s
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
    keyboard = [[service] for service in services]
    
    # Tilga mos "Орқага" tugmasi
    back_text = "Орқага" if language == "uz_kr" else "Orqaga" if language == "uz_lt" else "Назад"
    keyboard.append([back_text])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_region_menu(language="uz_kr"):
    regions = REGIONS.get(language, REGIONS["uz_kr"])
    keyboard = [[region] for region in regions.keys()]
    
    # Tilga mos "Орқага" tugmasi
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
    keyboard = [[city] for city in cities]
    
    # Tilga mos "Орқага" tugmasi
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

    context.user_data["phone"] = contact.phone_number
    context.user_data["name"] = clean_text(f"{contact.first_name or ''} {contact.last_name or ''}".strip())
    context.user_data["step"] = "service"

    await update.message.reply_text(texts["choose_service"], reply_markup=build_service_menu(language))

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
    text = update.message.text
    log_user(update.effective_user)
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    # ADMIN
    admin_buttons = ["Админга ёзиш", "Написать админу", "Adminga yozish", "📩 Админга ёзиш", "✍️ Админга ёзиш"]

    if "админ" in text.lower() or "yoz" in text.lower():
        await write_admin(update, context)
        return

    
    # Статистика
    if text == texts["statistics"]:
        await show_stats(update, context)
        return

    # Уста топиш
    if text == texts["find_master"]:
        context.user_data["flow"] = "find"
        context.user_data["step"] = "service"
        await update.message.reply_text(texts["choose_service"], reply_markup=build_service_menu(language))
        return
    
    # Орқага тугмаси - barcha tillardagi variantlar
    back_variants = ["Орқага", "Orqaga", "Назад"]
    if text in back_variants:
        # Тилни сақлаб қолиб, қолганини ўчириш
        language = context.user_data.get("language", "uz_kr")
        context.user_data.clear()
        context.user_data["language"] = language
        await update.message.reply_text(texts["welcome"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
        return

    step = context.user_data.get("step")

    if step == "age":
        await get_age(update, context)
        return

    if step == "experience":
        await get_experience(update, context)
        return
    
    if step == "service":
        # Agar bu "find" jarayoni bo'lsa, tilga mos xizmatlar menyusi
        if context.user_data.get("flow") == "find":
            await find_service(update, context)
        else:
            # Agar bu "register" jarayoni bo'lsa, tilga mos xizmatlar menyusi
            language = context.user_data.get("language", "uz_kr")
            texts = get_texts(language)
            services_list = SERVICES.get(language, SERVICES["uz_kr"])
            
            if update.message.text in services_list:
                context.user_data["service"] = update.message.text
                context.user_data["step"] = "region"
                await update.message.reply_text(texts["choose_region"], reply_markup=build_region_menu(language))

    elif step == "region":
        if context.user_data.get("flow") == "find":
            await ask_region(update, context)
        else:
            await ask_region(update, context)

    elif step == "district":
        await get_district(update, context)

async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    regions_data = REGIONS.get(language, REGIONS["uz_kr"])
    
    region = context.user_data.get("region", "")
    districts_list = regions_data.get(region, [])
    
    district = update.message.text
    
    # Faqat shu viloyatdagi tumanlarni qabul qilish
    if district not in districts_list:
        return
        
    context.user_data["district"] = district
    
    # mapping qilamiz
    uzkr_region = map_region_to_uzkr(context.user_data["region"])
    uzkr_district = map_district_to_uzkr(context.user_data["region"], district)
    uzkr_service = map_service_to_uzkr(context.user_data["service"])
    
    context.user_data["region"] = uzkr_region
    context.user_data["district"] = uzkr_district
    context.user_data["service"] = uzkr_service
    
    # ====== АГАР МИЖОЗ БЎЛСА ======
    if context.user_data.get("flow") == "find":
        await show_masters(update, context)
        return

    # ====== АГАР УСТА БЎЛСА ======
    if context.user_data.get("flow") == "register":
        # Ёшни сўраш
        await update.message.reply_text("Ёшингизни киритинг:", reply_markup=ReplyKeyboardRemove())
        context.user_data["step"] = "age"

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
    
    # Барча маълумотларни олиб устани қўшамиз
    telegram_id = update.effective_user.id
    add_master(telegram_id,
        context.user_data.get("name"),
        context.user_data.get("phone"),
        context.user_data.get("service"),
        context.user_data.get("region"),
        context.user_data.get("district"),
        context.user_data.get("age"),
        context.user_data.get("experience")
    )
    
    if language == "uz_kr":
        await update.message.reply_text("✅ Муваффақият! Сиз уста сифатида рўйхатдан ўтдингиз.", reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
    elif language == "uz_lt":
        await update.message.reply_text("✅ Muvaffaqiyat! Siz usta sifatida ro'yxatdan o'tdingiz.", reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
    else:  # ru
        await update.message.reply_text("✅ Успешно! Вы зарегистрировались как мастер.", reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
    
    # Тилни сақлаб қолиб, қолганини ўчириш
    language = context.user_data.get("language", "uz_kr")
    context.user_data.clear()
    context.user_data["language"] = language


# ================= FIND FLOW =================
async def start_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Tilni saqlab qolish
    language = context.user_data.get("language", "uz_kr")
    context.user_data.clear()
    context.user_data["language"] = language
    context.user_data["flow"] = "find"
    context.user_data["step"] = "service"
    
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
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    service = context.user_data.get("service")
    region = context.user_data.get("region")
    district = context.user_data.get("district")

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    c.execute("""
    SELECT m.id, m.name, m.phone, m.district, m.age, m.experience
    FROM masters m
    WHERE m.service=%s AND m.region=%s AND m.district=%s
    GROUP BY m.id
    """, (service, region, district))

    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(texts["no_masters"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
        return

    text = texts["masters_found"] + "\n\n"

    for i, (mid, name, phone, dist, age, experience) in enumerate(rows, 1):
        text += (
            f"════════════════════\n"
            f"👷 Уста №{i}\n"
            f"👤 Исм: {name}\n"
            f"📍 Ҳудуд: {dist}\n"
            f"🎂 Ёши: {age}\n"
            f"🧰 Тажриба: {experience} йил\n"
            f"📞 Телефон: +{phone}\n"
    )

    kb = [[texts["back"]]]

    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))


# ================= STATISTIKA =================
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if text == texts["statistics"]:
        await show_stats(update, context)
        return
    
    import psycopg2, os

    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    # Жами фойдаланувчилар
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    # Бугунги фаол
    c.execute("""SELECT COUNT(*) FROM users WHERE last_active::timestamp >= NOW() - INTERVAL '24 HOURS'""")
    today_users = c.fetchone()[0]

    # Жами усталар
    c.execute("SELECT COUNT(*) FROM masters")
    total_masters = c.fetchone()[0]

    # Жами баҳолар
    c.execute("SELECT COUNT(*) FROM ratings")
    total_ratings = c.fetchone()[0]

    conn.close()
    
    # Tilga mos matnlar
    if language == "uz_kr":
        text = f"📊 БОТ СТАТИСТИКАСИ:\n\n"
        text += f"👥 Жами фойдаланувчилар: {total_users}\n"
        text += f"📅 Бугунги фаоллар: {today_users}\n"
        text += f"👷 Жами усталар: {total_masters}\n"
        text += f"⭐ Жами бахолар: {total_ratings}\n"
    elif language == "uz_lt":
        text = f"📊 BOT STATISTIKASI:\n\n"
        text += f"👥 Jami foydalanuvchilar: {total_users}\n"
        text += f"📅 Bugungi faollar: {today_users}\n"
        text += f"👷 Jami ustalar: {total_masters}\n"
        text += f"⭐ Jami baholar: {total_ratings}\n"
    else:  # ru
        text = f"📊 СТАТИСТИКА БОТА:\n\n"
        text += f"👥 Всего пользователей: {total_users}\n"
        text += f"📅 Активные сегодня: {today_users}\n"
        text += f"👷 Всего мастеров: {total_masters}\n"
        text += f"⭐ Всего оценок: {total_ratings}\n"
    
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))

# ================= PROFILE =================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    print(f"my_profile called - language: {language}, user: {update.effective_user.id}")
    
    user = update.effective_user.id

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()
    c.execute("SELECT name, phone, service, region, district, age, experience, education, skills FROM masters WHERE telegram_id=%s", (user,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(texts["not_master"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
        return

    name, phone, service, region, district, age, experience, education, skills = row

    profile_text = f"👷 {name}\n📞 {phone}\n🛠 {service}\n📍 {region} / {district}"
    
    # Янги майдонларни қўшиш
    if age:
        profile_text += f"\n🎂 Ёш: {age}"
    if experience:
        profile_text += f"\n💼 Тажриба: {experience}"
    if education:
        profile_text += f"\n🎓 Маълумот: {education}"
    if skills:
        profile_text += f"\n🔧 Кўникмалар: {skills}"

    await update.message.reply_text(
        profile_text,
        reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True)
    )


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


# def populate_sample_data():
    """Bazaga 50 ta namuna usta ma'lumotlarini qo'shish"""
    sample_masters = [
        (123456789, "Ахмедов Карим", "+998901234567", "Электрик", "Тошкент", "Мирабад"),
        (123456790, "Умаров Бахтиёр", "+998912345678", "Сантехник", "Тошкент", "Чилонзор"),
        (123456834, "Юлдашев Азиз", "+998926789012", "Асосчи", "Бухоро", "Бухоро шаҳар"),
    ]
    
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()
    
    for master in sample_masters:
        c.execute("""
    INSERT INTO masters (telegram_id, name, phone, service, region, district)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (telegram_id)
    DO UPDATE SET
        name = EXCLUDED.name,
        phone = EXCLUDED.phone,
        service = EXCLUDED.service,
        region = EXCLUDED.region,
        district = EXCLUDED.district
    """, master)

    conn.commit()
    conn.close()
    print("50 ta namuna usta ma'lumotlari bazaga qo'shildi")

def main():
    print("NEW VERSION 777")
    print("Bot is starting...")
    init_db()
    # populate_sample_data()  # Namuna ma'lumotlarni qo'shish
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # til tanlash
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(Узбек \\(кирилл\\)|O'zbek \\(lotin\\)|Русский)$"), choose_language))

    # register - barcha tillar uchun
    app.add_handler(MessageHandler(filters.Regex("^(Уста бўлиш|Usta bo'lish|Стать мастером)$"), start_register))
    app.add_handler(MessageHandler(filters.CONTACT, get_phone))
    
    # find - barcha tillar uchun
    app.add_handler(MessageHandler(filters.Regex("^(Уста топиш|Usta topish|Найти мастера)$"), start_find))
    
    # profile - barcha tillar uchun
    app.add_handler(MessageHandler(filters.Regex("^(Менинг профилим|Mening profilim|Мой профиль)$"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^(Рўйхатдан чиқиш|Ro'yxatdan chiqish|Выйти)$"), unregister))
    app.add_handler(MessageHandler(filters.Regex("^💾 Backup$"), backup_database))
    
    # til o'zgartirish
    app.add_handler(MessageHandler(filters.Regex("^🌐 Тилни ўзгартиш$"), change_language))
    app.add_handler(MessageHandler(filters.Regex("^🌐 Tilni o'zgartirish$"), change_language))
    app.add_handler(MessageHandler(filters.Regex("^🌐 Изменить язык$"), change_language))

    # stats - barcha tillar uchun
    app.add_handler(MessageHandler(filters.Regex("^(Статистика|Statistika|Статистика)$"), show_stats))

    # ⭐ ЭНГ МУҲИМИ
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))


    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()













