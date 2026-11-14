"""OCR with PaddleOCR models. Returns text together with word boxes.

Two backends, chosen with the OCR_BACKEND environment variable:

* "onnx" (default): PP-OCR models run on ONNX Runtime through the
  rapidocr-onnxruntime package. The detector ships inside the package; the
  English recognition model (9 MB) is fetched from Hugging Face once and cached,
  after which it works offline. Roughly 1-2 seconds per invoice on a 4-core CPU.
* "paddle": the native paddleocr package (pip install paddlepaddle paddleocr).
  Downloads PP-OCRv5 models on first use. Keeps spaces between words better,
  but took 5-10 seconds per invoice on the same CPU.
"""

import os
import re
import warnings
from functools import lru_cache

import numpy as np

BACKEND = os.getenv("OCR_BACKEND", "onnx").lower()
ENGLISH_REC_MODEL = ("SWHL/RapidOCR", "PP-OCRv3/en_PP-OCRv3_rec_infer.onnx")

# OCR often drops the space after a caption's colon ("Invoice No:INV-12").
_GLUED_COLON = re.compile(r"(?<=[A-Za-z.]):(?=[^\s:/])")


@lru_cache(maxsize=1)
def _onnx_engine():
    from rapidocr_onnxruntime import RapidOCR

    try:
        from huggingface_hub import hf_hub_download

        # The packaged recogniser is Chinese-first and drops spaces in English text.
        return RapidOCR(rec_model_path=hf_hub_download(*ENGLISH_REC_MODEL))
    except Exception as error:  # offline on first run, or huggingface_hub missing
        warnings.warn(f"English OCR model unavailable ({error}); using the packaged model, "
                      "which merges adjacent English words.")
        return RapidOCR()


@lru_cache(maxsize=1)
def _paddle_engine():
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import PaddleOCR

    return PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="en_PP-OCRv5_mobile_rec",
        # oneDNN crashes on these models in paddlepaddle 3.3 (unsupported attribute type).
        enable_mkldnn=False,
    )


def _to_rgb_array(image) -> np.ndarray:
    """Accepts a PIL image, a numpy array or a file path."""
    if isinstance(image, (str, os.PathLike)):
        from PIL import Image

        image = Image.open(image)
    if not isinstance(image, np.ndarray):
        image = np.array(image.convert("RGB"))
    return image


def extract_lines(image) -> list:
    """Text lines as {"text", "box": [x0, y0, x1, y1], "score"}, in reading order."""
    rgb = _to_rgb_array(image)
    bgr = np.ascontiguousarray(rgb[:, :, ::-1])
    lines = []
    if BACKEND == "paddle":
        result = _paddle_engine().predict(bgr)[0]
        for text, score, poly in zip(result["rec_texts"], result["rec_scores"], result["rec_polys"]):
            poly = np.asarray(poly, dtype=float)
            lines.append({"text": text, "score": float(score),
                          "box": [*poly.min(axis=0).tolist(), *poly.max(axis=0).tolist()]})
    else:
        result, _ = _onnx_engine()(bgr)
        for poly, text, score in result or []:
            poly = np.asarray(poly, dtype=float)
            lines.append({"text": text, "score": float(score),
                          "box": [*poly.min(axis=0).tolist(), *poly.max(axis=0).tolist()]})
    lines = [line for line in lines if line["text"].strip()]
    return _reading_order(lines)


def _reading_order(lines: list) -> list:
    """Top to bottom, then left to right within a row of boxes at the same height."""
    rows = []
    for line in sorted(lines, key=lambda l: ((l["box"][1] + l["box"][3]) / 2, l["box"][0])):
        centre = (line["box"][1] + line["box"][3]) / 2
        height = line["box"][3] - line["box"][1]
        if rows and abs(centre - rows[-1]["centre"]) < 0.5 * min(height, rows[-1]["height"]):
            rows[-1]["lines"].append(line)
        else:
            rows.append({"centre": centre, "height": height, "lines": [line]})
    return [line for row in rows for line in sorted(row["lines"], key=lambda l: l["box"][0])]


def split_words(lines: list) -> list:
    """Splits each line into words; a word's box is its share of the line by character count."""
    words = []
    for line in lines:
        text = line["text"]
        x0, y0, x1, y1 = line["box"]
        per_char = (x1 - x0) / max(len(text), 1)
        position = 0
        for word in _GLUED_COLON.sub(": ", text).split():
            start = text.index(word, position)
            position = start + len(word)
            words.append({"text": word, "score": line["score"],
                          "box": [x0 + start * per_char, y0, x0 + position * per_char, y1]})
    return words


def extract_words(image) -> list:
    """Words as {"text", "box", "score"} in reading order: the input a layout model needs."""
    return split_words(extract_lines(image))


def extract_text(image) -> str:
    """Plain text, one detected line per row."""
    return "\n".join(line["text"] for line in extract_lines(image))
