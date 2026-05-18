# =========================================
# FILE: utils/llm_extractor.py
# SIMPLE + FAST + STABLE VERSION
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
# LOAD MODEL
# =========================================

model = genai.GenerativeModel(
    "models/gemini-2.5-flash"
)

# =========================================
# GSTIN VALIDATION REGEX
# =========================================

GST_PATTERN = re.compile(
    r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]$'
)

# =========================================
# SAFE JSON EXTRACTION
# =========================================

def extract_json(content):

    try:

        start = content.find("{")

        end = content.rfind("}") + 1

        json_text = content[start:end]

        return json.loads(json_text)

    except:

        return {}

# =========================================
# CLEAN MONEY VALUES
# =========================================

def clean_money(value):

    value = str(value)

    value = value.replace("₹", "")
    value = value.replace(",", "")
    value = value.replace("%", "")
    value = value.replace("Rs.", "")
    value = value.strip()

    try:

        return float(value)

    except:

        return 0

# =========================================
# VALIDATE GSTIN
# =========================================

def validate_gstin(gstin):

    gstin = str(gstin).strip().upper()

    return GST_PATTERN.match(gstin) is not None

# =========================================
# SMART GSTIN EXTRACTION
# =========================================

def extract_gstin_from_text(text):

    text_upper = text.upper()

    patterns = [
        # Fully lenient: all 15 chars after GST: label
        r'GSTIN?\s*[:#]?\s*([A-Z0-9]{15})',
        # Standard GSTIN format - lenient on O/0 in ALL letter positions
        r'\b(\d{2}[A-Z0-9]{5}\d{4}[A-Z0-9]{2}Z[A-Z0-9])\b',
        # Loose: 2 digits + 11 alphanum + Z + 1 alphanum
        r'\b(\d{2}[A-Z0-9]{11}Z[A-Z0-9])\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, text_upper)
        if match:
            g = match.group(1) if match.lastindex else match.group()
            # Must be exactly 15 chars
            if len(g) == 15:
                return g

    return ""

# =========================================
# MAIN EXTRACTION FUNCTION
# =========================================

def extract_invoice_llm(text, image=None):

    prompt = f"""
You are an expert at reading Indian GST tax invoices.

Analyze this invoice and extract ONLY these fields as valid JSON.

IMPORTANT RULES:
1. GSTIN: 15-character alphanumeric code near "GST:", "GSTIN:", "GST Registration No:" — copy EXACTLY.
2. Vendor Name: Business name at the TOP of the invoice.
3. Invoice Number: Look for "Invoice Number", "Invoice No", "Bill No", "B No:" — NOT Order Number.
4. Subtotal: Pre-tax amount (Net Amount / Taxable Value / Unit Price × Qty). NOT the final total.
5. Total Amount: Final amount payable at the BOTTOM.
6. GST Amount: Tax paid (CGST+SGST combined, or IGST alone).
7. GST Percentage: Tax rate percent. If CGST+SGST shown separately, ADD them. If IGST shown, use that value.
8. Category: Business type (restaurant, clothing, electronics, medicine, etc).

Return ONLY valid JSON. No explanation. No markdown.

FORMAT:
{{
  "GSTIN": "",
  "Invoice Number": "",
  "Vendor Name": "",
  "Subtotal": 0,
  "Total Amount": 0,
  "GST Amount": 0,
  "GST Percentage": 0,
  "Detected Products": [],
  "Category": ""
}}

SUPPLEMENTAL OCR TEXT (may have errors, use image as primary source):
{text}

"""

    try:

        # =====================================
        # GEMINI VISION (image) or TEXT fallback
        # =====================================

        if image is not None:
            # Gemini Vision: reads the image directly
            # Much more accurate for tables/structured layouts
            print("[LLM] Using Gemini Vision (image mode)")
            response = model.generate_content([prompt, image])
        else:
            # Text-only fallback
            print("[LLM] Using text-only mode")
            response = model.generate_content(prompt)

        content = response.text

        print("\n===== GEMINI RESPONSE =====\n")

        print(content)

        print("\n===========================\n")

        # =====================================
        # EXTRACT JSON
        # =====================================

        data = extract_json(content)

        detected_gstin = extract_gstin_from_text(
            text
        )
        if detected_gstin:
            data["GSTIN"] = detected_gstin

        # =====================================
        # DEFAULT VALUES
        # =====================================

        defaults = {

            "GSTIN": "",
            "Invoice Number": "",
            "Vendor Name": "Unknown",
            "Subtotal": 0,
            "Total Amount": 0,
            "GST Amount": 0,
            "GST Percentage": 0,
            "Detected Products": [],
            "Category": "General"
        }

        for key, value in defaults.items():

            if key not in data:

                data[key] = value

        # =====================================
        # CLEAN NUMERIC VALUES
        # =====================================

        data["Subtotal"] = clean_money(data["Subtotal"])
        data["Total Amount"] = clean_money(data["Total Amount"])
        data["GST Amount"] = clean_money(data["GST Amount"])
        data["GST Percentage"] = clean_money(data["GST Percentage"])

        # =====================================
        # SUBTOTAL FALLBACK
        # (Amazon uses 'Net Amount', others may differ)
        # =====================================

        if data["Subtotal"] == 0:
            sub_patterns = [
                r'net\s+amount[:\s]+([\d,]+(?:\.\d+)?)',
                r'sub\s*total[:\s]+([\d,]+(?:\.\d+)?)',
                r'taxable\s+value[:\s]+([\d,]+(?:\.\d+)?)',
                r'assessable\s+value[:\s]+([\d,]+(?:\.\d+)?)',
                r'base\s+amount[:\s]+([\d,]+(?:\.\d+)?)',
            ]
            for sp in sub_patterns:
                m = re.search(sp, text, re.IGNORECASE)
                if m:
                    try:
                        data["Subtotal"] = float(m.group(1).replace(',', ''))
                        print(f"[SUBTOTAL] Found via regex: {data['Subtotal']}")
                        break
                    except:
                        pass

        # =====================================
        # TOTAL AMOUNT: always try regex first
        # (Gemini often hallucinates large numbers)
        # =====================================

        total_patterns = [
            r'food\s+total\s*[:\s]+([\d,]+(?:\.\d+)?)',
            r'grand\s+total\s*[:\s]+([\d,]+(?:\.\d+)?)',
            r'total\s+amount\s*[:\s]+([\d,]+(?:\.\d+)?)',
            r'net\s+amount\s*[:\s]+([\d,]+(?:\.\d+)?)',
            r'bill\s+amount\s*[:\s]+([\d,]+(?:\.\d+)?)',
            r'amount\s+payable\s*[:\s]+([\d,]+(?:\.\d+)?)',
            r'\btotal\s*[:\s]+([\d,]+\.\d+)',
        ]
        regex_total = 0.0
        for tp in total_patterns:
            m = re.search(tp, text, re.IGNORECASE | re.MULTILINE)
            if m:
                try:
                    regex_total = float(m.group(1).replace(',', ''))
                    print(f"[TOTAL REGEX] matched pattern: {tp} → {regex_total}")
                    break
                except:
                    pass

        gemini_total = data.get("Total Amount", 0)

        # Prefer regex when it found something specific;
        # also override Gemini if its value looks absurd (> 1 million)
        if regex_total > 0 and (gemini_total == 0 or gemini_total > 1_000_000):
            data["Total Amount"] = regex_total
            print(f"[TOTAL] Using regex value: {regex_total} (Gemini had: {gemini_total})")
        elif gemini_total > 1_000_000:
            data["Total Amount"] = 0
            print(f"[TOTAL] Gemini value {gemini_total} too large, reset to 0")

        # =====================================
        # GST PERCENTAGE FALLBACK (CGST + SGST)
        # =====================================

        if data["GST Percentage"] == 0:
            # CGST + SGST (intra-state)
            cgst = re.search(r'CGST\s*@?\s*([\d.]+)\s*%', text, re.IGNORECASE)
            sgst = re.search(r'SGST\s*@?\s*([\d.]+)\s*%', text, re.IGNORECASE)
            # IGST (inter-state like Amazon Gujarat→Karnataka)
            igst = re.search(r'IGST\s*@?\s*([\d.]+)\s*%', text, re.IGNORECASE)
            # Table format: "5% | IGST" or "5 % IGST"
            igst_table = re.search(r'([\d.]+)\s*%\s*(?:IGST|GST)', text, re.IGNORECASE)
            # Tax Rate label in invoice tables
            tax_rate_label = re.search(r'Tax\s*Rate[:\s]+([\d.]+)\s*%?', text, re.IGNORECASE)
            # GST @ rate format
            gst_at = re.search(r'GST\s*@\s*([\d.]+)\s*%', text, re.IGNORECASE)

            if cgst and sgst:
                data["GST Percentage"] = float(cgst.group(1)) + float(sgst.group(1))
            elif igst:
                data["GST Percentage"] = float(igst.group(1))
            elif igst_table:
                data["GST Percentage"] = float(igst_table.group(1))
            elif tax_rate_label:
                data["GST Percentage"] = float(tax_rate_label.group(1))
            elif gst_at:
                data["GST Percentage"] = float(gst_at.group(1))

        # =====================================
        # GST AMOUNT FALLBACK
        # =====================================

        if data["GST Amount"] == 0:
            # Try CGST + SGST amounts
            cgst_amt = re.search(
                r'CGST.{0,40}?([\d,]+\.\d+)', text, re.IGNORECASE | re.DOTALL)
            sgst_amt = re.search(
                r'SGST.{0,40}?([\d,]+\.\d+)', text, re.IGNORECASE | re.DOTALL)
            igst_amt = re.search(
                r'IGST.{0,40}?([\d,]+\.\d+)', text, re.IGNORECASE | re.DOTALL)
            if cgst_amt and sgst_amt:
                data["GST Amount"] = round(
                    float(cgst_amt.group(1).replace(',', '')) +
                    float(sgst_amt.group(1).replace(',', '')), 2)
            elif igst_amt:
                data["GST Amount"] = float(igst_amt.group(1).replace(',', ''))

        # =====================================
        # GST % COMPUTED FROM AMOUNTS
        # =====================================

        VALID_SLABS = [0, 3, 5, 12, 18, 28]

        def snap_to_slab(rate, tolerance=3):
            nearest = min(VALID_SLABS, key=lambda s: abs(s - rate))
            return nearest if abs(nearest - rate) <= tolerance else None

        if data["GST Percentage"] == 0 and data["Subtotal"] > 0 and data["GST Amount"] > 0:
            snapped = snap_to_slab((data["GST Amount"] / data["Subtotal"]) * 100)
            if snapped is not None:
                data["GST Percentage"] = snapped
                print(f"[GST%] From amounts: {snapped}%")

        if data["GST Percentage"] == 0 and data["Total Amount"] > 0 and data["Subtotal"] > 0:
            implied = data["Total Amount"] - data["Subtotal"]
            if implied > 0:
                snapped = snap_to_slab((implied / data["Subtotal"]) * 100)
                if snapped is not None:
                    data["GST Percentage"] = snapped
                    print(f"[GST%] From total-subtotal: {snapped}%")

        # =====================================
        # GST % LAST RESORT: scan for valid slab %
        # near tax-related keywords in raw OCR text
        # =====================================

        if data["GST Percentage"] == 0:
            # Find any valid Indian GST slab % near a tax keyword
            gst_context = re.findall(
                r'(?:tax|gst|igst|cgst|sgst|rate).{0,20}?(\d+(?:\.\d+)?).{0,5}?%',
                text, re.IGNORECASE | re.DOTALL
            )
            gst_context += re.findall(
                r'(\d+(?:\.\d+)?).{0,5}?%.{0,20}?(?:igst|cgst|sgst|gst)',
                text, re.IGNORECASE | re.DOTALL
            )
            for val in gst_context:
                try:
                    v = float(val)
                    if v in VALID_SLABS and v > 0:
                        data["GST Percentage"] = v
                        print(f"[GST%] Keyword scan: {v}%")
                        break
                except:
                    pass

        # =====================================
        # CLEAN GSTIN
        # =====================================

        data["GSTIN"] = re.sub(
            r'[^A-Z0-9]',
            '',
            str(data["GSTIN"]).upper().strip()
        )

        # =====================================
        # OCR CORRECTIONS ON GSTIN
        # Fix O/0 and I/1 confusion per position
        # =====================================

        gstin = data["GSTIN"]
        if len(gstin) == 15:
            # Positions 0-1: state code = digits
            # Common OCR misreads: O→0, I→1, Q→0, G→6, S→5, B→8
            def fix_digit(c):
                return {'O':'0','I':'1','Q':'0','G':'6','S':'5','B':'8','Z':'2','D':'0'}.get(c, c)
            def fix_letter(c):
                return {'0':'O','1':'I','5':'S','8':'B'}.get(c, c)

            prefix    = ''.join(fix_digit(c) for c in gstin[0:2])
            pan_let   = ''.join(fix_letter(c) for c in gstin[2:7])
            pan_dig   = ''.join(fix_digit(c) for c in gstin[7:11])
            pan_last  = fix_letter(gstin[11])
            entity    = gstin[12]
            z_char    = 'Z'
            checksum  = gstin[14]
            gstin = prefix + pan_let + pan_dig + pan_last + entity + z_char + checksum
        data["GSTIN"] = gstin

        # =====================================
        # GSTIN VALIDATION
        # =====================================

        data["GST Valid"] = validate_gstin(
            data["GSTIN"]
        )

        # =====================================
        # DEBUG PRINT
        # =====================================

        print("\n===== FINAL EXTRACTED DATA =====\n")

        print(
            json.dumps(
                data,
                indent=4
            )
        )

        print("\n================================\n")

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
            "Subtotal": 0,
            "Total Amount": 0,
            "GST Amount": 0,
            "GST Percentage": 0,
            "Detected Products": [],
            "Category": "General",
            "GST Valid": False,
            "error": str(e)
        }