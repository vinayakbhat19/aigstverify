# =========================================
# FILE: utils/product_classifier.py
# COMPREHENSIVE AI-POWERED CATEGORY DETECTION
# =========================================

import google.generativeai as genai
import json

from config import GEMINI_API_KEY

# =========================================
# CONFIGURE GEMINI
# =========================================

genai.configure(
    api_key=GEMINI_API_KEY
)

model = genai.GenerativeModel(
    "models/gemini-2.5-flash"
)

# =========================================
# COMPREHENSIVE INDIAN GST RATE MAPPING
# Covers all major GST slabs (0,3,5,12,18,28%)
# Source: Indian GST Council rate schedule
# =========================================

GST_RATES = {

    # ===== 0% GST =====
    "agriculture": 0,
    "fresh produce": 0,
    "vegetables": 0,
    "fruits": 0,
    "grains": 0,
    "rice": 0,
    "wheat": 0,
    "pulses": 0,
    "milk": 0,
    "curd": 0,
    "eggs": 0,
    "salt": 0,
    "honey": 0,
    "books": 0,
    "newspaper": 0,
    "printed books": 0,
    "education": 0,
    "maps": 0,
    "stamps": 0,
    "postal": 0,
    "healthcare": 0,

    # ===== 3% GST =====
    "gold": 3,
    "silver": 3,
    "jewellery": 3,
    "jewelry": 3,
    "gems": 3,
    "precious stones": 3,
    "diamond": 3,
    "platinum": 3,

    # ===== 5% GST =====
    "restaurant": 5,
    "food": 5,
    "cafe": 5,
    "dhaba": 5,
    "eatery": 5,
    "canteen": 5,
    "mess": 5,
    "tiffin": 5,
    "catering": 5,
    "grocery": 5,
    "supermarket": 5,
    "kirana": 5,
    "general store": 5,
    "beverages": 5,
    "tea": 5,
    "coffee": 5,
    "juice": 5,
    "water": 5,
    "snacks": 5,
    "bakery": 5,
    "sweets": 5,
    "mithai": 5,
    "confectionery": 5,
    "biscuits": 5,
    "namkeen": 5,
    "spices": 5,
    "masala": 5,
    "oil": 5,
    "edible oil": 5,
    "clothing": 5,
    "apparel": 5,
    "fashion": 5,
    "garments": 5,
    "textiles": 5,
    "fabric": 5,
    "saree": 5,
    "kurta": 5,
    "dress": 5,
    "shirt": 5,
    "jeans": 5,
    "trousers": 5,
    "footwear": 5,
    "shoes": 5,
    "sandals": 5,
    "chappals": 5,
    "slippers": 5,
    "coal": 5,
    "fertilizer": 5,
    "pesticides": 5,
    "life-saving drugs": 5,
    "vaccines": 5,
    "insulin": 5,

    # ===== 12% GST =====
    "medicine": 12,
    "medicines": 12,
    "medical": 12,
    "pharmacy": 12,
    "pharmaceutical": 12,
    "drugs": 12,
    "hospital": 12,
    "clinic": 12,
    "diagnostic": 12,
    "ayurvedic": 12,
    "mobile": 12,
    "phone": 12,
    "smartphone": 12,
    "computer": 12,
    "laptop": 12,
    "tablet": 12,
    "desktop": 12,
    "printer": 12,
    "stationery": 12,
    "paper": 12,
    "notebook": 12,
    "pen": 12,
    "pencil": 12,
    "processed food": 12,
    "packaged food": 12,
    "frozen food": 12,
    "canned food": 12,
    "dairy": 12,
    "cheese": 12,
    "butter": 12,
    "hotel": 12,
    "accommodation": 12,
    "lodge": 12,
    "guesthouse": 12,
    "hostel": 12,
    "construction": 12,
    "tiles": 12,
    "plywood": 12,
    "building": 12,
    "sports goods": 12,
    "sports": 12,
    "exercise": 12,
    "fitness": 12,
    "gym": 12,
    "yoga": 12,
    "cycles": 12,
    "bicycle": 12,
    "sewing machine": 12,
    "umbrella": 12,
    "spectacles": 12,
    "glasses": 12,
    "optics": 12,

    # ===== 18% GST =====
    "electronics": 18,
    "appliances": 18,
    "electrical": 18,
    "refrigerator": 18,
    "fridge": 18,
    "washing machine": 18,
    "air conditioner": 18,
    "ac": 18,
    "television": 18,
    "tv": 18,
    "monitor": 18,
    "camera": 18,
    "headphones": 18,
    "earphones": 18,
    "speakers": 18,
    "audio": 18,
    "gaming": 18,
    "software": 18,
    "it services": 18,
    "telecom": 18,
    "internet": 18,
    "broadband": 18,
    "mobile data": 18,
    "furniture": 18,
    "sofa": 18,
    "chair": 18,
    "wardrobe": 18,
    "mattress": 18,
    "cosmetics": 18,
    "beauty": 18,
    "skincare": 18,
    "haircare": 18,
    "perfume": 18,
    "deodorant": 18,
    "makeup": 18,
    "salon": 18,
    "spa": 18,
    "parlour": 18,
    "insurance": 18,
    "banking": 18,
    "financial services": 18,
    "mutual funds": 18,
    "industrial": 18,
    "machinery": 18,
    "tools": 18,
    "hardware": 18,
    "paint": 18,
    "chemicals": 18,
    "adhesives": 18,
    "plastic": 18,
    "rubber": 18,
    "packaging": 18,
    "courier": 18,
    "logistics": 18,
    "transport": 18,
    "hotel ac": 18,
    "fine dining": 18,
    "restaurant ac": 18,

    # ===== 28% GST =====
    "automobile": 28,
    "car": 28,
    "vehicle": 28,
    "motorcycle": 28,
    "bike": 28,
    "scooter": 28,
    "luxury goods": 28,
    "luxury car": 28,
    "tobacco": 28,
    "cigarette": 28,
    "cigar": 28,
    "pan masala": 28,
    "aerated drinks": 28,
    "soft drinks": 28,
    "soda": 28,
    "cola": 28,
    "cement": 28,
    "concrete": 28,
    "casino": 28,
    "lottery": 28,
    "dishwasher": 28,
    "vacuum cleaner": 28,
    "projector": 28,
    "yacht": 28,
    "aircraft": 28,
}

