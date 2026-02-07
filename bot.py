import os
import sqlite3
from services import SERVICES
from regions import REGIONS
from database import get_masters_by_district
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

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
    SELECT id, name, phone,
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
    ["🔍 Уста топиш"],
    ["👷 Уста бўлиш"],
    ["👤 Менинг профилим"],
    ["❌ Рўйхатдан чиқиш"]
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

    keyboard.append(["⬅️ Орқага"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def build_region_menu():
    keyboard = [[region] for region in REGIONS.keys()]
    keyboard.append(["⬅️ Орқага"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def build_city_menu(region):
    cities = REGIONS.get(region, [])
    keyboard = [[city] for city in cities]
    keyboard.append(["⬅️ Орқага"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


RATING_MENU = ReplyKeyboardMarkup([
    ["⭐ 1", "⭐ 2", "⭐ 3"],
    ["⭐ 4", "⭐ 5"],
    ["⬅️ Орқага"]
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
 
async def show_masters(update: Update, context: ContextTypes.DEFAULT_TYPE):

    service = context.user_data.get("service")
    region = context.user_data.get("region")
    district = context.user_data.get("district")

    district = context.user_data.get("district")
    rows = get_masters_by_district(district)

    if not rows:
        await update.message.reply_text(
            "😕 Ҳозирча уста топилмади.",
            reply_markup=MAIN_MENU
        )
        return

    text = "🔎 Топилган усталар:\n\n"

    for master in rows:
        name = master[2]
        phone = master[3]
        description = master[7]

        text += (
            f"👤 {name}\n"
            f"📞 {phone}\n"
            f"📝 {description}\n\n"
        )

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

    kb = [[f"⭐ Баҳо бериш {i}"] for i in range(1, len(rows)+1)]
    kb.append(["⬅️ Орқага"])

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


def main():
    print("🔥 NEW VERSION 🔥")
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # register
    app.add_handler(MessageHandler(filters.Regex("^👷 Уста бўлиш$"), start_register))
    app.add_handler(MessageHandler(filters.CONTACT, get_phone))

    # find
    app.add_handler(MessageHandler(filters.Regex("^🔍 Уста топиш$"), start_find))

    # rating
    app.add_handler(MessageHandler(filters.Regex("^⭐ Баҳо бериш"), choose_rating))
    app.add_handler(MessageHandler(filters.Regex("^⭐ [1-5]$"), save_rating))

    # profile
    app.add_handler(MessageHandler(filters.Regex("^👤 Менинг профилим$"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^❌ Рўйхатдан чиқиш$"), unregister))

    # ⭐ ЭНГ МУҲИМИ
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot ishladi 🚀")
    app.run_polling()

if __name__ == "__main__": main()




















