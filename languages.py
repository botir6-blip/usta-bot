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
    "customer_menu": [
        ["🔎 Уста топиш", "🆔 Код орқали қидириш"],
        ["🪙 Танга", "🏆 Топ тангалар"],
        ["🎁 Таклиф қилиш", "👨‍🔧 Уста бўлиш"],
        ["🌐 Тилни ўзгартириш"]
    ],

    "master_menu": [
        ["👤 Менинг профилим", "📢 Бот янгиликлари"],
        ["🔎 Уста топиш", "🆔 Код орқали қидириш"],
        ["🪙 Танга", "🏆 Топ тангалар"],
        ["🎁 Таклиф қилиш", "🌐 Тилни ўзгартириш"]
    ],
    
    "welcome": "Ассалому алайкум! Танланг:",
    "back": "Орқага",
    "choose_language": "Тилни танланг:",
    "send_phone": "Телефон рақамингизни юборинг:",
    "choose_service": "Касбни танланг:",
    "choose_region": "Вилоятни танланг:",
    "choose_district": "Туманни танланг:",
    "no_masters": "❌ Бу ҳудудда ҳозирча уста топилмади.",
    "enter_age": "Ёшингизни киритинг:",
    "enter_experience": "Неча йиллик тажрибангиз бор?",
    "not_master": "Сиз уста эмассиз",
    "news_button": "📢 Бот янгиликлари",
    "unregistered_success": "❌ Сиз рўйхатдан чиқдингиз.",
    "not_registered": "Сиз ҳали уста сифатида рўйхатдан ўтмагансиз.",
    "backup_error": "❌ Backup вақтида хатолик юз берди:",
}

# ================= УЗБЕК (ЛОТИН) =================
UZ_LT = {
    "customer_menu": [
        ["🔎 Usta topish", "🆔 Kod orqali qidirish"],
        ["🪙 Tanga", "🏆 Top tangalar"],
        ["🎁 Taklif qilish", "👨‍🔧 Usta bo'lish"],
        ["🌐 Tilni o'zgartirish"]
    ],

    "master_menu": [
        ["👤 Mening profilim", "📢 Bot yangiliklari"],
        ["🔎 Usta topish", "🆔 Kod orqali qidirish"],
        ["🪙 Tanga", "🏆 Top tangalar"],
        ["🎁 Taklif qilish", "🌐 Tilni o'zgartirish"]
    ],

    "welcome": "Assalomu alaykum! Tanlang:",
    "back": "Orqaga",
    "choose_language": "Tilni tanlang:",
    "send_phone": "Telefon raqamingizni yuboring:",
    "choose_service": "Kasbni tanlang:",
    "choose_region": "Viloyatni tanlang:",
    "choose_district": "Tumanni tanlang:",
    "no_masters": "❌ Bu hududda hozircha usta topilmadi.",
    "enter_age": "Yoshingizni kiriting:",
    "enter_experience": "Necha yillik tajribangiz bor?",
    "not_master": "Siz usta emassiz",
    "news_button": "📢 Bot yangiliklari",
    "unregistered_success": "❌ Siz ro'yxatdan chiqdingiz.",
    "not_registered": "Siz hali usta sifatida ro'yxatdan o'tmagansiz.",
    "backup_error": "❌ Backup vaqtida xatolik yuz berdi:",
}

# ================= РУССКИЙ =================
RU = {
    "customer_menu": [
        ["🔎 Найти мастера", "🆔 Поиск по коду"],
        ["🪙 Монеты", "🏆 Топ монет"],
        ["🎁 Пригласить", "👨‍🔧 Стать мастером"],
        ["🌐 Изменить язык"]
    ],
    "master_menu": [
        ["👤 Мой профиль", "📢 Новости бота"],
        ["🔎 Найти мастера", "🆔 Поиск по коду"],
        ["🪙 Монеты", "🏆 Топ монет"],
        ["🎁 Пригласить", "🌐 Изменить язык"]
    ],

    "welcome": "Здравствуйте! Выберите:",
    "back": "Назад",
    "choose_language": "Выберите язык:",
    "send_phone": "Отправьте ваш номер телефона:",
    "choose_service": "Выберите профессию:",
    "choose_region": "Выберите область:",
    "choose_district": "Выберите район:",
    "no_masters": "❌ В этом районе мастеров пока нет.",
    "enter_age": "Введите ваш возраст:",
    "enter_experience": "Сколько лет опыта?",
    "not_master": "Вы не мастер",
    "news_button": "📢 Новости бота",
    "unregistered_success": "❌ Вы вышли из списка мастеров.",
    "not_registered": "Вы ещё не зарегистрированы как мастер.",
    "backup_error": "❌ Ошибка при создании backup:",
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
