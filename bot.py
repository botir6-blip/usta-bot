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
    cur = conn.cursor()
    cur.execute("""
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

def add_or_update_master(tg_id, name, phone, service, city):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO masters
        (telegram_id, name, phone, service, city)
        VALUES (?, ?, ?, ?, ?)
    """, (tg_id, name, phone, service, city))
    conn.commit()
    conn.close()

def delete_master(tg_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM masters WHERE telegram_id = ?", (tg_id,))
    conn.commit()
    conn.close()

def get_master(tg_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT name, phone, service, city
        FROM masters
        WHERE telegram_id = ?
    """, (tg_id,))
    row = cur.fetchone()
    conn.close()
    return row

def find_masters(service, city):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT name, phone
        FROM masters
        WHERE service = ? AND city = ?
    """, (service, city))
    rows = cur.fetchall()
    conn.close()
    return rows

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
# FIND FLOW
# =======================
async def start_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "find"
    await update.message.reply_text(
        "Қайси хизмат керак?",
        reply_markup=SERVICE_MENU
    )

async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["service"] = update.message.text
    await update.message.reply_text(
        "Қайси шаҳар?",
        reply_markup=CITY_MENU
    )

async def choose_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")

    if mode == "find":
        service = context.user_data.get("service")
        city = update.message.text
        results = find_masters(service, city)

        if not results:
            await update.message.reply_text(
                f"😕 {service} бўйича {city} да уста топилмади.",
                reply_markup=MAIN_MENU
            )
            return

        text = f"🔎 {service} — {city}:\n\n"
        for i, (name, phone) in enumerate(results, 1):
            text += f"{i}. 👷 {name}\n📞 {phone}\n\n"

        await update.message.reply_text(text, reply_markup=MAIN_MENU)

    elif mode == "register":
        await finish_register(update, context)

# =======================
# REGISTER FLOW
# =======================
async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "register"

    kb = [[KeyboardButton("📞 Телефон рақамни юбориш", request_contact=True)]]
    await update.message.reply_text(
        "Телефон рақамингизни юборинг 👇",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
    )

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.contact:
        return
    context.user_data["phone"] = update.message.contact.phone_number
    await update.message.reply_text(
        "Касбингизни танланг 👇",
        reply_markup=SERVICE_MENU
    )

async def finish_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    user = update.effective_user

    add_or_update_master(
        user.id,
        user.full_name,
        context.user_data["phone"],
        context.user_data["service"],
        city
    )

    await update.message.reply_text(
        "✅ Сиз уста сифатида муваффақиятли рўйхатдан ўтдингиз!",
        reply_markup=MAIN_MENU
    )

# =======================
# PROFILE / DELETE
# =======================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    master = get_master(update.effective_user.id)
    if not master:
        await update.message.reply_text(
            "❌ Сиз уста сифатида рўйхатдан ўтмагансиз.",
            reply_markup=MAIN_MENU
        )
        return

    name, phone, service, city = master
    text = (
        f"👤 Профилим\n\n"
        f"👷 {name}\n"
        f"📞 {phone}\n"
        f"🛠 {service}\n"
        f"📍 {city}"
    )
    await update.message.reply_text(text, reply_markup=MAIN_MENU)

async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delete_master(update.effective_user.id)
    await update.message.reply_text(
        "❌ Сиз рўйхатдан чиқдингиз.",
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

    app.add_handler(MessageHandler(filters.Regex("^🔍 Уста топиш$"), start_find))
    app.add_handler(MessageHandler(filters.Regex("^👷 Уста сифатида рўйхатдан ўтиш$"), start_register))
    app.add_handler(MessageHandler(filters.CONTACT, get_phone))

    app.add_handler(MessageHandler(filters.Regex("^(🔧|⚡|🧱|🧹)"), choose_service))
    app.add_handler(MessageHandler(filters.Regex("^(Қарши|Самарқанд|Тошкент|Бухоро)$"), choose_city))

    app.add_handler(MessageHandler(filters.Regex("^👤 Менинг профилим$"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^❌ Рўйхатдан чиқиш$"), unregister))

    print("🤖 Bot ishga tushdi")
    app.run_polling()

if __name__ == "__main__":
    main()
