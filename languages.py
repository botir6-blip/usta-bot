# ================= TILLAR =================
LANGUAGES = {
    "uz_kr": "Узбек (кирилл)",
    "uz_lt": "O'zbek (lotin)",
    "ru": "Русский"
}

# ================= TIL TUGMASI NOMLARI =================
LANGUAGE_NAMES = {
    "uz_kr": "🌐 Тилни ўзгартириш",
    "uz_lt": "🌐 Tilni o'zgartirish",
    "ru": "🌐 Изменить язык"
}
# ================= УЗБЕК (КИРИЛЛ) =================
UZ_KR = {

    # 🔹 MIJOZ MENU
    "customer_menu": [
        ["Уста топиш", "🔎 Код орқали қидириш"],
        ["🎁 Таклиф қилиш", "Уста бўлиш"],
        ["🌐 Тилни ўзгартириш"]
    ],

    # 🔹 USTA MENU
    "master_menu": [
        ["Менинг профилим", "📢 Бот янгиликлари"],
        ["🎁 Таклиф қилиш", "🌐 Тилни ўзгартириш"]
    ],
    
    "welcome": "Ассалому алайкум! Танланг:",
    "back": "Орқага",
    "choose_language": "Тилни танланг:",
    "send_phone": "Телефон рақамингизни юборинг:",
    "choose_service": "Касбни танланг:",
    "choose_region": "Вилоятни танланг:",
    "choose_district": "Туманни танланг:",
    "enter_age": "Ёшингизни киритинг:",
    "enter_experience": "Неча йиллик тажрибангиз бор?",
    "not_master": "Сиз уста эмассиз",
    "switch_to_customer": "👤 Мижоз режимига ўтиш",
    "news_button": "📢 Бот янгиликлари",
    "switch_to_master": "🛠 Уста режимига ўтиш"
}

# ================= УЗБЕК (ЛОТИН) =================
UZ_LT = {

    "customer_menu": [
        ["Usta topish", "🔎 Kod orqali qidirish"],
        ["🎁 Taklif qilish", "Usta bo'lish"],
        ["🌐 Tilni o'zgartirish"]
    ],

    "master_menu": [
        ["Mening profilim", "📢 Bot yangiliklari"],
        ["🎁 Taklif qilish", "🌐 Tilni o'zgartirish"]
    ],

    "welcome": "Assalomu alaykum! Tanlang:",
    "back": "Orqaga",
    "choose_language": "Tilni tanlang:",
    "send_phone": "Telefon raqamingizni yuboring:",
    "choose_service": "Kasbni tanlang:",
    "choose_region": "Viloyatni tanlang:",
    "choose_district": "Tumanni tanlang:",
    "enter_age": "Yoshingizni kiriting:",
    "enter_experience": "Necha yillik tajribangiz bor?",
    "not_master": "Siz usta emassiz",
    "switch_to_customer": "👤 Mijoz rejimiga o'tish",
    "news_button": "📢 Bot yangiliklari",
    "switch_to_master": "🛠 Usta rejimiga o'tish"
}

# ================= РУССКИЙ =================
RU = {

    "customer_menu": [
        ["Найти мастера", "🔎 Поиск по коду"],
        ["🎁 Пригласить", "Стать мастером"],
        ["🌐 Изменить язык"]
    ],

    "master_menu": [
        ["Мой профиль", "📢 Новости бота"],
        ["🎁 Пригласить", "🌐 Изменить язык"]
    ],

    "welcome": "Здравствуйте! Выберите:",
    "back": "Назад",
    "choose_language": "Выберите язык:",
    "send_phone": "Отправьте ваш номер телефона:",
    "choose_service": "Выберите профессию:",
    "choose_region": "Выберите область:",
    "choose_district": "Выберите район:",
    "enter_age": "Введите ваш возраст:",
    "enter_experience": "Сколько лет опыта?",
    "not_master": "Вы не мастер",
    "switch_to_customer": "👤 Перейти в режим клиента",
    "news_button": "📢 Новости бота",
    "switch_to_master": "🛠 Перейти в режим мастера"
}

# ================= GET TEXTS =================
def get_texts(language):
    if language == "uz_kr":
        return UZ_KR
    elif language == "uz_lt":
        return UZ_LT
    elif language == "ru":
        return RU
    else:
        return UZ_KR
