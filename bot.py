import os
import sqlite3
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

DB_NAME = "usta.db"

# =======================
# DATABASE
# =======================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS masters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            name TEXT,
            phone TEXT,
            service TEXT,
            city TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_master(user_id, name, phone, service, city):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO masters
        (telegram_id, name, phone, service, city)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, name, phone, service, city))
    conn.commit()
    conn.close()

def delete_master(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM masters WHERE telegram_id=?", (user_id,))
    conn.commit()
    conn.close()

def find_masters(service, city):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT name, phone
        FROM masters
        WHERE service=? AND city=?
    """, (service, city))
    rows = c.fetchall()
    conn.close()
    return rows

def get_master(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT name, phone, service, city
        FROM masters
        WHERE telegram_id=?
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    return row

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

SERVICE_MENU = ReplyKeyboardMarkup(
    [
        ["🔧 Сантехник", "⚡ Электрик"],
        ["🧱 Қурилиш", "🧹 Уй тозалаш"],
        ["⬅️ Орқага"],
    ],
    resize_keyboard=True
)

CITY_MENU = ReplyKeyboardMarkup(
    [
        ["Қарши", "Самарқанд"],
        ["Тошкент", "Бухоро"],
        ["⬅️ Орқага"],
    ],
    resize_keyboard=True
)

# =======================
# START / BACK
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
# FIND MASTER
# =======================
async def find_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["flow"] = "find"
    await update.message.reply_text("Қайси хизмат керак?", reply_markup=SERVICE_MENU)

async def find_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["service"] = update.message.text
    await update.message.reply_text("Қайси шаҳар?", reply_markup=CITY_MENU)

async def find_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = context.user_data.get("service")
    city = update.message.text

    masters = find_masters(service, city)

    if not masters:
        await update.message.reply_text(
            f"😕 {service} бўйича {city} да уста топилмади.",
            reply_markup=MAIN_MENU
        )
        return

    text = f"🔎 {service} — {city} бўйича усталар:\n\n"
    for i, (name, phone) in enumerate(masters, 1):
        text += f"{i}. 👷 {name}\n📞 {phone}\n\n"

    await update.message.reply_text(text, reply_markup=MAIN_MENU)

# =======================
# REGISTER MASTER
# =======================
async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["flow"] = "register"

    kb = [[KeyboardButton("📞 Телефон юбориш", request_contact=True)]]
    await update.message.reply_text(
        "Телефон рақамингизни юборинг 👇",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.contact.phone_number
    await update.message.reply_text("Касбингизни танланг 👇", reply_markup=SERVICE_MENU)

async def register_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["service"] = update.message.text
    await update.message.reply_text("Қайси шаҳарда ишлайсиз?", reply_markup=CITY_MENU)

async def register_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_master(
        user.id,
        user.full_name,
        context.user_data["phone"],
        context.user_data["service"],
        update.message.text
    )
    await update.message.reply_text(
        "✅ Сиз муваффақиятли рўйхатдан ўтдингиз!",
        reply_markup=MAIN_MENU
    )

# =======================
# PROFILE / UNREGISTER
# =======================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = get_master(user.id)

    if not data:
        await update.message.reply_text(
            "❌ Сиз уста сифатида рўйхатдан ўтмагансиз.",
            reply_markup=MAIN_MENU
        )
        return

    name, phone, service, city = data
    await update.message.reply_text(
        f"👤 Менинг профилим\n\n"
        f"👷 {name}\n"
        f"📞 {phone}\n"
        f"🛠 {service}\n"
        f"📍 {city}",
        reply_markup=MAIN_MENU
    )

async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delete_master(update.effective_user.id)
    await update.message.reply_text(
        "❌ Рўйхатдан чиқдингиз.",
        reply_markup=MAIN_MENU
    )

# =======================
# MAIN
# =======================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^⬅️ Орқага$"), back))

    app.add_handler(MessageHandler(filters.Regex("^🔍 Уста топиш$"), find_start))
    app.add_handler(MessageHandler(filters.Regex("^👷 Уста сифатида рўйхатдан ўтиш$"), register_start))
    app.add_handler(MessageHandler(filters.Regex("^👤 Менинг профилим$"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^❌ Рўйхатдан чиқиш$"), unregister))

    app.add_handler(MessageHandler(filters.CONTACT, register_phone))

    app.add_handler(MessageHandler(
        filters.Regex("^(🔧 Сантехник|⚡ Электрик|🧱 Қурилиш|🧹 Уй тозалаш)$") &
        filters.UserData("flow", "find"),
        find_service
    ))

    app.add_handler(MessageHandler(
        filters.Regex("^(🔧 Сантехник|⚡ Электрик|🧱 Қурилиш|🧹 Уй тозалаш)$") &
        filters.UserData("flow", "register"),
        register_service
    ))

    app.add_handler(MessageHandler(
        filters.Regex("^(Қарши|Самарқанд|Тошкент|Бухоро)$") &
        filters.UserData("flow", "find"),
        find_city
    ))

    app.add_handler(MessageHandler(
        filters.Regex("^(Қарши|Самарқанд|Тошкент|Бухоро)$") &
        filters.UserData("flow", "register"),
        register_city
    ))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
