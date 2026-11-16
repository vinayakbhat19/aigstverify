"""Expected GST rates by category, before and after the 22 September 2025 rate change.

From 22 Sept 2025 most goods moved to two main slabs, 5% and 18%, with a 40%
rate for luxury and sin goods; most 12% items went to 5% and most 28% items to
18%. Each keyword maps to the set of rates a genuine invoice could carry in
that period (some categories legitimately use two rates, for example clothing
priced above or below Rs 2,500). Keywords whose rate depends too much on the
exact product or service are left out, so the rate check reports "not checked"
instead of raising a false alarm.

This table is a screening aid, not a legal reference: the authoritative rate is
the one notified for the item's HSN/SAC code.
"""

import re
from datetime import date

RATE_CHANGE_DATE = date(2025, 9, 22)

# keyword: (rates before 22 Sept 2025, rates from 22 Sept 2025)
RATES = {
    # Nil-rated essentials
    "fresh produce": ({0}, {0}), "vegetables": ({0}, {0}), "fruits": ({0}, {0}),
    "milk": ({0}, {0}), "curd": ({0}, {0}), "eggs": ({0}, {0}), "salt": ({0}, {0}),
    "books": ({0}, {0}), "printed books": ({0}, {0}), "newspaper": ({0}, {0}),
    "education": ({0}, {0}), "healthcare": ({0}, {0}),

    # Precious metals
    "gold": ({3}, {3}), "silver": ({3}, {3}), "jewellery": ({3}, {3}), "jewelry": ({3}, {3}),
    "diamond": ({0.25, 3}, {0.25, 3}), "platinum": ({3}, {3}),

    # Food and restaurants (restaurants inside premium hotels charge 18%)
    "restaurant": ({5, 18}, {5, 18}), "cafe": ({5, 18}, {5, 18}), "dhaba": ({5}, {5}),
    "eatery": ({5}, {5}), "canteen": ({5}, {5}), "catering": ({5, 18}, {5, 18}),
    "grocery": ({0, 5, 12, 18}, {0, 5, 18}), "supermarket": ({0, 5, 12, 18}, {0, 5, 18}),
    "kirana": ({0, 5, 12, 18}, {0, 5, 18}),
    "rice": ({0, 5}, {0, 5}), "wheat": ({0, 5}, {0, 5}), "pulses": ({0, 5}, {0, 5}),
    "tea": ({5}, {5}), "coffee": ({5, 18}, {5}), "spices": ({5}, {5}), "edible oil": ({5}, {5}),
    "sugar": ({5}, {5}), "honey": ({0, 5}, {0, 5}),
    "butter": ({12}, {5}), "cheese": ({12}, {5}), "ghee": ({12}, {5}),
    "packaged food": ({12, 18}, {5}), "processed food": ({12, 18}, {5}),
    "frozen food": ({12, 18}, {5}), "biscuits": ({18}, {5}), "namkeen": ({12}, {5}),
    "confectionery": ({18}, {5}), "chocolate": ({18}, {5}), "sweets": ({5}, {5}),
    "bakery": ({5, 18}, {5}), "juice": ({12}, {5}), "mineral water": ({18}, {5}),
    "packaged water": ({18}, {5}),
    "aerated drinks": ({28}, {40}), "soft drinks": ({28}, {40}), "cola": ({28}, {40}),
    "soda": ({28}, {40}),

    # Medicines
    "medicine": ({5, 12}, {0, 5}), "medicines": ({5, 12}, {0, 5}),
    "pharmacy": ({5, 12}, {0, 5}), "pharmaceutical": ({5, 12}, {0, 5}),
    "ayurvedic": ({12}, {5}), "insulin": ({5}, {0, 5}), "vaccines": ({5}, {0, 5}),

    # Clothing and footwear (rate depends on price per piece)
    "clothing": ({5, 12}, {5, 18}), "apparel": ({5, 12}, {5, 18}), "garments": ({5, 12}, {5, 18}),
    "textiles": ({5, 12}, {5, 18}), "saree": ({5, 12}, {5, 18}), "kurta": ({5, 12}, {5, 18}),
    "shirt": ({5, 12}, {5, 18}), "jeans": ({5, 12}, {5, 18}), "trousers": ({5, 12}, {5, 18}),
    "footwear": ({5, 12, 18}, {5, 18}), "shoes": ({5, 12, 18}, {5, 18}),
    "sandals": ({5, 12, 18}, {5, 18}), "chappals": ({5, 12}, {5, 18}),

    # Electronics and appliances
    "mobile": ({18}, {18}), "smartphone": ({18}, {18}), "laptop": ({18}, {18}),
    "computer": ({18}, {18}), "tablet": ({18}, {18}), "printer": ({18}, {18}),
    "electronics": ({18, 28}, {18}), "appliances": ({18, 28}, {18}),
    "television": ({18, 28}, {18}), "tv": ({18, 28}, {18}),
    "air conditioner": ({28}, {18}), "dishwasher": ({28}, {18}), "projector": ({28}, {18}),
    "refrigerator": ({18, 28}, {18}), "washing machine": ({18, 28}, {18}),
    "vacuum cleaner": ({28}, {18}), "headphones": ({18}, {18}), "speakers": ({18}, {18}),
    "camera": ({18}, {18}),

    # Personal care and services
    "cosmetics": ({18}, {18}), "makeup": ({18}, {18}), "perfume": ({18}, {18}),
    "deodorant": ({18}, {18}), "shampoo": ({18}, {5}), "toothpaste": ({18}, {5}),
    "soap": ({18}, {5}), "hair oil": ({18}, {5}),
    "salon": ({18}, {5}), "spa": ({18}, {5}), "parlour": ({18}, {5}),
    "gym": ({18}, {5}), "fitness": ({18}, {5}), "yoga": ({18}, {5}),
    "hotel": ({12, 18}, {5, 18}), "lodge": ({12, 18}, {5, 18}), "guesthouse": ({12, 18}, {5, 18}),

    # Goods that moved from 12% to 5%
    "bicycle": ({12}, {5}), "cycles": ({12}, {5}), "sports goods": ({12}, {5}),
    "umbrella": ({12}, {5}), "sewing machine": ({12}, {5}), "spectacles": ({12}, {5}),
    "tractor": ({12}, {5}), "fertilizer": ({5, 12}, {5}), "pesticides": ({18}, {5}),

    # Business goods and services
    "software": ({18}, {18}), "it services": ({18}, {18}), "telecom": ({18}, {18}),
    "internet": ({18}, {18}), "broadband": ({18}, {18}), "banking": ({18}, {18}),
    "furniture": ({12, 18}, {5, 18}), "mattress": ({18}, {18}),
    "machinery": ({12, 18}, {5, 18}), "hardware": ({18}, {18}), "tools": ({12, 18}, {5, 18}),
    "paint": ({18, 28}, {18}), "chemicals": ({18}, {18}), "plastic": ({18}, {18}),
    "cement": ({28}, {18}), "concrete": ({28}, {18}),

    # Vehicles and sin goods
    "automobile": ({28}, {18, 40}), "car": ({28}, {18, 40}), "vehicle": ({28}, {18, 40}),
    "motorcycle": ({28}, {18, 40}), "bike": ({28}, {18, 40}), "scooter": ({28}, {18, 40}),
    "auto parts": ({18, 28}, {18}), "tyres": ({28}, {18}),
    "luxury car": ({28}, {40}), "yacht": ({28}, {40}),
    "tobacco": ({28}, {28, 40}), "cigarette": ({28}, {28, 40}), "pan masala": ({28}, {28, 40}),
    "casino": ({28}, {40}), "lottery": ({28}, {40}),
}

