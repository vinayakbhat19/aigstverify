"""Field extraction with OpenCV clean-up and a small open-source vision-language model.

No separate OCR step: the model looks at the (cleaned) invoice image and writes
the fields as JSON. Each field gets a confidence from the model's own token
probabilities, so the checks downstream can tell a confident reading from a
guess.

Backends (VLM_BACKEND):
    transformers  (default) runs the Hugging Face model in this process.
                  VLM_MODEL defaults to Qwen/Qwen3-VL-4B-Instruct (Apache-2.0).
                  VLM_DEVICE: mps (Apple GPU), cuda or cpu; picked automatically.
    ollama        sends the image to a local Ollama server (OLLAMA_URL, default
                  http://localhost:11434). VLM_MODEL defaults to qwen3-vl:4b.
                  Quantised, so it is the fastest option on a MacBook.

VLM_MAX_SIDE (default 1280) caps the longest image side in pixels: fewer
pixels means fewer image tokens and a faster read.
"""

import base64
import io
import json
import math
import os
import re
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image

from utils.layout_extractor import clean_amount, clean_date, clean_gstin, clean_invoice_no, clean_rate

BACKEND = os.getenv("VLM_BACKEND", "transformers").lower()
MODEL = os.getenv("VLM_MODEL") or ("qwen3-vl:4b" if BACKEND == "ollama" else "Qwen/Qwen3-VL-4B-Instruct")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
MAX_SIDE = int(os.getenv("VLM_MAX_SIDE", "1280"))
MAX_NEW_TOKENS = int(os.getenv("VLM_MAX_NEW_TOKENS", "900"))

PROMPT = """You are reading an Indian GST tax invoice. Return ONLY a JSON object with exactly these keys:

{
  "vendor_name": "business that issued the invoice (the seller), as printed",
  "vendor_gstin": "seller's 15-character GSTIN, exactly as printed",
  "buyer_name": "customer / bill-to name, or null",
  "buyer_gstin": "buyer's GSTIN, or null",
  "invoice_no": "invoice / bill number (not the order number), as printed",
  "invoice_date": "invoice date, as printed",
  "items": [{"description": "item or service name", "hsn": "HSN/SAC code or null"}],
  "taxable_value": "total value before tax",
  "cgst_rate": "CGST % as printed (e.g. 9), or null",
  "cgst_amount": "total CGST amount, or null",
  "sgst_rate": "SGST/UTGST % as printed, or null",
  "sgst_amount": "total SGST/UTGST amount, or null",
  "igst_rate": "IGST % as printed, or null",
  "igst_amount": "total IGST amount, or null",
  "total_amount": "final amount payable (grand total)"
}

Rules:
- Copy values exactly as printed. Do NOT calculate, correct or fill in any number: if a value is not printed, use null.
- Amounts as plain numbers without commas, currency signs or "/-" (e.g. 12345.50).
- The seller's GSTIN is near the seller's name and address at the top; the buyer's is in the bill-to block.
- If items have different tax rates, give the rate of the first tax line for cgst_rate / sgst_rate / igst_rate.
- If there are several pages of items, list every item.
Return the JSON object only, with no explanation."""


# ----------------------------------------------------------------- OpenCV clean-up

def preprocess(image: Image.Image) -> tuple:
    """(cleaned PIL image, steps applied). Straightens, evens out lighting and limits size."""
    rgb = np.asarray(image.convert("RGB"))
    steps = []

    # Straighten a slightly rotated scan or photo: fit a rotated box to the dark (text) pixels.
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    points = cv2.findNonZero(ink)
    if points is not None and len(points) > 500:
        angle = cv2.minAreaRect(points)[-1]
        angle = angle - 90 if angle > 45 else angle
        if 0.5 < abs(angle) < 15:
            h, w = gray.shape
            matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            rgb = cv2.warpAffine(rgb, matrix, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
            steps.append(f"deskewed {angle:.1f} deg")

    # Even out shadows and faded print with local contrast (CLAHE) on the lightness channel.
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    lightness, a, b = cv2.split(lab)
    if lightness.std() < 60:
        lightness = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lightness)
        rgb = cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2RGB)
        steps.append("contrast evened")

    # Limit size: image tokens grow with pixel count, and reading time with them.
    h, w = rgb.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        rgb = cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
        steps.append(f"resized to {rgb.shape[1]}x{rgb.shape[0]}")
    return Image.fromarray(rgb), steps


