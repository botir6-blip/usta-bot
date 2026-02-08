import os
import sqlite3
from services import SERVICES
from regions import REGIONS
from languages import LANGUAGES, get_texts, LANGUAGE_NAMES
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = "7573364452:AAFW1F3ax2HwSGOiULbk0xAEhBs-_vqmOhE"

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()

    # ====== USTALAR ======
    c.execute("""
    CREATE TABLE IF NOT EXISTS masters(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        name TEXT,
        phone TEXT,
        service TEXT,
        region TEXT,
        district TEXT,
        description TEXT
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

    conn.commit()
    conn.close()


# ================= USTA QO‘SHISH =================
def add_master(telegram_id, name, phone, service, region, district, description):
    # Barcha maydonlarni tozalash
    name = clean_text(name) if name else ""
    phone = clean_text(phone) if phone else ""
    service = clean_text(service) if service else ""
    region = clean_text(region) if region else ""
    district = clean_text(district) if district else ""
    description = clean_text(description) if description else ""
    
    # Minimal tekshirish
    if not name or not phone or not service or not region or not district:
        return False
    
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()

    # Avval eski ustani ID sini topamiz
    c.execute("SELECT id FROM masters WHERE telegram_id=?", (telegram_id,))
    old_master = c.fetchone()
    
    # Yangi ustani qo'shamiz (yoki yangilaymiz)
    c.execute(""" 
    INSERT OR REPLACE INTO masters
    (telegram_id, name, phone, service, region, district, description)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (telegram_id, name, phone, service, region, district, description))
    
    # Agar eski usta bo'lsa, reytinglarni yangi ID bilan bog'lash
    if old_master:
        old_master_id = old_master[0]
        new_master_id = c.lastrowid  # Yangi qo'shilgan ustani ID si
        c.execute(""" 
        UPDATE ratings 
        SET master_id = ?
        WHERE master_id = ?
        """, (new_master_id, old_master_id))
    
    conn.commit()
    conn.close()
    return True


# ================= USTANI TOPISH =================
def find_masters(service, region, district):
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()

    c.execute("""
    SELECT id, name, phone, region, district, description,
    IFNULL(AVG(rating), 0),
    COUNT(rating)
    FROM masters
    LEFT JOIN ratings ON masters.id = ratings.master_id
    WHERE service=? AND region=? AND district=?
    GROUP BY masters.id
    """, (service, region, district))

    data = c.fetchall()
    conn.close()
    return data


# ================= BAHA BERISH =================
def save_rating_db(master_id, user_id, rating):
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()

    c.execute("""
    INSERT OR REPLACE INTO ratings(master_id, user_id, rating)
    VALUES (?, ?, ?)
    """, (master_id, user_id, rating))

    conn.commit()
    conn.close()


# ================= RO‘YXATDAN CHIQARISH =================
def delete_master(telegram_id):
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()

    # Avval ustani ID sini topamiz
    c.execute("SELECT id FROM masters WHERE telegram_id=?", (telegram_id,))
    master = c.fetchone()
    
    if master:
        master_id = master[0]
        # AVVAL reytinglarni o'chiramiz
        c.execute("DELETE FROM ratings WHERE master_id=?", (master_id,))
        # KEYIN ustani o'chiramiz
        c.execute("DELETE FROM masters WHERE telegram_id=?", (telegram_id,))
        print(f"🗑️ Usta {master_id} va uning {c.rowcount} ta reytingi o'chirildi")
    
    conn.commit()
    conn.close()
    return master is not None