KEYWORDS = sorted(RATES, key=len, reverse=True)  # longest first: "luxury car" before "car"


def find_category(text: str) -> str:
    """The most specific known keyword in the text, matched on whole words, or ""."""
    lowered = str(text or "").lower()
    for key in KEYWORDS:
        if re.search(rf"\b{re.escape(key)}\b", lowered):
            return key
    return ""


def _parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def expected_rates(category: str, invoice_date=None):
    """Set of plausible rates for the category on that date, or None when unknown.

    Without a readable date both periods' rates are accepted.
    """
    key = find_category(category)
    if not key:
        return None
    before, after = RATES[key]
    when = _parse_date(invoice_date) if invoice_date else None
    if when is None:
        return before | after
    return after if when >= RATE_CHANGE_DATE else before


# HSN/SAC chapter (first two digits, or four for services): (before, after).
# Only chapters whose possible rates are narrow enough to be useful are listed.
HSN_CHAPTERS = {
    "01": ("live animals", {0, 5, 12}, {0, 5}), "02": ("meat", {0, 5, 12}, {0, 5}),
    "03": ("fish", {0, 5, 12}, {0, 5}), "04": ("dairy", {0, 5, 12}, {0, 5}),
    "07": ("vegetables", {0, 5}, {0, 5}), "08": ("fruit and nuts", {0, 5, 12}, {0, 5}),
    "09": ("tea, coffee and spices", {0, 5}, {0, 5}), "10": ("cereals", {0, 5}, {0, 5}),
    "11": ("flour", {0, 5}, {0, 5}), "17": ("sugar and confectionery", {5, 18}, {5}),
    "19": ("bakery and cereal products", {0, 5, 12, 18}, {0, 5}),
    "20": ("processed fruit and vegetables", {5, 12}, {5}),
    "22": ("beverages", {5, 12, 18, 28}, {5, 18, 40}), "24": ("tobacco", {28}, {28, 40}),
    "30": ("pharmaceuticals", {0, 5, 12, 18}, {0, 5, 18}),
    "33": ("cosmetics and toiletries", {18, 28}, {5, 18}), "34": ("soap and detergents", {18}, {5, 18}),
    "61": ("knitted apparel", {5, 12}, {5, 18}), "62": ("apparel", {5, 12}, {5, 18}),
    "63": ("textile articles", {5, 12}, {5, 18}), "64": ("footwear", {5, 12, 18}, {5, 18}),
    "71": ("gold, silver and jewellery", {0.25, 3}, {0.25, 3}),
    "84": ("machinery and computers", {5, 12, 18, 28}, {5, 18}),
    "85": ("electrical and electronics", {5, 12, 18, 28}, {5, 18}),
    "87": ("vehicles and parts", {5, 12, 18, 28}, {5, 18, 40}),
    "9963": ("hotels and restaurants", {5, 12, 18}, {5, 18}),
}


