import difflib
from regions import REGIONS


def normalize_text(text):
    if not text:
        return ""

    text = text.lower().strip()

    text = text.replace("shahri", "sh.")
    text = text.replace("shahar", "sh.")
    text = text.replace("city", "sh.")
    text = text.replace("tumani", "")
    text = text.replace("tuman", "")
    text = text.replace("district", "")
    text = text.replace("viloyati", "")
    text = text.replace("region", "")

    text = " ".join(text.split())

    return text


def find_region(raw_region):
    if not raw_region:
        return None

    regions = list(REGIONS["uz_kr"].keys())

    normalized = normalize_text(raw_region)

    mapping = {
        normalize_text(r): r
        for r in regions
    }

    match = difflib.get_close_matches(
        normalized,
        mapping.keys(),
        n=1,
        cutoff=0.6
    )

    if match:
        return mapping[match[0]]

    return None


def find_district(region, raw_district):

    if not region or not raw_district:
        return None

    districts = REGIONS["uz_kr"].get(region, [])

    normalized = normalize_text(raw_district)

    mapping = {
        normalize_text(d): d
        for d in districts
    }

    match = difflib.get_close_matches(
        normalized,
        mapping.keys(),
        n=1,
        cutoff=0.6
    )

    if match:
        return mapping[match[0]]

    return None