# ----------------------------------------------------------------- model backends

@lru_cache(maxsize=1)
def _load_transformers():
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    device = os.getenv("VLM_DEVICE") or (
        "cuda" if torch.cuda.is_available() else
        "mps" if torch.backends.mps.is_available() else "cpu")
    # bfloat16 halves memory (about 9 GB for the 4B model) and does not overflow the way
    # float16 can with Qwen models. VLM_FP32=1 forces full precision if a device lacks bf16.
    dtype = torch.float32 if os.getenv("VLM_FP32") else torch.bfloat16
    processor = AutoProcessor.from_pretrained(MODEL)
    model = AutoModelForImageTextToText.from_pretrained(MODEL, dtype=dtype).to(device).eval()
    print(f"[vlm] loaded {MODEL} on {device} ({dtype})", flush=True)
    return processor, model, device


def _generate_transformers(image: Image.Image) -> tuple:
    """(reply text, [(token text, probability)])."""
    import torch

    processor, model, device = _load_transformers()
    messages = [{"role": "user", "content": [{"type": "image", "image": image},
                                             {"type": "text", "text": PROMPT}]}]
    inputs = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                           return_dict=True, return_tensors="pt").to(device)
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                             output_scores=True, return_dict_in_generate=True)
    new_ids = out.sequences[0, inputs["input_ids"].shape[1]:].tolist()
    tokens = []
    for token_id, scores in zip(new_ids, out.scores):
        probability = torch.softmax(scores[0].float(), dim=-1)[token_id].item()
        tokens.append((processor.tokenizer.decode([token_id]), probability))
    text = processor.tokenizer.decode(new_ids, skip_special_tokens=True)
    return text, tokens


def _generate_ollama(image: Image.Image) -> tuple:
    import requests

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    body = {"model": MODEL, "stream": False, "think": False, "format": "json", "logprobs": True,
            "options": {"temperature": 0, "num_predict": MAX_NEW_TOKENS},
            "messages": [{"role": "user", "content": PROMPT,
                          "images": [base64.b64encode(buffer.getvalue()).decode()]}]}
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=600)
    response.raise_for_status()
    reply = response.json()
    tokens = [(t.get("token", ""), math.exp(t.get("logprob", 0.0))) for t in reply.get("logprobs") or []]
    return reply["message"]["content"], tokens


def check_ready() -> str:
    """"" when the backend can run, otherwise what to do about it."""
    if BACKEND == "ollama":
        import requests

        try:
            names = [m.get("name", "") for m in requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).json().get("models", [])]
        except requests.RequestException:
            return f"Ollama is not running at {OLLAMA_URL}: start the Ollama app, then run: ollama pull {MODEL}"
        if not any(name == MODEL or name.split(":")[0] == MODEL for name in names):
            return f"The model is not in Ollama yet: run: ollama pull {MODEL}"
        return ""
    if os.path.isdir(MODEL):
        return ""
    from huggingface_hub import try_to_load_from_cache

    if not isinstance(try_to_load_from_cache(MODEL, "config.json"), str):
        return (f"{MODEL} is not downloaded yet (about 9 GB): run "
                f"python -c \"from huggingface_hub import snapshot_download; snapshot_download('{MODEL}')\"")
    return ""


# ----------------------------------------------------------------- JSON and confidence

def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("the model did not return JSON")
    return json.loads(text[start:end + 1])


