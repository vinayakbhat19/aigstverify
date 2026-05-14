# =========================================
# FILE: utils/product_classifier.py
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

# =========================================
# LOAD MODEL
# =========================================

model = genai.GenerativeModel(
    "models/gemini-2.5-flash"
)

# =========================================
# GST CATEGORY RULES
# =========================================

GST_RULES = {

    "restaurant": 5,

    "food": 5,

    "fashion": 5,

    "clothing": 5,

    "electronics": 18,

    "mobile": 18,

    "laptop": 18,

    "grocery": 5,

    "medical": 12,

    "pharmacy": 12,

    "gold": 3,

    "jewellery": 3,

    "automobile": 28,

    "furniture": 18,

    "cosmetics": 18,

    "books": 0,

    "stationery": 12
}

# =========================================
# DETECT PRODUCT CATEGORY
# =========================================

def detect_product_category(text):

    prompt = f"""

    Analyze this invoice text.

    Detect:

    1. Product category
    2. Product names
    3. Expected GST rate in India

    Return ONLY valid JSON.

    JSON FORMAT:

    {{
      "category":"",
      "products":[],
      "expected_gst":0
    }}

    OCR TEXT:
    {text}

    """

    try:

        # =====================================
        # GEMINI RESPONSE
        # =====================================

        response = model.generate_content(
            prompt
        )

        content = response.text

        print("\n===== PRODUCT CLASSIFIER =====\n")

        print(content)

        print("\n==============================\n")

        # =====================================
        # EXTRACT JSON
        # =====================================

        start = content.find("{")

        end = content.rfind("}") + 1

        json_text = content[start:end]

        data = json.loads(json_text)

        # =====================================
        # CLEAN CATEGORY
        # =====================================

        category = str(

            data.get(
                "category",
                "general"
            )

        ).lower()

        # =====================================
        # AUTO GST RULE
        # =====================================

        expected_gst = GST_RULES.get(

            category,

            data.get(
                "expected_gst",
                18
            )
        )

        # =====================================
        # RETURN RESULT
        # =====================================

        return {

            "category":

                category.title(),

            "products":

                data.get(
                    "products",
                    []
                ),

            "expected_gst":

                expected_gst,

            "ai_detected":

                True
        }

    except Exception as e:

        print(

            "Product Classification Error:",
            str(e)
        )

        # =====================================
        # FALLBACK
        # =====================================

        return {

            "category": "General",

            "products": [],

            "expected_gst": 18,

            "ai_detected": False,

            "error": str(e)
        }