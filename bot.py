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
            city TEXT,
            description TEXT
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


def add_master(tg_id, name, phone, service, city, desc):
    conn = sqlite3.connect("usta.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO masters
        (telegram_id, name, phone, service, city, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (tg_id, name, phone, service, city, desc))
    conn.commit()
    conn.close()


def delete_master(tg_id):
    conn = sqlite3.connect("usta.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM masters WHERE telegram_id=?", (tg_id,))
    conn.commit()
    conn.close()


def get_master_by_tg(tg_id):
    conn = sqlite3.connect("usta.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, phone, service, city, description
        FROM masters WHERE telegram_id=?
    """, (tg_id,))
    row = cur.fetchone()
    conn.close()
    return row


def find_masters(service, city):
    conn = sqlite3.connect("usta.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            m.id, m.name, m.phone, m.description,
            IFNULL(AVG(r.rating), 0),
            COUNT(r.rating)
        FROM masters m
        LEFT JOIN ratings r ON m.id=r.master_id
        WHERE m.service=? AND m.city=?
        GROUP BY m.id
    """, (service, city))
    rows = cur.fetchall()
    conn.close()
    return rows


def save_rating(master_id, user_id, rating):
    conn = sqlite3.connect("usta.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO ratings (master_id, user_id, rating)
        VALUES (?, ?, ?)
    """, (master_id, user_id, rating))
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
# START
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Ассалому алайкум!\nКеракли бўлимни танланг 👇",
        reply_markup=MAIN_MENU
    )


# =======================
# FIND FLOW
# =======================
async def start_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["flow"] = "find"
    await update.message.reply_text(
        "Қайси хизмат керак?",
        reply_markup=SERVICE_MENU
    )


async def service_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("flow") == "find":
        context.user_data["service"] = update.message.text
        await update.message.reply_text("Қайси шаҳар?", reply_markup=CITY_MENU)

    elif context.user_data.get("flow") == "register":
        context.user_data["service"] = update.message.text
        await update.message.reply_text("Қайси шаҳарда ишлайсиз?", reply_markup=CITY_MENU)


async def city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    flow = context.user_data.get("flow")

    if flow == "find":
        service = context.user_data.get("service")
        results = find_masters(service, city)

        if not results:
            await update.message.reply_text(
                f"😕 {service} бўйича {city} да уста топилмади.",
                reply_markup=MAIN_MENU
            )
            return

        text = f"🔎 {service} — {city}:\n\n"
        context.user_data.clear()

        for i, (mid, name, phone, desc, avg, cnt) in enumerate(results, 1):
            stars = "⭐" * round(avg) if avg else "⭐ йўқ"
            text += (
                f"{i}. 👷 {name}\n"
                f"📞 {phone}\n"
                f"📝 {desc}\n"
                f"⭐ {stars} ({cnt})\n\n"
            )
            context.user_data[f"rate_{i}"] = mid

        kb = [[f"⭐ Баҳо бериш {i}"] for i in range(1, len(results)+1)]
        kb.append(["⬅️ Орқага"])

        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )

    elif flow == "register":
        context.user_data["city"] = city
        await update.message.reply_text("Қисқача изоҳ ёзинг (қандай ишлар қиласиз):")


# =======================
# REGISTER FLOW
# =======================
async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["flow"] = "register"

    kb = [[KeyboardButton("📞 Телефон юбориш", request_contact=True)]]
    await update.message.reply_text(
        "Телефон рақамингизни юборинг 👇",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.contact:
        return

    context.user_data["phone"] = update.message.contact.phone_number
    await update.message.reply_text(
        "Касбингизни танланг 👇",
        reply_markup=SERVICE_MENU
    )


async def save_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    user = update.effective_user

    add_master(
        user.id,
        user.full_name,
        context.user_data["phone"],
        context.user_data["service"],
        context.user_data["city"],
        desc
    )

    context.user_data.clear()
    await update.message.reply_text(
        "✅ Сиз уста сифатида рўйхатдан ўтдингиз!",
        reply_markup=MAIN_MENU
    )


# =======================
# RATING
# =======================
async def start_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idx = int(update.message.text.split()[-1])
    context.user_data["rate_master"] = context.user_data.get(f"rate_{idx}")
    await update.message.reply_text("Баҳо қўйинг 👇", reply_markup=RATING_MENU)


async def save_rating_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rating = int(update.message.text.replace("⭐", "").strip())
    save_rating(
        context.user_data["rate_master"],
        update.effective_user.id,
        rating
    )
    await update.message.reply_text("✅ Раҳмат!", reply_markup=MAIN_MENU)


# =======================
# PROFILE / UNREGISTER
# =======================
async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = get_master_by_tg(update.effective_user.id)
    if not m:
        await update.message.reply_text("❌ Сиз уста эмассиз", reply_markup=MAIN_MENU)
        return

    _, name, phone, service, city, desc = m
    await update.message.reply_text(
        f"👤 {name}\n📞 {phone}\n🛠 {service}\n📍 {city}\n📝 {desc}",
        reply_markup=MAIN_MENU
    )


async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delete_master(update.effective_user.id)
    await update.message.reply_text("❌ Рўйхатдан чиқдингиз", reply_markup=MAIN_MENU)


# =======================
# MAIN
# =======================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^🔍 Уста топиш$"), start_find))
    app.add_handler(MessageHandler(filters.Regex("^👷"), start_register))
    app.add_handler(MessageHandler(filters.CONTACT, get_phone))

    app.add_handler(MessageHandler(filters.Regex("^(🔧|⚡|🧱|🧹)"), service_handler))
    app.add_handler(MessageHandler(filters.Regex("^(Қарши|Самарқанд|Тошкент|Бухоро)$"), city_handler))
    app.add_handler(MessageHandler(filters.Regex("^⭐ Баҳо бериш"), start_rating))
    app.add_handler(MessageHandler(filters.Regex("^⭐ [1-5]$"), save_rating_handler))
    app.add_handler(MessageHandler(filters.Regex("^👤"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^❌"), unregister))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_description))

    print("🤖 Bot ishга тушди")
    app.run_polling()


if __name__ == "__main__":
    main()



