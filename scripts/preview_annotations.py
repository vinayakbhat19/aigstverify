"""Draw the labelled word boxes on an invoice image, to eyeball annotation quality.

    python scripts/preview_annotations.py data/synthetic/annotations/invoice_0001.json out.png
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

COLOURS = ["#e11d48", "#2563eb", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#be185d", "#65a30d"]


def main(annotation_path: str, out_path: str):
    path = Path(annotation_path)
    record = json.loads(path.read_text(encoding="utf-8"))
    image = Image.open(path.parent.parent / record["image"]).convert("RGB")
    draw = ImageDraw.Draw(image)
    kinds = sorted({label[2:] for label in record["labels"] if label != "O"})
    for box, label in zip(record["bboxes_px"], record["labels"]):
        if label == "O":
            draw.rectangle(box, outline="#bbbbbb")
        else:
            colour = COLOURS[kinds.index(label[2:]) % len(COLOURS)]
            draw.rectangle(box, outline=colour, width=2)
            if label.startswith("B-"):
                draw.text((box[0], box[1] - 11), label[2:], fill=colour)
    image.save(out_path)
    print(f"{out_path}: {len(record['words'])} words, {len(kinds)} entity types")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
