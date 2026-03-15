import difflib
from regions import REGIONS


def normalize_text(text):
    if not text:
        return ""

    text = text.lower().strip()

    # apostroflarni bir xil qilamiz
    text = (
        text.replace("ʻ", "'")
        .replace("’", "'")
        .replace("`", "'")
        .replace("ʼ", "'")
    )

    # umumiy so'zlarni olib tashlash
    replacements = {
        " viloyati": "",
        " viloyat": "",
        " region": "",
        " province": "",
        " oblast": "",
        " shahri": " sh",
        " shahar": " sh",
        " city": " sh",
        " tumani": "",
        " tuman": "",
        " district": "",
        ".": "",
        ",": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = " ".join(text.split())
    return text


def build_region_aliases():
    return {
        "qashqadaryo": "Қашқадарё",
        "kashkadaryo": "Қашқадарё",
        "kashkadarya": "Қашқадарё",
        "qashkadaryo": "Қашқадарё",

        "toshkent": "Тошкент",
        "tashkent": "Тошкент",

        "samarqand": "Самарқанд",
        "samarkand": "Самарқанд",

        "buxoro": "Бухоро",
        "bukhara": "Бухоро",

        "andijon": "Андижон",
        "andijan": "Андижон",

        "fargona": "Фарғона",
        "fergana": "Фарғона",

        "namangan": "Наманган",
        "navoiy": "Навоий",
        "jizzax": "Жиззах",
        "jizzakh": "Жиззах",
        "surxondaryo": "Сурхондарё",
        "surkhandarya": "Сурхондарё",
        "sirdaryo": "Сирдарё",
        "xorazm": "Хоразм",
        "khorezm": "Хоразм",
        "qoraqalpogiston": "Қорақалпоғистон",
        "karakalpakstan": "Қорақалпоғистон",
    }


def build_district_aliases():
    return {
        "qarshi": "Қарши ш.",
        "qarshi sh": "Қарши ш.",
        "karshi": "Қарши ш.",
        "karshi sh": "Қарши ш.",
    }


def find_region(raw_region):
    if not raw_region:
        return None

    normalized = normalize_text(raw_region)

    # 1) tayyor aliasdan tekshiramiz
    aliases = build_region_aliases()
    if normalized in aliases:
        return aliases[normalized]

    # 2) REGIONS ichidagi asl nomlar bilan tekshiramiz
    regions = list(REGIONS["uz_kr"].keys())
    normalized_map = {
        normalize_text(region): region
        for region in regions
    }

    if normalized in normalized_map:
        return normalized_map[normalized]

    matches = difflib.get_close_matches(
        normalized,
        normalized_map.keys(),
        n=1,
        cutoff=0.5
    )

    if matches:
        return normalized_map[matches[0]]

    return None


def find_district(region, raw_district):
    if not region or not raw_district:
        return None

    normalized = normalize_text(raw_district)

    # 1) tayyor aliaslar
    aliases = build_district_aliases()
    if normalized in aliases:
        return aliases[normalized]

    # 2) shu region ichidagi districtlar bilan tekshiramiz
    districts = REGIONS["uz_kr"].get(region, [])
    normalized_map = {
        normalize_text(district): district
        for district in districts
    }

    if normalized in normalized_map:
        return normalized_map[normalized]

    matches = difflib.get_close_matches(
        normalized,
        normalized_map.keys(),
        n=1,
        cutoff=0.5
    )

    if matches:
        return normalized_map[matches[0]]

    return None
