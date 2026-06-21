import sys
from pathlib import Path
from PIL import Image

# Ensure project root is on sys.path so `utils` imports work
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.ocr import extract_text
from utils.llm_extractor import extract_invoice_llm


def main(image_path):
    img = Image.open(image_path)

    print(f"Opening image: {image_path}\n")

    text = extract_text(img)

    print("\n--- OCR TEXT END ---\n")

    data = extract_invoice_llm(text, image=img)

    print("\n=== EXTRACTED DATA ===\n")

    import json

    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_extraction.py <image-path>")
        sys.exit(1)
    main(sys.argv[1])
