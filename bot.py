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


# =======================
# MENUS
# =======================
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🔍 Уста топиш"],
        ["👷 Уста сифатида рўйхатдан ўтиш"],
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


async def register_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["service"] = update.message.text

    await update.message.reply_text(
        "Қайси шаҳарда ишлайсиз?",
        reply_markup=CITY_MENU
    )


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
    app.add_handler(MessageHandler(
        filters.Regex("^(🔧 Сантехник|⚡ Электрик|🧱 Қурилиш|🧹 Уй тозалаш)$"),
        find_service
    ))
    app.add_handler(MessageHandler(
        filters.Regex("^(Қарши|Самарқанд|Тошкент|Бухоро)$"),
        find_city
    ))

    # register master
    app.add_handler(MessageHandler(filters.Regex("^👷 Уста сифатида рўйхатдан ўтиш$"), register_start))
    app.add_handler(MessageHandler(filters.CONTACT, register_phone))
    app.add_handler(MessageHandler(
        filters.Regex("^(🔧 Сантехник|⚡ Электрик|🧱 Қурилиш|🧹 Уй тозалаш)$"),
        register_service
    ))
    app.add_handler(MessageHandler(
        filters.Regex("^(Қарши|Самарқанд|Тошкент|Бухоро)$"),
        register_city
    ))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
