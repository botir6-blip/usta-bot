import os
import sqlite3
from services import SERVICES
from regions import REGIONS
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = "8561942994:AAE9L5BnSpyo5H5FVYQJQZpIP4Bt_K-YFO4"

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

    conn.commit()
    conn.close()


# ================= USTA QO‘SHISH =================
def add_master(telegram_id, name, phone, service, region, district, description):
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()

    c.execute("""
    INSERT OR REPLACE INTO masters
    (telegram_id, name, phone, service, region, district, description)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (telegram_id, name, phone, service, region, district, description))

    conn.commit()
    conn.close()


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

    c.execute("DELETE FROM masters WHERE telegram_id=?", (telegram_id,))

    conn.commit()
    conn.close()
    
# ================= MENUS =================
MAIN_MENU = ReplyKeyboardMarkup([
    ["Уста топиш", "Топ-10 усталар"],
    ["Уста бўлиш"],
    ["Менинг профилим"],
    ["Рўйхатдан чиқиш"]
], resize_keyboard=True)


def build_service_menu():
    keyboard = []
    row = []

    for i, service in enumerate(SERVICES, 1):
        row.append(service)
        if i % 2 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append(["Орқага"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def build_region_menu():
    keyboard = [[region] for region in REGIONS.keys()]
    keyboard.append(["Орқага"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def build_city_menu(region):
    cities = REGIONS.get(region, [])
    keyboard = [[city] for city in cities]
    keyboard.append(["Орқага"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


RATING_MENU = ReplyKeyboardMarkup([
    ["1", "2", "3"],
    ["4", "5"],
    ["Орқага"]
], resize_keyboard=True)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Ассалому алайкум 👋\nТанланг:",
        reply_markup=MAIN_MENU
    )


# ================= REGISTER FLOW =================
async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["flow"] = "register"
    context.user_data["step"] = "phone"

    kb = [[KeyboardButton("📞 Телефон юбориш", request_contact=True)]]
    await update.message.reply_text("Телефон рақамингизни юборинг 👇", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact

    if not contact:
        return

    context.user_data["phone"] = contact.phone_number
    context.user_data["step"] = "service"

    await update.message.reply_text("Касбни танланг 👇", reply_markup=build_service_menu())

async def ask_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    region = update.message.text

    if region not in REGIONS:
        return

    context.user_data["region"] = region
    context.user_data["step"] = "district"

    await update.message.reply_text("Туманни танланг:", reply_markup=build_city_menu(region))


async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    region = update.message.text
    context.user_data["region"] = region
    context.user_data["step"] = "city"
    
    await update.message.reply_text("Қайси шаҳар?", reply_markup=build_city_menu(region))

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    step = context.user_data.get("step")

    if step == "service":
        await find_service(update, context)

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
    district = update.message.text
    context.user_data["district"] = district

    # ====== АГАР МИЖОЗ БЎЛСА ======
    if context.user_data.get("flow") == "find":
        await show_masters(update, context)
        return

    # ====== АГАР УСТА БЎЛСА ======
    if context.user_data.get("flow") == "register":
        await update.message.reply_text("Ўзингиз ҳақингизда қисқача ёзинг:", reply_markup=ReplyKeyboardRemove())
    context.user_data["step"] = "description"

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # агар уста руйхатидан утмаяпган булса
    if context.user_data.get("flow") != "register":
        return
    
    if context.user_data.get("step") != "description":
        return

    telegram_id = update.effective_user.id
    description = update.message.text

    add_master(telegram_id,
        context.user_data.get("name"),
        context.user_data.get("phone"),
        context.user_data.get("service"),
        context.user_data.get("region"),
        context.user_data.get("district"),
        description
    )

    await update.message.reply_text(
        "✅ Сиз рўйхатдан ўтдингиз!",
        reply_markup=MAIN_MENU
    )

    context.user_data.clear()
 
async def show_masters(update, context: ContextTypes.DEFAULT_TYPE):

    service = context.user_data.get("service")
    region = context.user_data.get("region")
    district = context.user_data.get("district")

    rows = find_masters(service, region, district)

    if not rows:
        await update.message.reply_text("😕 Ҳозирча уста топилмади.", reply_markup=MAIN_MENU)
        return

    text = "🔎 Топилган усталар:\n\n"

    for master in rows:
        name = master[2]
        phone = master[3]
        region = master[4]
        district = master[5]
        description = master[6]
        avg_rating = master[7]
        rating_count = master[8]
        
        text += f"👤 {name}\n📞 {phone}\n📍 {region}, {district}\nℹ️ {description}\n⭐ {avg_rating:.1f} ({rating_count} бaho)\n\n"

    await update.message.reply_text(text, reply_markup=MAIN_MENU)

# ================= FIND FLOW =================
async def start_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["flow"] = "find"
    context.user_data["step"] = "service"

    await update.message.reply_text("Керакли касб:", reply_markup=build_service_menu()   # ()
    )


async def find_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text not in SERVICES:
        return

    context.user_data["service"] = update.message.text
    context.user_data["step"] = "region"

    await update.message.reply_text("Қайси вилоят?", reply_markup=build_region_menu())


async def find_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("flow") != "find":
        return

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
        await update.message.reply_text("😕 Уста топилмади", reply_markup=MAIN_MENU)
        return

    text = "Усталар:\n\n"
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
    kb.append(["Орқага"])

    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))


# ================= RATING =================
async def choose_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    num = update.message.text.split()[-1]
    context.user_data["rating_master"] = context.user_data["rate"].get(num)

    await update.message.reply_text("Балл:", reply_markup=RATING_MENU)


async def save_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rating = int(update.message.text.replace("⭐", "").strip())
    master = context.user_data.get("rating_master")
    user = update.effective_user.id

    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ratings VALUES(?,?,?)", (master, user, rating))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Раҳмат!", reply_markup=MAIN_MENU)


# ================= TOP 10 USTALAR =================
async def show_top_masters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()

    c.execute("""
        SELECT m.name, m.phone, m.service, m.region, m.district, m.description,
        IFNULL(AVG(r.rating), 0) as avg_rating,
        COUNT(r.rating) as rating_count
        FROM masters m
        LEFT JOIN ratings r ON r.master_id = m.id
        GROUP BY m.id
        HAVING rating_count > 0
        ORDER BY avg_rating DESC, rating_count DESC
        LIMIT 10
    """)

    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("😕 Ҳозирча бaho berilgan усталар йўқ.", reply_markup=MAIN_MENU)
        return

    text = "🏆 ТОП-10 УСТАЛАР:\n\n"

    for i, (name, phone, service, region, district, description, avg_rating, rating_count) in enumerate(rows, 1):
        text += (
            f"{i}. 👷 {name}\n"
            f"📞 {phone}\n"
            f"🛠 {service}\n"
            f"📍 {region}, {district}\n"
            f"ℹ️ {description}\n"
            f"⭐ {avg_rating:.1f} ({rating_count} бaho)\n\n"
        )

    await update.message.reply_text(text, reply_markup=MAIN_MENU)

# ================= PROFILE =================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id

    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    c.execute("SELECT name, phone, service, region, district FROM masters WHERE telegram_id=?", (user,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("Сиз уста эмассиз", reply_markup=MAIN_MENU)
        return

    name, phone, service, region, district = row

    await update.message.reply_text(
        f"👷 {name}\n📞 {phone}\n🛠 {service}\n📍 {region} / {district}",
        reply_markup=MAIN_MENU
    )


# ================= DELETE =================
async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id

    conn = sqlite3.connect("usta.db")
    c = conn.cursor()
    c.execute("DELETE FROM masters WHERE telegram_id=?", (user,))
    conn.commit()
    conn.close()

    await update.message.reply_text("❌ Ўчирилди", reply_markup=MAIN_MENU)


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

    # register
    app.add_handler(MessageHandler(filters.Regex("^Уста бўлиш$"), start_register))
    app.add_handler(MessageHandler(filters.CONTACT, get_phone))

    # find
    app.add_handler(MessageHandler(filters.Regex("^Уста топиш$"), start_find))

    # rating
    app.add_handler(MessageHandler(filters.Regex("^Баҳо бериш"), choose_rating))
    app.add_handler(MessageHandler(filters.Regex("^[1-5]$"), save_rating))

    # top masters
    app.add_handler(MessageHandler(filters.Regex("^Топ-10 усталар$"), show_top_masters))
    
    # profile
    app.add_handler(MessageHandler(filters.Regex("^Менинг профилим$"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^Рўйхатдан чиқиш$"), unregister))

    # ⭐ ЭНГ МУҲИМИ
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__": main()























