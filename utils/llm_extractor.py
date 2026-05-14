# =========================================
# FILE: utils/llm_extractor.py
# =========================================

import google.generativeai as genai
import json
import re

from config import GEMINI_API_KEY

# =========================================
# CONFIGURE GEMINI
# =========================================

genai.configure(
    api_key=GEMINI_API_KEY
)

# =========================================
# LOAD GEMINI MODEL
# =========================================

model = genai.GenerativeModel(
    "models/gemini-2.5-flash"
)

# =========================================
# GSTIN REGEX
# =========================================

GST_PATTERN = re.compile(

    r'\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]'
)

# =========================================
# GSTIN OCR CORRECTION
# =========================================

def correct_gstin(gstin):

    if not gstin:

        return ""

    gstin = gstin.upper()

    chars = list(gstin)

    # =====================================
    # FIX NUMERIC POSITIONS
    # GSTIN FORMAT:
    #
    # 12ABCDE1234F1Z5
    # 012345678901234
    #
    # Numeric positions:
    # 0,1,7,8,9,10,12,14
    # =====================================

    numeric_fixes = {

        "O": "0",

        "I": "1",

        "Z": "2",

        "S": "5",

        "B": "8",

        "G": "6"
    }

    numeric_positions = [

        0,1,7,8,9,10,12,14
    ]

    for pos in numeric_positions:

        if pos < len(chars):

            chars[pos] = numeric_fixes.get(

                chars[pos],

                chars[pos]
            )

    corrected = "".join(chars)

    return corrected[:15]

# =========================================
# MAIN EXTRACTION FUNCTION
# =========================================

def extract_invoice_llm(text):

    prompt = f"""

    You are an AI GST invoice analyzer.

    Extract invoice details carefully.

    IMPORTANT RULES:

    - Extract exact GSTIN
    - Extract subtotal
    - Extract GST amount
    - Extract total amount
    - Extract GST percentage
    - Detect products
    - Detect invoice category

    RETURN ONLY VALID JSON.

    JSON FORMAT:

    {{
      "GSTIN":"",
      "Invoice Number":"",
      "Vendor Name":"",
      "Subtotal":"",
      "Total Amount":"",
      "GST Amount":"",
      "GST Percentage":"",
      "Detected Products":[],
      "Category":""
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

        print(content)

        # =====================================
        # JSON EXTRACTION
        # =====================================

        start = content.find("{")

        end = content.rfind("}") + 1

        json_text = content[start:end]

        data = json.loads(json_text)

        # =====================================
        # FORCE GSTIN EXTRACTION FROM OCR
        # =====================================

        ocr_upper = text.upper()

        gst_match = GST_PATTERN.search(
            ocr_upper
        )

        if gst_match:

            data["GSTIN"] = gst_match.group()

        else:

            # REMOVE SPACES/SYMBOLS

            cleaned_text = re.sub(

                r'[^A-Z0-9]',

                '',

                ocr_upper
            )

            gst_match = GST_PATTERN.search(
                cleaned_text
            )

            if gst_match:

                data["GSTIN"] = gst_match.group()

        # =====================================
        # GSTIN OCR CORRECTION
        # =====================================

        data["GSTIN"] = correct_gstin(

            data.get("GSTIN", "")
        )

        # =====================================
        # CLEAN GST PERCENTAGE
        # =====================================

        if "GST Percentage" in data:

            data["GST Percentage"] = str(

                data["GST Percentage"]

            ).replace("%", "").strip()

        # =====================================
        # CLEAN MONEY VALUES
        # =====================================

        money_fields = [

            "Subtotal",

            "Total Amount",

            "GST Amount"
        ]

        for field in money_fields:

            if field in data:

                data[field] = str(

                    data[field]

                ).replace("₹", "") \
                 .replace(",", "") \
                 .strip()

        # =====================================
        # DEFAULT VALUES
        # =====================================

        defaults = {

            "GSTIN": "",

            "Invoice Number": "",

            "Vendor Name": "",

            "Subtotal": "0",

            "Total Amount": "0",

            "GST Amount": "0",

            "GST Percentage": "0",

            "Detected Products": [],

            "Category": "Unknown"
        }

        for key, value in defaults.items():

            if key not in data:

                data[key] = value

        return data

    except Exception as e:

        print(

            "LLM Extraction Error:",
            str(e)
        )

        return {

            "GSTIN": "",

            "Invoice Number": "",

            "Vendor Name": "Unknown",

            "Subtotal": "0",

            "Total Amount": "0",

            "GST Amount": "0",

            "GST Percentage": "0",

            "Detected Products": [],

            "Category": "Unknown",

            "error": str(e)
        }