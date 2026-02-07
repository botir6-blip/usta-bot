# database.py

MASTERS = {
    "Чироқчи": [
        {"name": "Алишер", "phone": "+998901111111"},
        {"name": "Бекзод", "phone": "+998902222222"},
    ],
    "Касби": [
        {"name": "Дилшод", "phone": "+998903333333"},
    ],
}


def get_masters_by_district(district):
    return MASTERS.get(district, [])