def rates_from_hsn(codes, invoice_date=None):
    """(label, allowed rates) for the HSN codes on an invoice, or ("", None).

    Every code must fall in a listed chapter; otherwise the invoice may carry a
    rate this table cannot vouch for, and None is returned.
    """
    codes = [re.sub(r"\D", "", str(code)) for code in codes or []]
    codes = [code for code in codes if len(code) >= 4]
    if not codes:
        return "", None
    when = _parse_date(invoice_date) if invoice_date else None
    labels, allowed = [], set()
    for code in codes:
        entry = HSN_CHAPTERS.get(code[:4]) or HSN_CHAPTERS.get(code[:2])
        if not entry:
            return "", None
        label, before, after = entry
        labels.append(label)
        allowed |= (before | after) if when is None else (after if when >= RATE_CHANGE_DATE else before)
    return ", ".join(dict.fromkeys(labels)), allowed


# Words that only appear on food served by a restaurant. On such a bill every
# line (including "Butter Naan" or "Fresh Lime Soda") is a restaurant service.
DISH_WORDS = ("biryani", "dosa", "idli", "vada", "naan", "roti", "paratha", "thali", "masala dosa",
              "paneer", "tikka", "tandoori", "manchurian", "dal tadka", "dal fry", "dal makhani", "curry", "pulao", "fried rice",
              "curd rice", "jeera rice", "chai", "lassi", "gulab jamun", "meals", "combo", "starter",
              "noodles hakka", "sizzler", "kebab", "kabab", "chaat", "pav bhaji", "samosa")


def is_restaurant_bill(items) -> bool:
    text = " ".join(str(item) for item in items or []).lower()
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in DISH_WORDS)
