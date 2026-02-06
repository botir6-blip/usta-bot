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

# =======================
# DATABASE
# =======================
def init_db():
    conn = sqlite3.connect("usta.db")
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


def get_masters(service, city):
    conn = sqlite3.connect("usta.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT m.id, m.name, m.phone,
               IFNULL(AVG(r.rating),0),
               COUNT(r.rating)
        FROM masters m
        LEFT JOIN ratings r ON m.id = r.master_id
        WHERE LOWER(m.service)=LOWER(?) AND LOWER(m.city)=LOWER(?)
        GROUP BY m.id
    """, (service, city))

    rows = cur.fetchall()
    conn.close()
    return rows


def get_master_by_user(user_id):
    conn = sqlite3.connect("usta.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT name, phone, service, city
        FROM masters WHERE telegram_id=?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def delete_master(user_id):
    conn = sqlite3.connect("usta.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM masters WHERE telegram_id=?", (user_id,))
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
# BASIC
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
# FIND FLOW
# =======================
async def start_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "find"
    await update.message.reply_text("Қайси хизмат керак?", reply_markup=SERVICE_MENU)


async def select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["service"] = update.message.text
    await update.message.reply_text("Қайси шаҳар?", reply_markup=CITY_MENU)


async def select_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = context.user_data.get("service")
    city = update.message.text

    results = get_masters(service, city)
    if not results:
        await update.message.reply_text(
            f"😕 {service} бўйича {city} да уста топилмади.",
            reply_markup=MAIN_MENU
        )
        return

    text = f"🔎 {service} — {city}\n\n"
    context.user_data.clear()

    for i, (mid, name, phone, avg, cnt) in enumerate(results, 1):
        stars = "⭐" * round(avg) if avg else "⭐ йўқ"
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
# REGISTER FLOW
# =======================
async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "register"
    kb = [[KeyboardButton("📞 Телефон рақамни юбориш", request_contact=True)]]
    await update.message.reply_text(
        "Телефон рақамингизни юборинг 👇",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.contact.phone_number
    await update.message.reply_text("Касбингизни танланг 👇", reply_markup=SERVICE_MENU)


async def register_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect("usta.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO masters
        (telegram_id,name,phone,service,city)
        VALUES (?,?,?,?,?)
    """, (
        user.id,
        user.full_name,
        context.user_data["phone"],
        context.user_data["service"],
        update.message.text
    ))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Рўйхатдан ўтдингиз!",
        reply_markup=MAIN_MENU
    )

# =======================
# RATING
# =======================
async def start_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idx = int(update.message.text.split()[-1])
    context.user_data["rating_master"] = context.user_data.get(f"rate_{idx}")
    await update.message.reply_text("Баҳо беринг 👇", reply_markup=RATING_MENU)


async def save_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rating = int(update.message.text.replace("⭐", "").strip())
    mid = context.user_data.get("rating_master")
    uid = update.effective_user.id

    conn = sqlite3.connect("usta.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO ratings (master_id,user_id,rating)
        VALUES (?,?,?)
    """, (mid, uid, rating))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Раҳмат!", reply_markup=MAIN_MENU)

# =======================
# PROFILE / DELETE
# =======================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_master_by_user(update.effective_user.id)
    if not row:
        await update.message.reply_text("❌ Сиз рўйхатдан ўтмагансиз.", reply_markup=MAIN_MENU)
        return

    name, phone, service, city = row
    await update.message.reply_text(
        f"👤 Профилим\n\n"
        f"👷 {name}\n📞 {phone}\n🛠 {service}\n📍 {city}",
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
    app.add_handler(MessageHandler(filters.Regex("^(🔧|⚡|🧱|🧹)"), select_service))
    app.add_handler(MessageHandler(filters.Regex("^(Қарши|Самарқанд|Тошкент|Бухоро)$"), select_city))
    app.add_handler(MessageHandler(filters.Regex("^⭐ Баҳо бериш"), start_rating))
    app.add_handler(MessageHandler(filters.Regex("^⭐ [1-5]$"), save_rating))
    app.add_handler(MessageHandler(filters.Regex("^👤"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^❌"), unregister))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
