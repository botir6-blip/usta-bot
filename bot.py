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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_id INTEGER,
            user_id INTEGER,
            rating INTEGER,
            UNIQUE(master_id, user_id)
        )
    """)

    conn.commit()
    conn.close()


def find_masters(service, city):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            m.id,
            m.name,
            m.phone,
            IFNULL(AVG(r.rating), 0),
            COUNT(r.rating)
        FROM masters m
        LEFT JOIN ratings r ON m.id = r.master_id
        WHERE LOWER(m.service)=LOWER(?) AND LOWER(m.city)=LOWER(?)
        GROUP BY m.id, m.name, m.phone
    """, (service, city))

    rows = cur.fetchall()
    conn.close()
    return rows


def get_master_by_telegram_id(tg_id):
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


def delete_master(tg_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM masters WHERE telegram_id = ?", (tg_id,))
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

RATING_MENU = ReplyKeyboardMarkup(
    [
        ["⭐ 1", "⭐ 2", "⭐ 3"],
        ["⭐ 4", "⭐ 5"],
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
        "Ассалому алайкум!\nКеракли хизматни танланг 👇",
        reply_markup=MAIN_MENU
    )


async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# =======================
# FIND MASTER
# =======================
async def usta_topish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "find"
    await update.message.reply_text("Қайси хизмат керак?", reply_markup=SERVICE_MENU)

async def find_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = context.user_data.get("service")
    city = update.message.text

    results = find_masters(service, city)

    if not results:
        await update.message.reply_text(
            f"😕 {service} бўйича {city} да уста топилмади.",
            reply_markup=MAIN_MENU
        )
        return

    context.user_data = {k: v for k, v in context.user_data.items() if not k.startswith("rate_")}

    text = f"🔎 {service} — {city} бўйича усталар:\n\n"

    for i, (mid, name, phone, avg, cnt) in enumerate(results, 1):
        stars = "⭐" * round(avg) if avg > 0 else "⭐ йўқ"
        text += (
            f"{i}. 👷 {name}\n"
            f"📞 {phone}\n"
            f"⭐ {stars} ({cnt} та баҳо)\n\n"
        )
        context.user_data[f"rate_{i}"] = mid

    keyboard = [[f"⭐ Баҳо бериш {i}"] for i in range(1, len(results)+1)]
    keyboard.append(["⬅️ Орқага"])

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# =======================
# REGISTER MASTER
# =======================
async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "register"

    keyboard = [[KeyboardButton("📞 Телефон рақамни юбориш", request_contact=True)]]
    await update.message.reply_text(
        "Телефон рақамингизни юборинг 👇",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.contact.phone_number
    await update.message.reply_text("Касбингизни танланг 👇", reply_markup=SERVICE_MENU)


async def register_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["service"] = update.message.text
    await update.message.reply_text("Қайси шаҳарда ишлайсиз?", reply_markup=CITY_MENU)

async def register_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("mode") != "register":
        return

    context.user_data["service"] = update.message.text
    await update.message.reply_text("Қайси шаҳарда ишлайсиз?", reply_markup=CITY_MENU)

async def register_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO masters
        (telegram_id, name, phone, service, city)
        VALUES (?, ?, ?, ?, ?)
    """, (
        user.id,
        user.full_name,
        context.user_data["phone"],
        context.user_data["service"],
        update.message.text
    ))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Рўйхатдан ўтдингиз!", reply_markup=MAIN_MENU)

# =======================
# PROFILE / UNREGISTER
# =======================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    master = get_master_by_telegram_id(update.effective_user.id)

    if not master:
        await update.message.reply_text("❌ Сиз уста эмассиз.", reply_markup=MAIN_MENU)
        return

    name, phone, service, city = master
    await update.message.reply_text(
        f"👤 Профиль\n\n"
        f"👷 {name}\n📞 {phone}\n🛠 {service}\n📍 {city}",
        reply_markup=MAIN_MENU
    )


async def unregister_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delete_master(update.effective_user.id)
    await update.message.reply_text("❌ Рўйхатдан чиқдингиз.", reply_markup=MAIN_MENU)

# =======================
# RATING
# =======================
async def start_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    index = int(update.message.text.split()[-1])
    context.user_data["rating_master"] = context.user_data.get(f"rate_{index}")
    await update.message.reply_text("Баҳо қўйинг 👇", reply_markup=RATING_MENU)


async def save_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rating = int(update.message.text.replace("⭐", "").strip())
    master_id = context.user_data.get("rating_master")
    user_id = update.effective_user.id

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT telegram_id FROM masters WHERE id=?", (master_id,))
    owner = cur.fetchone()

    if owner and owner[0] == user_id:
        await update.message.reply_text("❌ Ўзингизни баҳолай олмайсиз.", reply_markup=MAIN_MENU)
        conn.close()
        return

    cur.execute("""
        INSERT OR REPLACE INTO ratings (master_id, user_id, rating)
        VALUES (?, ?, ?)
    """, (master_id, user_id, rating))

    conn.commit()
    conn.close()

    await update.message.reply_text("⭐ Баҳо сақланди, раҳмат!", reply_markup=MAIN_MENU)

# =======================
# MAIN
# =======================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^⬅️ Орқага$"), back))

    app.add_handler(MessageHandler(filters.Regex("^🔍 Уста топиш$"), usta_topish))
    app.add_handler(MessageHandler(filters.Regex("^(🔧|⚡|🧱|🧹)"), find_service))

    app.add_handler(MessageHandler(filters.Regex("^(Қарши|Самарқанд|Тошкент|Бухоро)$"), find_city))

    app.add_handler(MessageHandler(filters.Regex("^👷 Уста сифатида рўйхатдан ўтиш$"), register_start))
    app.add_handler(MessageHandler(filters.CONTACT, register_phone))
    app.add_handler(MessageHandler(filters.Regex("^(🔧|⚡|🧱|🧹)"), register_service))
    app.add_handler(MessageHandler(filters.Regex("^(Қарши|Самарқанд|Тошкент|Бухоро)$"), register_city))

    app.add_handler(MessageHandler(filters.Regex("^👤 Менинг профилим$"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^❌ Рўйхатдан чиқиш$"), unregister_master))

    app.add_handler(MessageHandler(filters.Regex("^⭐ Баҳо бериш"), start_rating))
    app.add_handler(MessageHandler(filters.Regex("^⭐ [1-5]$"), save_rating))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()

