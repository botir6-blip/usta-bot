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

def init_db():
    conn = sqlite3.connect("usta.db")
    c = conn.cursor()

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

def clean_text(text):
    import re
    text = re.sub(r'[^\w\s\u0400-\u04FF\-.,()]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

MAIN_MENU = ReplyKeyboardMarkup([
    ["Уста топиш", "Топ-10 усталар"],
    ["Уста бўлиш", "Статистика"],
    ["Менинг профилим"],
    ["Рўйхатдан чиқиш"]
], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ассалому алайкум! Танланг:", reply_markup=MAIN_MENU)

async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("📞 Телефон юбориш", request_contact=True)]]
    await update.message.reply_text("Телефон рақамингизни юборинг:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def start_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Касбни танланг:", reply_markup=ReplyKeyboardMarkup([["Орқага"]], resize_keyboard=True))

async def show_top_masters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏆 Топ-10 усталар:", reply_markup=MAIN_MENU)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Статистика:", reply_markup=MAIN_MENU)

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👤 Менинг профилим:", reply_markup=MAIN_MENU)

async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Рўйхатдан чиқилди:", reply_markup=MAIN_MENU)

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Орқага":
        await update.message.reply_text("Ассалому алайкум! Танланг:", reply_markup=MAIN_MENU)

def main():
    print("Bot is starting...")
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^Уста бўлиш$"), start_register))
    app.add_handler(MessageHandler(filters.Regex("^Уста топиш$"), start_find))
    app.add_handler(MessageHandler(filters.Regex("^Топ-10 усталар$"), show_top_masters))
    app.add_handler(MessageHandler(filters.Regex("^Статистика$"), show_stats))
    app.add_handler(MessageHandler(filters.Regex("^Менинг профилим$"), my_profile))
    app.add_handler(MessageHandler(filters.Regex("^Рўйхатдан чиқиш$"), unregister))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
