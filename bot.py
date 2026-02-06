import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
DB = "usta.db"

# =======================
# DATA
# =======================
SERVICES = [
    "🔧 Сантехник",
    "⚡ Электрик",
    "🧱 Қурилиш",
    "🧹 Уй тозалаш",
    "🪚 Мебель устаси",
    "🛠 Маиший техника",
    "❄️ Кондиционер",
    "🚗 Автоэлектрик",
    "💻 Компьютер устаси",
]

REGIONS = {
    "Тошкент": ["Тошкент ш.", "Чирчиқ", "Ангрен", "Олмалиқ", "Бекобод"],
    "Самарқанд": ["Самарқанд ш.", "Каттақўрғон", "Пастдарғом", "Нарпай"],
    "Бухоро": ["Бухоро ш.", "Ғиждувон", "Когон"],
    "Қашқадарё": ["Қарши", "Шаҳрисабз", "Косон"],
    "Фарғона": ["Фарғона", "Қўқон", "Марғилон"],
    "Андижон": ["Андижон", "Асака", "Хўжаобод"],
    "Наманган": ["Наманган", "Чортоқ"],
    "Навоий": ["Навоий", "Зарафшон"],
    "Сурхондарё": ["Термиз", "Денов"],
    "Жиззах": ["Жиззах", "Ғаллаорол"],
    "Сирдарё": ["Гулистон", "Сирдарё"],
    "Хоразм": ["Урганч", "Хива"],
    "Қорақалпоғистон": ["Нукус", "Тўрткўл"],
}

# =======================
# DATABASE
# =======================
def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS masters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            name TEXT,
            phone TEXT,
            service TEXT,
            region TEXT,
            city TEXT,
            description TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_master(tg_id, name, phone, service, region, city, desc):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO masters
        (telegram_id, name, phone, service, region, city, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (tg_id, name, phone, service, region, city, desc))
    conn.commit()
    conn.close()

def find_masters(service, region, city):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT name, phone, description
        FROM masters
        WHERE service=? AND region=? AND city=?
    """, (service, region, city))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_master(tg_id):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT name, phone, service, region, city, description
        FROM masters WHERE telegram_id=?
    """, (tg_id,))
    row = cur.fetchone()
    conn.close()
    return row

def delete_master(tg_id):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("DELETE FROM masters WHERE telegram_id=?", (tg_id,))
    conn.commit()
    conn.close()

# =======================
# MENUS
# =======================
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🔍 Уста топиш"],
        ["👷 Уста сифатида рўйхатдан ўтиш"],
        ["👤 Менинг профилим"],
        ["❌ Рўйхатдан чиқиш"],
    ],
    resize_keyboard=True
)

def kb_from_list(lst):
    return ReplyKeyboardMarkup([[x] for x in lst] + [["⬅️ Орқага"]], resize_keyboard=True)

# =======================
# BASIC
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Ассалому алайкум!\nКеракли бўлимни танланг 👇",
        reply_markup=MAIN_MENU
    )

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# =======================
# FIND FLOW
# =======================
async def start_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "find"
    await update.message.reply_text("Хизматни танланг 👇", reply_markup=kb_from_list(SERVICES))

async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["service"] = update.message.text
    await update.message.reply_text("Вилоятни танланг 👇", reply_markup=kb_from_list(REGIONS.keys()))

async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    region = update.message.text
    context.user_data["region"] = region
    await update.message.reply_text("Шаҳар / туманни танланг 👇", reply_markup=kb_from_list(REGIONS[region]))

async def find_city(update, context):
    if context.user_data.get("mode") != "find":
        return

async def choose_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    d = context.user_data
    results = find_masters(d["service"], d["region"], city)

    if not results:
        await update.message.reply_text("😕 Усталар топилмади.", reply_markup=MAIN_MENU)
        return

    text = f"🔎 {d['service']} — {d['region']} / {city}\n\n"
    for i, (name, phone, desc) in enumerate(results, 1):
        text += (
            f"{i}. 👷 {name}\n"
            f"📞 {phone}\n"
            f"📝 {desc}\n\n"
        )

    await update.message.reply_text(text, reply_markup=MAIN_MENU)

# =======================
# REGISTER FLOW
# =======================
async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "register"
    kb = [[KeyboardButton("📞 Телефон юбориш", request_contact=True)]]
    await update.message.reply_text(
        "Телефон рақамингизни юборинг 👇",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.contact.phone_number
    await update.message.reply_text("Касбингизни танланг 👇", reply_markup=kb_from_list(SERVICES))

async def get_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["region"] = update.message.text
    await update.message.reply_text("Шаҳар / туманни танланг 👇", reply_markup=kb_from_list(REGIONS[update.message.text]))

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text
    await update.message.reply_text(
        "✍️ Қисқача изоҳ ёзинг (тажриба, иш турлари):"
    )

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    d = context.user_data
    add_master(
        u.id,
        u.full_name,
        d["phone"],
        d["service"],
        d["region"],
        d["city"],
        update.message.text
    )
    await update.message.reply_text("✅ Рўйхатдан ўтдингиз!", reply_markup=MAIN_MENU)

# =======================
# PROFILE / DELETE
# =======================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = get_master(update.effective_user.id)
    if not m:
        await update.message.reply_text("❌ Сиз уста эмассиз.", reply_markup=MAIN_MENU)
        return

    name, phone, service, region, city, desc = m
    await update.message.reply_text(
        f"👤 Профилим\n\n"
        f"👷 {name}\n📞 {phone}\n🛠 {service}\n📍 {region}, {city}\n📝 {desc}",
        reply_markup=MAIN_MENU
    )

async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delete_master(update.effective_user.id)
    await update.message.reply_text("❌ Рўйхатдан чиқдингиз.", reply_markup=MAIN_MENU)

# =======================
# MAIN
# =======================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^⬅️ Орқага$"), back))

    app.add_handler(MessageHandler(filters.Regex("^🔍 Уста топиш$"), start_find))
    app.add_handler(MessageHandler(filters.Regex("^👷"), start_register))
    app.add_handler(MessageHandler(filters.CONTACT, get_phone))

    app.add_handler(MessageHandler(filters.Regex("^(" + "|".join(SERVICES) + ")$"), choose_service))
    app.add_handler(MessageHandler(filters.Regex("^(" + "|".join(REGIONS.keys()) + ")$"), choose_region))
    app.add_handler(MessageHandler(filters.Regex("^(" + "|".join(sum(REGIONS.values(), [])) + ")$"), choose_city))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_description))

    app.add_handler(MessageHandler(filters.Regex("^👤"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^❌"), unregister))

    print("🤖 Bot ishга тушди")
    app.run_polling()

if __name__ == "__main__":
    main()

