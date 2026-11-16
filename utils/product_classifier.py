"""Works out the goods/service category of an invoice and the GST rates it should carry."""

import json

from config import GEMINI_API_KEY
from utils.gst_rates import expected_rates, find_category, is_restaurant_bill, rates_from_hsn


def _ask_gemini(text: str) -> str:
    """Category named by Gemini, or "" (only used when GEMINI_API_KEY is set)."""
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    prompt = ("Name the main product or service category of this Indian GST invoice in one or two words "
              "(for example restaurant, clothing, electronics, medicine, cement). "
              'Return only JSON: {"category": ""}\n\nOCR TEXT:\n' + text[:4000])
    content = model.generate_content(prompt).text
    return str(json.loads(content[content.find("{"):content.rfind("}") + 1]).get("category", ""))


def detect_product_category(text, items=None, invoice_date=None, hsn_codes=None):
    """{"category", "expected_rates" (set or None), "source"}.

    Every item name is looked up on its own and the invoice may carry any rate
    one of its items carries (a vegetable shop mixes 0% and 5% items). If any
    item is not recognised, the HSN codes are tried instead, then Gemini if a
    key is configured. The rest of the OCR text is not searched: addresses and
    captions ("Mobile: 98...", "Hotel Road") would give false categories. When
    nothing settles it, the expected rate is None and the rate check is skipped
    rather than guessed.
    """
    if isinstance(items, str):
        items = [items]
    items = [item for item in items or [] if str(item).strip()]
    if is_restaurant_bill(items):
        rates = expected_rates("restaurant", invoice_date)
        print(f"[classifier] restaurant bill (dish names) -> expected rates {sorted(rates)}")
        return {"category": "Restaurant", "expected_rates": rates, "source": "item names"}
    found = [find_category(item) for item in items]
    if found and all(found):
        rates = set()
        for key in found:
            rates |= expected_rates(key, invoice_date)
        label = ", ".join(dict.fromkeys(found))
        print(f"[classifier] category={label!r} from item names -> expected rates {sorted(rates)}")
        return {"category": label.title(), "expected_rates": rates, "source": "item names"}

    label, rates = rates_from_hsn(hsn_codes, invoice_date)
    if rates:
        print(f"[classifier] category={label!r} from HSN codes -> expected rates {sorted(rates)}")
        return {"category": label.capitalize(), "expected_rates": rates, "source": "HSN codes"}

    if GEMINI_API_KEY:
        try:
            category = find_category(_ask_gemini(text))
            if category:
                rates = expected_rates(category, invoice_date)
                print(f"[classifier] category={category!r} from Gemini -> expected rates {sorted(rates)}")
                return {"category": category.title(), "expected_rates": rates, "source": "gemini"}
        except Exception as error:
            print(f"[classifier] Gemini category lookup failed: {error}")
    print("[classifier] category unknown: rate not checked")
    return {"category": "", "expected_rates": None, "source": ""}
