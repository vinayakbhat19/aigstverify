"""Field extraction with the fine-tuned LayoutLMv3 model.

Takes OCR words (utils/ocr.py) and the page image, tags every word with a field
label, and turns the tagged words into cleaned field values with a confidence
for each. The model directory comes from LAYOUT_MODEL_DIR (default
models/layoutlmv3-gst); train it with scripts/train_layoutlmv3.py.
"""

import os
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from utils.validator import gstin_checksum_ok

MODEL_DIR = Path(os.getenv("LAYOUT_MODEL_DIR", "models/layoutlmv3-gst"))

GSTIN_SHAPE = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]")
DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d-%b-%Y", "%d-%b-%y", "%d %b %Y",
                "%d %B %Y", "%d/%m/%y", "%d %b, %Y", "%d%b%Y", "%d %b,%Y", "%d-%B-%Y"]

# Characters OCR confuses, by what the GSTIN position must hold.
_TO_DIGIT = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "G": "6", "B": "8"}
_TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "6": "G", "8": "B"}


def model_available() -> bool:
    return (MODEL_DIR / "config.json").exists()


@lru_cache(maxsize=1)
def _load():
    import torch
    from transformers import AutoModelForTokenClassification, AutoProcessor

    processor = AutoProcessor.from_pretrained(MODEL_DIR, apply_ocr=False)
    model = AutoModelForTokenClassification.from_pretrained(MODEL_DIR)
    # LAYOUT_DEVICE=mps uses the Apple GPU; the default is CPU, which is reliable everywhere.
    device = os.getenv("LAYOUT_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
    # ONNX Runtime (OCR) and PyTorch each start their own thread pool; capping
    # PyTorch avoids the two oversubscribing the CPU when they run back to back.
    torch.set_num_threads(int(os.getenv("LAYOUT_THREADS", max(1, (os.cpu_count() or 4) // 2))))
    return processor, model.to(device).eval(), device


def tag_words(image, words: list) -> list:
    """(label, confidence) for each OCR word. Long pages are tagged in overlapping windows."""
    import torch

    if not words:
        return []
    processor, model, device = _load()
    width, height = image.size
    boxes = [[min(1000, max(0, round(1000 * w["box"][0] / width))),
              min(1000, max(0, round(1000 * w["box"][1] / height))),
              min(1000, max(0, round(1000 * w["box"][2] / width))),
              min(1000, max(0, round(1000 * w["box"][3] / height)))] for w in words]
    encoding = processor(image.convert("RGB"), [w["text"] for w in words], boxes=boxes,
                         truncation=True, max_length=512, stride=128, padding="max_length",
                         return_overflowing_tokens=True, return_tensors="pt")
    word_ids = [encoding.word_ids(i) for i in range(len(encoding["input_ids"]))]
    encoding.pop("overflow_to_sample_mapping", None)
    with torch.no_grad():
        # With overflow windows the processor returns pixel_values as a list of arrays.
        inputs = {key: (torch.stack([torch.as_tensor(v) for v in value]) if isinstance(value, list)
                        else value).to(device) for key, value in encoding.items()}
        logits = model(**inputs).logits
    probabilities = torch.softmax(logits, dim=-1).cpu()

    tags = [("O", 0.0)] * len(words)
    for window, ids in enumerate(word_ids):
        previous = None
        for position, word_id in enumerate(ids):
            if word_id is not None and word_id != previous:  # first sub-token of a word
                confidence, label = probabilities[window, position].max(dim=-1)
                if confidence.item() > tags[word_id][1]:
                    tags[word_id] = (model.config.id2label[label.item()], confidence.item())
            previous = word_id
    return tags


def group_entities(words: list, tags: list) -> dict:
    """{field: [{"text", "confidence"}]}: adjacent words with the same field form one entity."""
    entities, current = {}, None
    for word, (label, confidence) in zip(words, tags):
        kind = label[2:] if label != "O" else None
        if kind and current and current["kind"] == kind and not label.startswith("B-"):
            current["words"].append(word["text"])
            current["scores"].append(confidence)
            continue
        current = {"kind": kind, "words": [word["text"]], "scores": [confidence]} if kind else None
        if current:
            entities.setdefault(kind, []).append(current)
    return {
        kind: [{"text": " ".join(e["words"]), "confidence": min(e["scores"])} for e in found]
        for kind, found in entities.items()
    }


def clean_gstin(text: str) -> str:
    """Finds a GSTIN in OCR text, repairing digit/letter confusions position by position."""
    compact = re.sub(r"[^A-Z0-9]", "", text.upper())
    candidates = []
    for start in range(max(1, len(compact) - 14)):
        chunk = compact[start:start + 15]
        if len(chunk) < 15:
            break
        fixed = "".join(
            _TO_DIGIT.get(ch, ch) if i in (0, 1, 7, 8, 9, 10) else
            _TO_LETTER.get(ch, ch) if i in (2, 3, 4, 5, 6, 11) else
            "Z" if i == 13 and ch in "Z2" else ch
            for i, ch in enumerate(chunk))
        if GSTIN_SHAPE.fullmatch(fixed):
            candidates.append(fixed)
            # The check character is itself often misread; try its look-alikes.
            swap = {**_TO_DIGIT, **_TO_LETTER}.get(fixed[14])
            if swap:
                candidates.append(fixed[:14] + swap)
    for candidate in candidates:
        if gstin_checksum_ok(candidate):
            return candidate
    return candidates[0] if candidates else ""


def clean_amount(text: str):
    """'Rs.1,23,456.50/-' -> 123456.5 ; None when no number is present."""
    text = re.sub(r"(?i)rs\.?|inr|₹|/-", "", text).replace(",", "").replace(" ", "")
    match = re.search(r"\d+(?:\.\d{1,2})?", text)
    return float(match.group()) if match else None


def clean_rate(text: str):
    match = re.search(r"\d+(?:\.\d+)?", text)
    value = float(match.group()) if match else None
    return value if value is not None and value <= 40 else None


def clean_invoice_no(text: str) -> str:
    """Drops a caption glued on by OCR ('Number:TX/97' or 'Bill No.A12'), keeping prefixes like 'INV-'."""
    text = text.split(":")[-1].strip(" .#-")
    stripped = re.sub(r"(?i)^(invoice|bill|memo|inv\.)?\s*(number|no\.|#)\s*", "", text).strip(" .#-:")
    return stripped or text


def clean_date(text: str) -> str:
    """ISO date when the text parses, otherwise the text as read."""
    compact = re.sub(r"\s+", " ", text.strip(" .:"))
    compact = re.sub(r"(?i)^(invoice|inv|bill)?\s*(dated|date|dt)[.:\s]*(?=\d)", "", compact)
    for candidate in (compact, compact.replace(" ", ""), re.sub(r"(?<=[A-Za-z])(?=\d)", " ", compact)):
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                pass
    return compact


def _best(entities: dict, kind: str, clean=None):
    """Highest-confidence usable entity of a field: (value, confidence), or (None, 0.0)."""
    for entity in sorted(entities.get(kind, []), key=lambda e: -e["confidence"]):
        value = clean(entity["text"]) if clean else entity["text"].strip()
        if value not in (None, ""):
            return value, entity["confidence"]
    return None, 0.0


def extract_fields(image, words: list) -> dict:
    """{"fields": cleaned values, "confidence": per-field score, "entities": raw tagged text}."""
    entities = group_entities(words, tag_words(image, words))
    fields, confidence = {}, {}

    def take(name, kind, clean=None):
        fields[name], confidence[name] = _best(entities, kind, clean)

    take("vendor_name", "VENDOR_NAME")
    take("vendor_gstin", "VENDOR_GSTIN", clean_gstin)
    take("buyer_name", "BUYER_NAME")
    take("buyer_gstin", "BUYER_GSTIN", clean_gstin)
    take("invoice_no", "INVOICE_NO", clean_invoice_no)
    take("invoice_date", "INVOICE_DATE", clean_date)
    take("taxable_value", "TAXABLE_VALUE", clean_amount)
    take("cgst_amount", "CGST_AMOUNT", clean_amount)
    take("sgst_amount", "SGST_AMOUNT", clean_amount)
    take("igst_amount", "IGST_AMOUNT", clean_amount)
    take("total_amount", "TOTAL_AMOUNT", clean_amount)

    def unique(kind, clean=None):
        seen = []
        for entity in entities.get(kind, []):
            value = clean(entity["text"]) if clean else entity["text"].strip()
            if value not in (None, "") and value not in seen:
                seen.append(value)
        return seen

    fields["items"] = unique("ITEM_DESC")
    fields["hsn_codes"] = unique("HSN", lambda t: re.sub(r"\D", "", t))
    rates = {kind: unique(f"{kind}_RATE", clean_rate) for kind in ("CGST", "SGST", "IGST")}
    fields["gst_rates"] = sorted(set(rates["IGST"]) | {2 * r for r in rates["CGST"] or rates["SGST"]})
    return {"fields": fields, "confidence": confidence, "entities": entities}
