"""Run one invoice through OCR and the layout model outside the web app, with timings.

    python scripts/check_invoice.py path/to/invoice.jpg

If a step hangs, after 120 seconds this prints where every thread is stuck.
"""

import faulthandler
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
faulthandler.dump_traceback_later(120, exit=False)


def step(name, started):
    print(f"  {name}: {time.perf_counter() - started:.1f}s", flush=True)
    return time.perf_counter()


def main(path):
    t = time.perf_counter()
    from PIL import Image
    image = Image.open(path).convert("RGB")
    print(f"image {image.size[0]}x{image.size[1]}", flush=True)

    from utils.ocr import extract_lines, split_words
    t = step("import OCR", t)
    lines = extract_lines(image)
    t = step(f"OCR ({len(lines)} lines)", t)

    from utils import layout_extractor
    if not layout_extractor.model_available():
        sys.exit(f"No model in {layout_extractor.MODEL_DIR}")
    layout_extractor._load()
    t = step("load layout model", t)
    words = split_words(lines)
    result = layout_extractor.extract_fields(image, words)
    t = step(f"layout model ({len(words)} words)", t)

    from utils.pipeline import review
    print("\nfields:", json.dumps(result["fields"], indent=1, ensure_ascii=False, default=str))
    print("confidence:", {k: round(v, 2) for k, v in result["confidence"].items()})
    print("would fall back to Gemini because:", review(result) or "no, accepted locally")
    faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
