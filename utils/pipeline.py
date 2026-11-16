"""Invoice extraction pipeline.

EXTRACTOR picks how fields are read:
    vlm        (default) OpenCV clean-up, then a local vision-language model
               (Qwen3-VL-4B) writes the fields as JSON. No OCR, no fallback.
    layoutlmv3 OCR (PaddleOCR) -> fine-tuned LayoutLMv3 -> Gemini only when the
               result is not trusted and GEMINI_API_KEY is set.

Either way the result is reviewed: key fields present, read with enough
confidence, GSTIN checksum holds, amounts add up. Problems are recorded as
"Fallback Reasons" and the invoice is marked unverified.
"""

import os
import re
import time

from utils import layout_extractor
from utils.validator import gstin_checksum_ok

EXTRACTOR = os.getenv("EXTRACTOR", "vlm").lower()

def log(message: str):
    print(f"[pipeline] {message}", flush=True)


MIN_CONFIDENCE = float(os.getenv("EXTRACTION_MIN_CONFIDENCE", "0.80"))
REQUIRED = ("vendor_gstin", "invoice_no", "total_amount")
SLABS = (0, 0.25, 3, 5, 12, 18, 28, 40)


def reconcile(fields: dict, confidence: dict = None) -> list:
    """Fills amounts that follow from the others and returns the problems that remain.

    A derived amount is only as trustworthy as the amounts it came from, so its
    confidence is the lowest of theirs (written into confidence when given).
    """
    problems = []
    confidence = confidence if confidence is not None else {}
    conf = lambda key: confidence.get(key, 0.0)
    total, taxable = fields.get("total_amount"), fields.get("taxable_value")
    taxes = [fields.get(k) for k in ("cgst_amount", "sgst_amount", "igst_amount")]
    # CGST and SGST are always equal, so one implies the other.
    if taxes[0] is not None and taxes[1] is None:
        taxes[1] = fields["sgst_amount"] = taxes[0]
        confidence["sgst_amount"] = conf("cgst_amount")
    elif taxes[1] is not None and taxes[0] is None:
        taxes[0] = fields["cgst_amount"] = taxes[1]
        confidence["cgst_amount"] = conf("sgst_amount")
    gst = sum(t for t in taxes if t is not None) if any(t is not None for t in taxes) else None
    used = [k for k, t in zip(("cgst_amount", "sgst_amount", "igst_amount"), taxes) if t is not None]
    gst_conf = min((conf(k) for k in used), default=0.0)

    if total is not None and taxable is not None and gst is None:
        gst = round(total - taxable, 2)
        gst_conf = min(conf("total_amount"), conf("taxable_value"))
        problems.append("tax amount not read; taken as total minus taxable value")
    elif total is not None and gst is not None and taxable is None:
        taxable = round(total - gst, 2)
        confidence["taxable_value"] = min(conf("total_amount"), gst_conf)
        problems.append("taxable value not read; taken as total minus tax")
        if taxable <= 0:
            taxable = None
            problems.append("tax read as larger than the total, so it is a misread")
        fields["taxable_value"] = taxable
    if gst is not None and gst < 0:
        gst = None
    fields["gst_amount"] = gst
    confidence["gst_amount"] = gst_conf if gst is not None else 0.0

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
        # Only report a rate that is close to a real slab; anything else means misread amounts.
        rate = nearest if abs(nearest - implied) <= 0.3 else None
        if rate is None:
            problems.append(f"tax is {implied:.1f}% of taxable value, which is not a GST slab")
    fields["gst_rate"] = rate
    return problems


TOTAL_CAPTION = re.compile(
    r"(grand\s*total|invoice\s*total|total\s*amount|amount\s*payable|net\s*payable|bill\s*amount|"
    r"net\s*amount\s*payable|total\s*payable|\btotal\b|\btot\b)", re.I)
NOT_TOTAL = re.compile(r"sub\s*-?\s*total|total\s*(tax|gst|qty|quantity|items?|discount|savings)|before\s*tax|taxable", re.I)
AMOUNT = re.compile(r"(?<![\d,:/-])(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+\.\d{2}|\d{2,7})(?![\d%:/-])")


