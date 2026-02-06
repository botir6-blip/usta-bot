import os
import sqlite3
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

# =======================
# DATABASE
# =======================
def init_db():
    conn = sqlite3.connect("usta.db")
    cursor = conn.cursor()
    cursor.execute("""
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

async def city_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("mode") == "find":
        await find_city(update, context)
    else:
        await register_city(update, context)

def find_masters(service, city):
    conn = sqlite3.connect("usta.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, phone
        FROM masters
        WHERE LOWER(service)=LOWER(?) AND LOWER(city)=LOWER(?)
    """, (service, city))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_master_by_telegram_id(telegram_id):
    conn = sqlite3.connect("usta.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, phone, service, city
        FROM masters
        WHERE telegram_id = ?
    """, (telegram_id,))
    row = cursor.fetchone()
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

REGISTER_SERVICE_MENU = ReplyKeyboardMarkup(
    [
        ["🔧 Сантехник", "⚡ Электрик"],
        ["🧱 Қурилиш", "🧹 Уй тозалаш"],
    ],
    resize_keyboard=True
)


# =======================
# START / BACK
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Ассалому алайкум!\nКеракли хизматни танланг 👇",
        reply_markup=MAIN_MENU
    )


async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


# =======================
# FIND MASTER FLOW
# =======================
async def usta_topish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "find"

    await update.message.reply_text(
        "Қайси хизмат керак?",
        reply_markup=SERVICE_MENU
    )

async def find_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["find_service"] = update.message.text
    await update.message.reply_text(
        "Қайси шаҳар?",
        reply_markup=CITY_MENU
    )

async def service_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")

    if mode == "find":
        await find_service(update, context)
    elif mode == "register":
        await register_service(update, context)
    else:
        await update.message.reply_text("Илтимос, менюдан танланг 👇")

async def find_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = context.user_data.get("find_service")
    city = update.message.text

    results = find_masters(service, city)

    if not results:
        await update.message.reply_text(
            f"😕 {service} бўйича {city} да ҳозирча уста йўқ.",
            reply_markup=MAIN_MENU
        )
    else:
        text = f"🔎 {service} — {city} бўйича усталар:\n\n"
        for i, (name, phone) in enumerate(results, 1):
            text += f"{i}. 👷 {name}\n📞 {phone}\n\n"

        await update.message.reply_text(text, reply_markup=MAIN_MENU)


# =======================
# REGISTER MASTER FLOW
# =======================
async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "register"

    keyboard = [[KeyboardButton("📞 Телефон рақамни юбориш", request_contact=True)]]
    await update.message.reply_text(
        "Уста сифатида рўйхатдан ўтиш учун телефон юборинг 👇",
        reply_markup=ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
    )


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact:
        return

    context.user_data["phone"] = contact.phone_number

    await update.message.reply_text(
        "Касбингизни танланг 👇",
        reply_markup=REGISTER_SERVICE_MENU
    )

async def unregister_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    delete_master(user.id)

    context.user_data.clear()
    await update.message.reply_text(
        "❌ Сиз уста сифатида рўйхатдан чиқдингиз.",
        reply_markup=MAIN_MENU
    )

async def register_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["service"] = update.message.text

    await update.message.reply_text(
        "Қайси шаҳарда ишлайсиз?",
        reply_markup=CITY_MENU
    )

def delete_master(telegram_id):
    conn = sqlite3.connect("usta.db")
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM masters WHERE telegram_id = ?",
        (telegram_id,)
    )
    conn.commit()
    conn.close()

async def register_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    service = context.user_data.get("service")
    phone = context.user_data.get("phone")
    user = update.effective_user

    conn = sqlite3.connect("usta.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO masters
        (telegram_id, name, phone, service, city)
        VALUES (?, ?, ?, ?, ?)
    """, (
        user.id,
        user.full_name,
        phone,
        service,
        city
    ))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Сиз муваффақиятли рўйхатдан ўтдингиз!",
        reply_markup=MAIN_MENU
    )
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    master = get_master_by_telegram_id(user.id)

    if not master:
        await update.message.reply_text(
            "❌ Сиз уста сифатида рўйхатдан ўтмагансиз.",
            reply_markup=MAIN_MENU
        )
        return

    name, phone, service, city = master

    text = (
        "👤 *Менинг профилим*\n\n"
        f"👷 Исм: {name}\n"
        f"📞 Телефон: {phone}\n"
        f"🛠 Касб: {service}\n"
        f"📍 Шаҳар: {city}"
    )

    await update.message.reply_text(
        text,
        reply_markup=MAIN_MENU,
        parse_mode="Markdown"
    )


# =======================
# MAIN
# =======================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # back
    app.add_handler(MessageHandler(filters.Regex("^⬅️ Орқага$"), back))

    # find master
    app.add_handler(MessageHandler(filters.Regex("^🔍 Уста топиш$"), usta_topish))
    
    app.add_handler(MessageHandler(filters.Regex("^(🔧 Сантехник|⚡ Электрик|🧱 Қурилиш|🧹 Уй тозалаш)$"), service_router))

    # city select (find / register)
    app.add_handler(MessageHandler(filters.Regex("^(Қарши|Самарқанд|Тошкент|Бухоро)$"), city_router))

    # register master
    app.add_handler(MessageHandler(filters.Regex("^👷 Уста сифатида рўйхатдан ўтиш$"), register_start))
    app.add_handler(MessageHandler(filters.CONTACT, register_phone))
    # unregister master
    app.add_handler(MessageHandler(filters.Regex("^❌ Рўйхатдан чиқиш$"), unregister_master))
    
    app.add_handler(MessageHandler(filters.Regex("^👤 Менинг профилим$"), my_profile))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()









