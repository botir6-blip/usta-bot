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

    # ====== BAHOLAR ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS ratings (
        id SERIAL PRIMARY KEY,
        master_id INTEGER,
        user_id BIGINT,
        rating INTEGER
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

    c.execute("ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT")
    c.execute("ALTER TABLE masters ALTER COLUMN telegram_id TYPE BIGINT")
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT")
    
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
        [InlineKeyboardButton("⭐ VIP бериш", callback_data="admin_vip")],
        [InlineKeyboardButton("📊 VIP рўйхати", callback_data="admin_vip_list")]
    ]

    await update.message.reply_text("🛠 VIP бошқарув панели", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_vip_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    context.user_data["step"] = "vip_input"

    await query.message.reply_text("VIP бериш учун устанинг telegram_id ни киритинг:")

async def give_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    try:
        master_tid = int(update.message.text)
    except:
        await update.message.reply_text("Тўғри telegram_id киритинг.")
        return

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    c.execute("""
        UPDATE masters
        SET vip = TRUE,
            vip_until = NOW() + INTERVAL '30 days'
        WHERE telegram_id = %s
    """, (master_tid,))

    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Уста 30 кунга VIP қилинди.")

    context.user_data.pop("step", None)


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

    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    # ⭐ RATING
    if context.user_data.get("step") == "rating":
        await save_rating(update, context)
        return
    
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
    from datetime import datetime

    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    service = context.user_data.get("service")
    region = context.user_data.get("region")
    district = context.user_data.get("district")

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    c = conn.cursor()

    c.execute("""
    SELECT m.id, m.name, m.phone, m.district, 
           m.age, m.experience,
           m.vip, m.vip_until
    FROM masters m
    WHERE m.service=%s 
      AND m.region=%s 
      AND m.district=%s
    ORDER BY 
        m.vip DESC,
        m.vip_until DESC NULLS LAST
    """, (service, region, district))

    rows = c.fetchall()

    if not rows:
        conn.close()
        await update.message.reply_text(
            texts["no_masters"],
            reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True)
        )
        return

    # 🔥 ҳар бир устани алоҳида чиқарамиз
    for i, (mid, name, phone, dist, age, experience, vip, vip_until) in enumerate(rows, 1):

        # 💎 VIP текшириш
        is_vip_active = vip and vip_until and vip_until > datetime.now()
        vip_text = "💎 VIP Уста\n" if is_vip_active else ""

        # ⭐ Рейтингни оламиз
        c.execute(
            "SELECT AVG(rating), COUNT(*) FROM ratings WHERE master_id=%s",
            (mid,)
        )
        result = c.fetchone()

        avg_rating = result[0]
        votes = result[1]

        if avg_rating:
            rating_text = f"⭐ Рейтинг: {round(avg_rating, 1)} ({votes} та овоз)"
        else:
            rating_text = "⭐ Рейтинг: ҳали йўқ"

        text = (
            f"════════════════════\n"
            f"{vip_text}"
            f"👷 Уста №{i}\n"
            f"👤 Исм: {name}\n"
            f"📍 Ҳудуд: {dist}\n"
            f"🎂 Ёши: {age}\n"
            f"🧰 Тажриба: {experience} йил\n"
            f"📞 Телефон: +{phone}\n"
            f"{rating_text}\n"
        )

        keyboard = [
            [InlineKeyboardButton("📞 Қўнғироқ қилиш", callback_data=f"call_{phone}")],
            [InlineKeyboardButton("✅ Чақирдим", callback_data=f"order_{mid}")],
            [InlineKeyboardButton("⭐ Баҳо бериш", callback_data=f"rate_{mid}")]
        ]

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    conn.close()

    kb = [[texts["back"]]]
    await update.message.reply_text(
        "⬅",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )


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
        c.execute(
            "INSERT INTO orders (user_id, master_id) VALUES (%s, %s)",
            (user_id, mid)
        )

        # ustaning telegram id sini olamiz
        c.execute("SELECT telegram_id, name FROM masters WHERE id=%s", (mid,))
        master = c.fetchone()

        # klient telefonini olamiz
        c.execute("SELECT phone FROM users WHERE telegram_id=%s", (user_id,))
        user_phone = c.fetchone()

        conn.commit()
        conn.close()

        await query.message.reply_text(
            "✅ Буюртма қабул қилинди. Уста сиз билан боғланади."
        )

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


# ================= STATISTIKA =================
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
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

    await query.message.reply_text(
        "Устага нечта юлдуз берасиз?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    print("NEW VERSION 777")
    print("Bot is starting...")
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    # start
    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("admin", admin_panel))

    # ⭐ БИТТА callback handler — ҳаммасини ушлайди
    app.add_handler(CallbackQueryHandler(admin_vip_menu, pattern="^admin_vip"))
    app.add_handler(CallbackQueryHandler(callback_router, pattern="^(call_|order_|rate_|setrate_)"))

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
    app.add_handler(MessageHandler(
        filters.Regex("^(Статистика|Statistika|Статистика)$"),
        show_stats
    ))

    # ⭐ оддий текстлар
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()

