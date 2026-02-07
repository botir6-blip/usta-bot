# database.py

MASTERS = {
    "Қарши": [
        {"name": "Ботир", "phone": "+998994150020"},
    ],
    "Чироқчи": [
        {"name": "Алишер", "phone": "+998901111111"},
    ],
}


def get_masters_by_district(district):
    return MASTERS.get(district, [])