# =========================================
# GST RATE LOOKUP
# Uses fuzzy matching against all categories
# =========================================

def get_gst_rate(category):
    """
    Find GST rate for any product/service category.
    Uses multi-level fuzzy matching:
    1. Exact match
    2. Category contains a key
    3. A key contains the category
    Falls back to 18% (most common rate) if unknown.
    """

    cat = category.lower().strip()

    if not cat or cat in ("general", "unknown", "other", ""):
        return 18

    # 1. Exact match
    if cat in GST_RATES:
        return GST_RATES[cat]

    # 2. Any GST key found inside the category string
    for key, rate in GST_RATES.items():
        if key in cat:
            return rate

    # 3. Category found inside any GST key
    words = cat.split()
    for word in words:
        if len(word) > 3:  # skip short words
            if word in GST_RATES:
                return GST_RATES[word]

    # Default
    return 18

# =========================================
# DETECT PRODUCT CATEGORY
# Uses Gemini's AI category as primary source,
# with optional Gemini call if not provided.
# =========================================

def detect_product_category(text, ai_category=None):

    prompt = f"""
You are an Indian GST taxation expert.

Analyze this invoice text and determine:
1. The specific product/service category (be precise - e.g. "restaurant food", "clothing", "electronics", "medicine", "automobile", "jewellery", "cosmetics", "furniture")
2. The list of products/services
3. The applicable GST rate under Indian GST law

Return ONLY valid JSON:
{{
  "category": "",
  "products": [],
  "expected_gst": 0
}}

OCR TEXT:
{text}
"""

    # =========================================
    # PRIMARY: Use AI category from LLM extractor
    # (avoids a second Gemini call)
    # =========================================

    if ai_category and ai_category.strip().lower() not in (
        "", "general", "unknown", "other", "none"
    ):
        category = ai_category.lower().strip()
        print(f"[CLASSIFIER] Using AI category: {category}")

    else:
        # =====================================
        # FALLBACK: Call Gemini for classification
        # =====================================
        try:
            response = model.generate_content(prompt)
            content = response.text
            print("\n===== PRODUCT CLASSIFIER =====\n")
            print(content)
            print("\n==============================\n")

            start = content.find("{")
            end = content.rfind("}") + 1
            data = json.loads(content[start:end])
            category = str(
                data.get("category", "general")
            ).lower().strip()

        except Exception as e:
            print("Product Classification Error:", str(e))
            category = "general"

    # =========================================
    # GST RATE LOOKUP
    # =========================================

    expected_gst = get_gst_rate(category)

    print(f"[CLASSIFIER] Category: {category!r} → GST: {expected_gst}%")

    return {
        "category": category.title(),
        "products": [],
        "expected_gst": expected_gst,
        "ai_detected": True
    }