def _value_confidence(tokens: list) -> dict:
    """Lowest token probability inside each top-level value of the JSON reply.

    The lowest, not the average: one uncertain digit makes the whole amount uncertain.
    Returns {} when the backend gave no token probabilities.
    """
    if not tokens:
        return {}
    spans, offset = [], 0
    for token, probability in tokens:
        spans.append((offset, offset + len(token), probability))
        offset += len(token)
    joined = "".join(t for t, _ in tokens)
    confidence = {}
    for match in re.finditer(r'"(\w+)"\s*:\s*("(?:[^"\\]|\\.)*"|-?[\d.]+|null|true|false|\[[^\]]*\])', joined):
        key, (start, end) = match.group(1), match.span(2)
        inside = [p for s, e, p in spans if s < end and e > start]
        if inside and key not in confidence:
            confidence[key] = min(inside)
    return confidence


def _gstin(value):
    """Repaired GSTIN, or the text as read when it cannot be repaired (the checks then report it)."""
    text = re.sub(r"[^A-Z0-9]", "", _text(value).upper())
    if not text or text in ("NULL", "NONE"):
        return None
    return clean_gstin(text) or text


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def extract_fields(image: Image.Image) -> dict:
    """{"fields", "confidence", "raw", "preprocessing"} in the same shape as the LayoutLMv3 extractor."""
    cleaned, steps = preprocess(image)
    raw, tokens = (_generate_ollama if BACKEND == "ollama" else _generate_transformers)(cleaned)
    data = _parse_json(raw)
    token_conf = _value_confidence(tokens)

    def amount(key):
        value = data.get(key)
        return clean_amount(_text(value)) if _text(value) not in ("", "null", "None") else None

    items = data.get("items") or []
    items = [item for item in items if isinstance(item, dict)]
    fields = {
        "vendor_name": _text(data.get("vendor_name")) or None,
        "vendor_gstin": _gstin(data.get("vendor_gstin")),
        "buyer_name": _text(data.get("buyer_name")) or None,
        "buyer_gstin": _gstin(data.get("buyer_gstin")),
        "invoice_no": clean_invoice_no(_text(data.get("invoice_no"))) or None,
        "invoice_date": clean_date(_text(data.get("invoice_date"))) or None,
        "taxable_value": amount("taxable_value"),
        "cgst_amount": amount("cgst_amount"),
        "sgst_amount": amount("sgst_amount"),
        "igst_amount": amount("igst_amount"),
        "total_amount": amount("total_amount"),
        "items": [_text(item.get("description")) for item in items if _text(item.get("description"))],
        "hsn_codes": [re.sub(r"\D", "", _text(item.get("hsn"))) for item in items
                      if re.sub(r"\D", "", _text(item.get("hsn")))],
    }
    # Intra-state invoices print CGST and SGST halves; the GST rate is their sum.
    half = [clean_rate(_text(data.get(key))) for key in ("cgst_rate", "sgst_rate")]
    half = [rate for rate in half if rate is not None]
    igst = clean_rate(_text(data.get("igst_rate")))
    rates = set()
    if half:
        rates.add(sum(half) if len(half) == 2 else 2 * half[0])
    if igst is not None and fields["igst_amount"]:
        rates.add(igst)
    fields["gst_rates"] = sorted(rates)

    # Without token probabilities (some Ollama versions) every value counts as read confidently.
    default = 1.0 if not token_conf else 0.0
    confidence = {key: (round(token_conf.get(key, default), 3) if fields.get(key) is not None else 0.0)
                  for key in ("vendor_name", "vendor_gstin", "buyer_name", "buyer_gstin", "invoice_no",
                              "invoice_date", "taxable_value", "cgst_amount", "sgst_amount",
                              "igst_amount", "total_amount")}
    return {"fields": fields, "confidence": confidence, "raw": raw, "preprocessing": steps}