def total_from_text(lines: list):
    """Last-resort total: the amount on (or right of) the lowest 'Total'-style caption.

    Used only when the model found no total. Rows are rebuilt from OCR line boxes,
    because captions and their amounts are often detected as separate lines.
    """
    rows = []
    for line in lines:
        y0, y1 = line["box"][1], line["box"][3]
        for row in rows:
            overlap = min(y1, row["y1"]) - max(y0, row["y0"])
            if overlap > 0.5 * min(y1 - y0, row["y1"] - row["y0"]):
                row["lines"].append(line)
                break
        else:
            rows.append({"y0": y0, "y1": y1, "lines": [line]})
    best = None
    for row in rows:
        ordered = sorted(row["lines"], key=lambda l: l["box"][0])
        text = " ".join(l["text"] for l in ordered)
        caption = TOTAL_CAPTION.search(text)
        if not caption or NOT_TOTAL.search(text):
            continue
        amounts = [float(m.group(1).replace(",", "")) for m in AMOUNT.finditer(text[caption.end():])]
        if amounts:
            best = amounts[-1]  # lower rows win: the payable total is usually last
    return best


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
    reasons += [p for p in reconcile(fields, confidence) if not p.startswith(("tax amount not read", "taxable value not read"))]
    return reasons


def guess_category(items: list) -> str:
    """Category from item descriptions, using the rate table's keywords (no API call)."""
    from utils.gst_rates import find_category

    return find_category(" ".join(items))


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
        "HSN Codes": fields.get("hsn_codes") or [],
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
    "Extraction Source" ("vlm" | "vlm-unverified" | "layoutlmv3" | "gemini" |
    "layoutlmv3-unverified"), "Fallback Reasons" and "Field Confidence".
    """
    if EXTRACTOR == "layoutlmv3":
        return _extract_with_layoutlm(image, use_fallback)
    return _extract_with_vlm(image)


def _extract_with_vlm(image):
    from utils import vlm_extractor

    problem = vlm_extractor.check_ready()
    if problem:
        raise RuntimeError(problem)
    started = time.perf_counter()
    result = vlm_extractor.extract_fields(image)
    log(f"{vlm_extractor.MODEL} ({vlm_extractor.BACKEND}): {time.perf_counter() - started:.1f}s"
        + (f", image {', '.join(result['preprocessing'])}" if result["preprocessing"] else ""))
    reasons = review(result)
    data = to_legacy(result["fields"])
    data.update({"Extraction Source": "vlm-unverified" if reasons else "vlm",
                 "Fallback Reasons": reasons,
                 "Field Confidence": {k: round(v, 3) for k, v in result["confidence"].items()},
                 "Model": vlm_extractor.MODEL,
                 "Image Clean-up": result["preprocessing"]})
    return data, result["raw"]


def _extract_with_layoutlm(image, use_fallback: bool = True):
    from utils.ocr import extract_lines, split_words

    started = time.perf_counter()
    lines = extract_lines(image)
    log(f"OCR: {len(lines)} lines in {time.perf_counter() - started:.1f}s")
    text = "\n".join(line["text"] for line in lines)
    local, reasons = None, ["local model not installed"]

    if layout_extractor.model_available():
        started = time.perf_counter()
        local = layout_extractor.extract_fields(image, split_words(lines))
        log(f"layout model: {time.perf_counter() - started:.1f}s")
        if local["fields"].get("total_amount") is None:
            found = total_from_text(lines)
            if found is not None:
                # Low confidence on purpose: it fills the gap but still sends the invoice for checking.
                local["fields"]["total_amount"], local["confidence"]["total_amount"] = found, 0.5
                log(f"total not tagged by the model; found {found} next to a 'Total' caption")
        reasons = review(local)
        if not reasons:
            data = to_legacy(local["fields"])
            data.update({"Extraction Source": "layoutlmv3", "Fallback Reasons": [],
                         "Field Confidence": {k: round(v, 3) for k, v in local["confidence"].items()}})
            return data, text

    if use_fallback and _gemini_configured():
        from utils.llm_extractor import extract_invoice_llm

        log("local result not trusted, asking Gemini: " + "; ".join(reasons))
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
