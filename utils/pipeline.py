"""Invoice extraction pipeline: OCR -> LayoutLMv3 -> checks -> Gemini only when needed.

The local model's answer is accepted when the key fields are present, read
with enough confidence, the GSTIN checksum holds and the amounts add up.
Otherwise the invoice is passed to Gemini (if a key is configured), and the
reasons are recorded either way.
"""

import os
import re

from utils import layout_extractor
from utils.ocr import extract_lines, split_words
from utils.validator import gstin_checksum_ok

MIN_CONFIDENCE = float(os.getenv("EXTRACTION_MIN_CONFIDENCE", "0.80"))
REQUIRED = ("vendor_gstin", "invoice_no", "total_amount")
SLABS = (0, 0.25, 3, 5, 12, 18, 28, 40)


def reconcile(fields: dict) -> list:
    """Fills amounts that follow from the others and returns the problems that remain."""
    problems = []
    total, taxable = fields.get("total_amount"), fields.get("taxable_value")
    taxes = [fields.get(k) for k in ("cgst_amount", "sgst_amount", "igst_amount")]
    # CGST and SGST are always equal, so one implies the other.
    if taxes[0] is not None and taxes[1] is None:
        taxes[1] = fields["sgst_amount"] = taxes[0]
    elif taxes[1] is not None and taxes[0] is None:
        taxes[0] = fields["cgst_amount"] = taxes[1]
    gst = sum(t for t in taxes if t is not None) if any(t is not None for t in taxes) else None

    if total is not None and taxable is not None and gst is None:
        gst = round(total - taxable, 2)
        problems.append("tax amount not read; taken as total minus taxable value")
    elif total is not None and gst is not None and taxable is None:
        taxable = fields["taxable_value"] = round(total - gst, 2)
        problems.append("taxable value not read; taken as total minus tax")
    fields["gst_amount"] = gst

    if total is None or taxable is None or gst is None:
        problems.append("amounts incomplete")
    elif abs(taxable + gst - total) > 1.0:  # invoices round to the nearest rupee
        problems.append(f"amounts do not add up: {taxable} + {gst} != {total}")
    elif gst < 0 or taxable <= 0:
        problems.append("amounts not plausible")

    rate = None
    if len(fields.get("gst_rates") or []) == 1:
        rate = fields["gst_rates"][0]
    elif taxable and gst is not None:
        implied = 100 * gst / taxable
        nearest = min(SLABS, key=lambda slab: abs(slab - implied))
        rate = nearest if abs(nearest - implied) <= 0.3 else round(implied, 2)
    fields["gst_rate"] = rate
    return problems


def review(result: dict) -> list:
    """Reasons the local extraction should not be trusted as is (empty = accept)."""
    fields, confidence = result["fields"], result["confidence"]
    reasons = []
    for name in REQUIRED:
        if fields.get(name) in (None, ""):
            reasons.append(f"{name} not found")
        elif confidence.get(name, 0) < MIN_CONFIDENCE:
            reasons.append(f"{name} low confidence ({confidence[name]:.2f})")
    if fields.get("vendor_gstin") and not gstin_checksum_ok(fields["vendor_gstin"]):
        reasons.append("vendor GSTIN fails checksum (misread or invalid)")
    reasons += [p for p in reconcile(fields) if not p.startswith(("tax amount not read", "taxable value not read"))]
    return reasons


def guess_category(items: list) -> str:
    """Category from item descriptions, using the app's keyword-to-rate table (no API call)."""
    from utils.product_classifier import GST_RATES

    text = " ".join(items).lower()
    matches = [key for key in GST_RATES if re.search(rf"\b{re.escape(key)}\b", text)]
    return max(matches, key=len) if matches else ""


def to_legacy(fields: dict) -> dict:
    """The dict shape the rest of the app (validators, report, database) expects."""
    return {
        "GSTIN": fields.get("vendor_gstin") or "",
        "Invoice Number": fields.get("invoice_no") or "",
        "Vendor Name": fields.get("vendor_name") or "Unknown",
        "Subtotal": fields.get("taxable_value") or 0,
        "Total Amount": fields.get("total_amount") or 0,
        "GST Amount": fields.get("gst_amount") or 0,
        "GST Percentage": fields.get("gst_rate") or 0,
        "Detected Products": fields.get("items") or [],
        "Category": guess_category(fields.get("items") or []),
        "Invoice Date": fields.get("invoice_date") or "",
        "Buyer Name": fields.get("buyer_name") or "",
        "Buyer GSTIN": fields.get("buyer_gstin") or "",
        "GST Valid": gstin_checksum_ok(fields.get("vendor_gstin") or ""),
    }


def _gemini_configured() -> bool:
    from config import GEMINI_API_KEY

    return bool(GEMINI_API_KEY)


def extract_invoice(image, use_fallback: bool = True):
    """Returns (data, text). data is the app's field dict plus how it was obtained:
    "Extraction Source" ("layoutlmv3" | "gemini" | "layoutlmv3-unverified"),
    "Fallback Reasons" and "Field Confidence".
    """
    lines = extract_lines(image)
    text = "\n".join(line["text"] for line in lines)
    local, reasons = None, ["local model not installed"]

    if layout_extractor.model_available():
        local = layout_extractor.extract_fields(image, split_words(lines))
        reasons = review(local)
        if not reasons:
            data = to_legacy(local["fields"])
            data.update({"Extraction Source": "layoutlmv3", "Fallback Reasons": [],
                         "Field Confidence": {k: round(v, 3) for k, v in local["confidence"].items()}})
            return data, text

    if use_fallback and _gemini_configured():
        from utils.llm_extractor import extract_invoice_llm

        data = extract_invoice_llm(text, image=image)
        if "error" not in data:
            # A locally read GSTIN that passes its checksum beats a re-read.
            local_gstin = local["fields"].get("vendor_gstin") if local else ""
            if local_gstin and gstin_checksum_ok(local_gstin) and not gstin_checksum_ok(data.get("GSTIN", "")):
                data["GSTIN"] = local_gstin
            data.update({"Extraction Source": "gemini", "Fallback Reasons": reasons})
            return data, text
        reasons = reasons + [f"Gemini fallback failed: {data['error']}"]

    data = to_legacy(local["fields"]) if local else to_legacy({})
    data.update({"Extraction Source": "layoutlmv3-unverified" if local else "none",
                 "Fallback Reasons": reasons,
                 "Field Confidence": {k: round(v, 3) for k, v in local["confidence"].items()} if local else {}})
    return data, text