# ================= MENUS =================
MAIN_MENU = ReplyKeyboardMarkup([
    ["Уста топиш", "Топ-10 усталар"],
    ["Уста бўлиш", "Статистика"],
    ["Менинг профилим"],
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

def build_city_menu(region, language="uz_kr"):
    regions_data = REGIONS.get(language, REGIONS["uz_kr"])
    cities = regions_data.get(region, [])
    keyboard = [[city] for city in cities]
    
    # Tilga mos "Орқага" tugmasi
    back_text = "Орқага" if language == "uz_kr" else "Orqaga" if language == "uz_lt" else "Назад"
    keyboard.append([back_text])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


RATING_MENU = ReplyKeyboardMarkup([
    ["1", "2", "3"],
    ["4", "5"],
    ["Орқага"]
], resize_keyboard=True)

# ================= TIL TANLASH =================
def build_language_menu():
    keyboard = [[LANGUAGES[lang]] for lang in LANGUAGES.keys()]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Til tanlash"""
    text = update.message.text
    
    # Tilni topish
    language = None
    for lang_code, lang_name in LANGUAGES.items():
        if text == lang_name:
            language = lang_code
            break
    
    if language:
        context.user_data["language"] = language
        texts = get_texts(language)
        
        # Asosiy menuni yangilash
        context.user_data.clear()
        context.user_data["language"] = language
        
        await update.message.reply_text(
            texts["welcome"],
            reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            "Илтимос, тилни танланг:",
            reply_markup=build_language_menu()
        )

# ================= FOYDALANUVCHI QO'SHISH =================
def log_user(user):
    from datetime import datetime
    
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    c.execute("""
    INSERT OR REPLACE INTO users 
    (telegram_id, username, first_name, last_name, join_date, last_active, message_count)
    VALUES (?, ?, ?, ?, 
        COALESCE((SELECT join_date FROM users WHERE telegram_id=?), ?),
        ?, 
        COALESCE((SELECT message_count FROM users WHERE telegram_id=?), 0) + 1)
    """, (
        user.id, user.username, user.first_name, user.last_name,
        user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user.id
    ))
    
    conn.commit()
    conn.close()

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    log_user(update.effective_user)  # Foydalanuvchini yozish
    
    # Agar til tanlanmagan bo'lsa, til tanlash
    if not context.user_data.get("language"):
        await update.message.reply_text(
            "🌐 Tilni tanlang / Выберите язык:\nChoose language:",
            reply_markup=build_language_menu()
        )
    else:
        # Til tanlangan bo'lsa, asosiy menuni ko'rsatish
        language = context.user_data["language"]
        texts = get_texts(language)
        await update.message.reply_text(
            texts["welcome"],
            reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True)
        )


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
    context.user_data.clear()
    context.user_data["flow"] = "register"
    context.user_data["step"] = "phone"
    
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    kb = [[KeyboardButton("📞 Телефон юбориш", request_contact=True)]]
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
    context.user_data["step"] = "city"
    
    # Tilga mos "Қайси шаҳар?" matni
    if language == "uz_kr":
        question = "Қайси шаҳар?"
    elif language == "uz_lt":
        question = "Qaysi shahar?"
    else:  # ru
        question = "Какой город?"
    
    await update.message.reply_text(question, reply_markup=build_city_menu(region, language))

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    # Орқага тугмаси - barcha tillardagi variantlar
    back_variants = ["Орқага", "Orqaga", "Назад"]
    if text in back_variants:
        await update.message.reply_text(texts["welcome"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
        context.user_data.clear()
        return

    step = context.user_data.get("step")

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
            await find_region(update, context)
        else:
            await ask_region(update, context)

    elif step == "district":
        await get_district(update, context)

    elif step == "description":
        await get_description(update, context)

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

    # ====== АГАР МИЖОЗ БЎЛСА ======
    if context.user_data.get("flow") == "find":
        await show_masters(update, context)
        return

    # ====== АГАР УСТА БЎЛСА ======
    if context.user_data.get("flow") == "register":
        await update.message.reply_text(texts["write_description"], reply_markup=ReplyKeyboardRemove())
    context.user_data["step"] = "description"

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    # агар уста руйхатидан утмаяпган булса
    if context.user_data.get("flow") != "register":
        return
    
    if context.user_data.get("step") != "description":
        return

    telegram_id = update.effective_user.id
    description = clean_text(update.message.text)
    
    # Agar tozalashdan keyin hech narsa qolmagan bo'lsa
    if not description:
        await update.message.reply_text(
            texts["invalid_input"] + "\n" + texts["write_description"],
            reply_markup=ReplyKeyboardRemove()
        )
        return

    add_master(telegram_id,
        context.user_data.get("name"),
        context.user_data.get("phone"),
        context.user_data.get("service"),
        context.user_data.get("region"),
        context.user_data.get("district"),
        description
    )

    await update.message.reply_text(
        texts["success_register"],
        reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True)
    )

    context.user_data.clear()
 
async def show_masters(update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    service = context.user_data.get("service")
    region = context.user_data.get("region")
    district = context.user_data.get("district")

    rows = find_masters(service, region, district)

    if not rows:
        await update.message.reply_text(texts["no_masters"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
        return

    text = texts["masters_found"] + "\n\n"

    for master in rows:
        name = master[2]
        phone = master[3]
        region = master[4]
        district = master[5]
        description = master[6]
        avg_rating = master[7]
        rating_count = master[8]
        
        text += f"👤 {name}\n📞 {phone}\n📍 {region} / {district}\n📝 {description}\n⭐ {avg_rating:.1f} ({rating_count} бахо)\n\n"

    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))

# ================= FIND FLOW =================
async def start_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
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


async def find_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("flow") != "find":
        return

    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)

    service = context.user_data["service"]
    region = update.message.text

    conn = sqlite3.connect("usta.db")
    c = conn.cursor()

    c.execute("""
        SELECT m.id, m.name, m.phone, m.district, m.description,
        IFNULL(AVG(r.rating),0), COUNT(r.rating)
        FROM masters m
        LEFT JOIN ratings r ON r.master_id = m.id
        WHERE m.service=? AND m.region=?
        GROUP BY m.id
    """, (service, region))

    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(texts["no_masters"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
        return

    text = texts["masters_found"] + "\n\n"
    context.user_data["rate"] = {}

    for i, (mid, name, phone, dist, desc, avg, cnt) in enumerate(rows, 1):
        stars = "⭐" * round(avg) if avg else "⭐ йўқ"

        text += (
            f"{i}. 👷 {name}\n"
            f"📞 {phone}\n"
            f"📍 {dist}\n"
            f"ℹ️ {desc}\n"
            f"{stars} ({cnt})\n\n"
        )

        context.user_data["rate"][str(i)] = mid

    kb = [[f"Баҳо бериш {i}"] for i in range(1, len(rows)+1)]
    kb.append([texts["back"]])

    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))


# ================= RATING =================
async def choose_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    num = update.message.text.split()[-1]
    context.user_data["rating_master"] = context.user_data["rate"].get(num)

    await update.message.reply_text("Балл:", reply_markup=RATING_MENU)


async def save_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    rating = int(update.message.text.replace("⭐", "").strip())
    master = context.user_data.get("rating_master")
    user = update.effective_user.id

    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ratings VALUES(?,?,?)", (master, user, rating))
    conn.commit()
    conn.close()

    await update.message.reply_text(texts["rating_saved"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))


# ================= STATISTIKA =================
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    # Jami foydalanuvchilar
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    # Bugungi faol foydalanuvchilar
    c.execute("SELECT COUNT(*) FROM users WHERE DATE(last_active) = DATE('now')")
    today_users = c.fetchone()[0]
    
    # Jami ustalar
    c.execute("SELECT COUNT(*) FROM masters")
    total_masters = c.fetchone()[0]
    
    # Jami baholar
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
# ================= TOP 10 USTALAR =================
async def show_top_masters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()

    c.execute("""
        SELECT m.name, m.phone, m.service, m.region, m.district, m.description,
        IFNULL(AVG(r.rating), 0) as avg_rating,
        COUNT(r.rating) as rating_count
        FROM masters m
        LEFT JOIN ratings r ON m.id = r.master_id
        GROUP BY m.id
        HAVING rating_count > 0
        ORDER BY avg_rating DESC, rating_count DESC
        LIMIT 10
    """)

    rows = c.fetchall()
    conn.close()

    if not rows:
        no_masters_text = "😕 Ҳозирча бахо берилган усталар йўқ." if language == "uz_kr" else "😕 Hozircha baho berilgan ustalar yo'q." if language == "uz_lt" else "😕 Пока нет оцененных мастеров."
        await update.message.reply_text(no_masters_text, reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
        return

    # Viloyatlar bo'yicha guruhlash
    regions = {}
    for name, phone, service, region, district, description, avg_rating, rating_count in rows:
        if region not in regions:
            regions[region] = []
        regions[region].append({
            'name': name, 'phone': phone, 'service': service,
            'district': district, 'description': description,
            'avg_rating': avg_rating, 'rating_count': rating_count
        })

    # Tilga mos sarlavha
    if language == "uz_kr":
        text = "🏆 ТОП-10 УСТАЛАР (Вилоятлар бўйича):\n\n"
        location_label = "📍"
        service_label = "🛠"
        district_label = "🏘️"
        info_label = "ℹ️"
        rating_label = "⭐"
        rating_word = "баҳо"
    elif language == "uz_lt":
        text = "🏆 TOP-10 USTALAR (Viloyatlar bo'yicha):\n\n"
        location_label = "📍"
        service_label = "🛠"
        district_label = "🏘️"
        info_label = "ℹ️"
        rating_label = "⭐"
        rating_word = "baho"
    else:  # ru
        text = "🏆 ТОП-10 МАСТЕРОВ (по областям):\n\n"
        location_label = "📍"
        service_label = "🛠"
        district_label = "🏘️"
        info_label = "ℹ️"
        rating_label = "⭐"
        rating_word = "оценок"

    for region, masters in regions.items():
        text += f"{location_label} {region}:\n"
        for i, master in enumerate(masters, 1):
            text += (
                f"  {i}. {master['name']}\n"
                f"  📞 {master['phone']}\n"
                f"  {service_label} {master['service']}\n"
                f"  {district_label} {master['district']}\n"
                f"  {info_label} {master['description']}\n"
                f"  {rating_label} {master['avg_rating']:.1f} ({master['rating_count']} {rating_word})\n\n"
            )
        text += "\n"

    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))

# ================= PROFILE =================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    user = update.effective_user.id

    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    c.execute("SELECT name, phone, service, region, district FROM masters WHERE telegram_id=?", (user,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(texts["not_master"], reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True))
        return

    name, phone, service, region, district = row

    await update.message.reply_text(
        f"👷 {name}\n📞 {phone}\n🛠 {service}\n📍 {region} / {district}",
        reply_markup=ReplyKeyboardMarkup(texts["main_menu"], resize_keyboard=True)
    )


# ================= DELETE =================
async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("language", "uz_kr")
    texts = get_texts(language)
    
    user = update.effective_user.id

    # delete_master funksiyasidan foydalanamiz
    success = delete_master(user)
    
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
    
    try:
        import json
        from datetime import datetime
        
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
        (123456789, "Ахмедов Карим", "+998901234567", "Электрик", "Тошкент", "Мирабад", "10 йил тажриба, чор-чора ва уй электр ишлари"),
        (123456790, "Умаров Бахтиёр", "+998912345678", "Сантехник", "Тошкент", "Чилонзор", "Канализация, қувур ишлари, қизитиш системалари"),
        (123456791, "Рахимова Гулчехра", "+998923456789", "Наккаш", "Самарканд", "Самарканд шаҳар", "Уй деворларини нақшлаш, реставрация ишлари"),
        (123456792, "Тошев Жамшед", "+998934567890", "Мебел устаси", "Бухоро", "Бухоро шаҳар", "Мебел тиклаш, янги мебел яратиш"),
        (123456793, "Каримова Дилфуза", "+998945678901", "Тикувчи", "Фарғона", "Фарғона шаҳар", "Кийим-кечак тикиш, тўқимачилик"),
        (123456794, "Саидов Бобур", "+998956789012", "Қурилишчи", "Андижон", "Андижон шаҳар", "Уй қурилиши, таъмирлаш"),
        (123456795, "Нематова Муҳаббат", "+998967890123", "Ошпаз", "Наманган", "Наманган шаҳар", "Тўйлар учун таомлар, кулинар хизмат"),
        (123456796, "Қодиров Элмурод", "+998978901234", "Авто устаси", "Қорақалпоғистон", "Нукус", "Автомобил таъмири, диогностика"),
        (123456797, "Тўхтаева Зарина", "+998989012345", "Сартарош", "Хоразм", "Урганч", "Эркаклар ва аёллар сартарошлиги"),
        (123456798, "Ҳамроқулов Азиз", "+998990123456", "Компютер устаси", "Тошкент", "Яшнабад", "Компютер таъмири, дастур ўрнатиш"),
        (123456799, "Солиева Мохира", "+998991234567", "Фотограф", "Самарканд", "Самарканд шаҳар", "Тўй, портрет фотографияси"),
        (123456800, "Юлдашев Фаррух", "+998992345678", "Асосчи", "Бухоро", "Бухоро шаҳар", "Фундамент, девор қурилиши"),
        (123456801, "Абдуллаева Рано", "+998993456789", "Гулчӣ", "Фарғона", "Фарғона шаҳар", "Тўй гуллари, букетлар"),
        (123456802, "Ҳасанов Бехзод", "+998994567890", "Металл ишлари", "Андижон", "Андижон шаҳар", "Темир эшik, панжара ишлари"),
        (123456803, "Мирзаева Муниса", "+998995678901", "Манакур", "Наманган", "Наманган шаҳар", "Оёқ ва қўл манакури"),
        (123456804, "Рашидов Шерзод", "+998996789012", "Шиша устаси", "Қорақалпоғистон", "Нукус", "Ойна, шиша ишлари"),
        (123456805, "Турсунова Дилором", "+998997890123", "Косметолог", "Тошкент", "Мирабад", "Юз тўлиши, эпиляция"),
        (123456806, "Олимов Сардор", "+998998901234", "Электрик", "Тошкент", "Чилонзор", "Қурилиш электр ишлари"),
        (123456807, "Қодирова Мохира", "+998999012345", "Тикувчи", "Самарканд", "Самарканд шаҳар", "Болалар кийимлари тикиш"),
        (123456808, "Умаров Жамшид", "+998900123456", "Сантехник", "Бухоро", "Бухоро шаҳар", "Сув иссиқлиги, қувур ўтказиш"),
        (123456809, "Тўраев Бахтиёр", "+998901234567", "Наккаш", "Фарғона", "Фарғона шаҳар", "Миллий нақшлар, девор безаклари"),
        (123456810, "Саидова Гулшан", "+998902345678", "Мебел устаси", "Андижон", "Андижон шаҳар", "Офис мебели, кухня мебели"),
        (123456811, "Рахимов Азиз", "+998903456789", "Қурилишчи", "Наманган", "Наманган шаҳар", "Қурилиш материаллари, таъмирлаш"),
        (123456812, "Каримова Зарина", "+998904567890", "Ошпаз", "Қорақалпоғистон", "Нукус", "Миллий таомлар, тўйлар"),
        (123456813, "Тошев Элмурод", "+998905678901", "Авто устаси", "Тошкент", "Яшнабад", "Ёқилғи система, мотор таъмири"),
        (123456814, "Нематова Дилфуза", "+998906789012", "Сартарош", "Тошкент", "Мирабад", "Эркаклар сартарошлиги, соч кесиш"),
        (123456815, "Ҳамроқулова Мохира", "+998907890123", "Компютер устаси", "Тошкент", "Чилонзор", "Ноутбук таъмири, вирус тозалаш"),
        (123456816, "Солиев Бехзод", "+998908901234", "Фотограф", "Самарканд", "Самарканд шаҳар", "Маҳсулот фотографияси, студия"),
        (123456817, "Юлдашева Рано", "+998909012345", "Асосчи", "Бухоро", "Бухоро шаҳар", "Ғисла ишлари, девор оқлаш"),
        (123456818, "Абдуллаев Шерзод", "+998910123456", "Гулчӣ", "Фарғона", "Фарғона шаҳар", "Маҳсулот гуллари, доға гуллари"),
        (123456819, "Ҳасанова Муниса", "+998911234567", "Металл ишлари", "Андижон", "Андижон шаҳар", "Металл конструкциялар, эшikлар"),
        (123456820, "Мирзаев Фаррух", "+998912345678", "Манакур", "Наманган", "Наманган шаҳар", "Француз манакури, гель лак"),
        (123456821, "Рашидова Дилором", "+998913456789", "Шиша устаси", "Қорақалпоғистон", "Нукус", "Шиша ўрнатиш, жўра ишлари"),
        (123456822, "Турсунов Сардор", "+998914567890", "Косметолог", "Тошкент", "Яшнабад", "Массаж, парфюмерия"),
        (123456823, "Олимова Гулчехра", "+998915678901", "Электрик", "Тошкент", "Мирабад", "Чиқиш ишлари, розетка ўрнатиш"),
        (123456824, "Қодиров Жамшид", "+998916789012", "Тикувчи", "Самарканд", "Самарканд шаҳар", "Кўйлак, шим тикиш"),
        (123456825, "Умарова Зарина", "+998917890123", "Сантехник", "Бухоро", "Бухоро шаҳар", "Қозон, арматура ишлари"),
        (123456826, "Тўраева Мохира", "+998918901234", "Наккаш", "Фарғона", "Фарғона шаҳар", "Қадимий нақшлар, реставрация"),
        (123456827, "Саидов Азиз", "+998919012345", "Мебел устаси", "Андижон", "Андижон шаҳар", "Ётқизув мебели, шкафлар"),
        (123456828, "Рахимова Дилфуза", "+998920123456", "Қурилишчи", "Наманган", "Наманган шаҳар", "Қоплама ишлари, таъмирлаш"),
        (123456829, "Каримов Бехзод", "+998921234567", "Ошпаз", "Қорақалпоғистон", "Нукус", "Ресторан таомлари, банкеты"),
        (123456830, "Тошева Рано", "+998922345678", "Авто устаси", "Тошкент", "Чилонзор", "Маслаф алмаштириш, тормозлар"),
        (123456831, "Нематов Шерзод", "+998923456789", "Сартарош", "Тошкент", "Мирабад", "Болалар сартарошлиги, модел бериш"),
        (123456832, "Ҳамроқулов Фаррух", "+998924567890", "Компютер устаси", "Тошкент", "Яшнабад", "Интернет ўрнатиш, тармоқ"),
        (123456833, "Солиева Дилором", "+998925678901", "Фотограф", "Самарканд", "Самарканд шаҳар", "Видео ишлари, монтаж"),
        (123456834, "Юлдашев Азиз", "+998926789012", "Асосчи", "Бухоро", "Бухоро шаҳар", "Том қоплама, гидроизоляция"),
    ]
    
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    
    for master in sample_masters:
        c.execute("""
        INSERT OR REPLACE INTO masters 
        (telegram_id, name, phone, service, region, district, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, master)
    
    conn.commit()
    conn.close()
    print("50 ta namuna usta ma'lumotlari bazaga qo'shildi")

def main():
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

    # rating - barcha tillar uchun
    app.add_handler(MessageHandler(filters.Regex("^(Баҳо бериш|Baho bering|Оценить)$"), choose_rating))
    app.add_handler(MessageHandler(filters.Regex("^[1-5]$"), save_rating))

    # top masters - barcha tillar uchun
    app.add_handler(MessageHandler(filters.Regex("^(Топ-10 усталар|Top-10 ustalar|Топ-10 мастеров)$"), show_top_masters))
    
    # stats - barcha tillar uchun
    app.add_handler(MessageHandler(filters.Regex("^(Статистика|Statistika|Статистика)$"), show_stats))
    
    # profile - barcha tillar uchun
    app.add_handler(MessageHandler(filters.Regex("^(Менинг профилим|Mening profilim|Мой профиль)$"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^(Рўйхатдан чиқиш|Ro'yxatdan chiqish|Выйти)$"), unregister))
    app.add_handler(MessageHandler(filters.Regex("^💾 Backup$"), backup_database))
    
    # til o'zgartirish
    app.add_handler(MessageHandler(filters.Regex("^🌐 Тилни ўзгартиш$"), change_language))
    app.add_handler(MessageHandler(filters.Regex("^🌐 Tilni o'zgartirish$"), change_language))
    app.add_handler(MessageHandler(filters.Regex("^🌐 Изменить язык$"), change_language))

    # ⭐ ЭНГ МУҲИМИ
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__": main()























