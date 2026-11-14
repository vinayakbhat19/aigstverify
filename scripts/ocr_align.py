"""Re-OCR the synthetic invoices and carry the labels over to the OCR words.

    python scripts/ocr_align.py --input data/synthetic --output data/synthetic_ocr

The generator's word boxes are exact, but at inference the model sees OCR
output: different word splits, merged words and misread characters. This
script runs the same OCR the app uses on every image, then labels each OCR
word with the entity of the ground-truth word it overlaps most. Train on the
result so training matches inference. Images are not copied; records point at
the originals.
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.ocr import extract_words  # noqa: E402


def entity_ids(labels: list) -> list:
    """Entity index per word (-1 for O), from IOB2 labels."""
    ids, current = [], -1
    for i, label in enumerate(labels):
        if label == "O":
            ids.append(-1)
        else:
            if label.startswith("B-") or i == 0 or ids[-1] == -1 or labels[i - 1][2:] != label[2:]:
                current += 1
            ids.append(current)
    return ids


def overlap(a, b) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def align(record: dict, ocr_words: list, min_cover: float = 0.5):
    """Labels for the OCR words, plus how many ground-truth entities were found again."""
    truth_boxes, truth_labels = record["bboxes_px"], record["labels"]
    truth_entities = entity_ids(truth_labels)
    assigned = []  # (entity type, entity id) or None per OCR word
    for word in ocr_words:
        box = word["box"]
        area = max((box[2] - box[0]) * (box[3] - box[1]), 1e-6)
        cover = Counter()
        for truth_box, label, entity in zip(truth_boxes, truth_labels, truth_entities):
            shared = overlap(box, truth_box)
            if shared > 0:
                cover[(label[2:], entity) if entity >= 0 else None] += shared / area
        best = max(cover.items(), key=lambda kv: kv[1], default=(None, 0.0))
        assigned.append(best[0] if best[0] is not None and best[1] >= min_cover else None)

    labels, previous = [], None
    for tag in assigned:
        if tag is None:
            labels.append("O")
        else:
            labels.append(("I-" if tag == previous else "B-") + tag[0])
        previous = tag
    recovered = {tag[1] for tag in assigned if tag is not None}
    total = {entity for entity in truth_entities if entity >= 0}
    return labels, len(recovered), len(total)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--output", type=Path, default=Path("data/synthetic_ocr"))
    parser.add_argument("--limit", type=int, default=0, help="only process the first N invoices")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    paths = sorted((args.input / "annotations").glob("*.json"))
    if args.limit:
        paths = paths[: args.limit]
    out = {part: open(args.output / f"{part}.jsonl", "w", encoding="utf-8") for part in ("train", "val", "test")}
    found = total = words = 0
    exact = Counter()
    seconds = []
    for n, path in enumerate(paths, 1):
        record = json.loads(path.read_text(encoding="utf-8"))
        image_path = args.input / record["image"]
        started = time.perf_counter()
        ocr_words = extract_words(image_path)
        seconds.append(time.perf_counter() - started)
        labels, hit, count = align(record, ocr_words)
        found, total, words = found + hit, total + count, words + len(ocr_words)

        # How often does OCR read a key field exactly right?
        text_of = {}
        for word, label in zip(ocr_words, labels):
            if label != "O":
                text_of.setdefault(label[2:], []).append(word["text"])
        for kind, key in (("VENDOR_GSTIN", "vendor_gstin"), ("INVOICE_NO", "invoice_no")):
            exact[kind + "_seen"] += 1
            exact[kind] += record["fields"][key] in " ".join(text_of.get(kind, []))

        width, height = record["width"], record["height"]
        aligned = {
            "id": record["id"],
            "image": str(Path("..") / args.input.name / record["image"]),
            "width": width, "height": height, "split": record["split"],
            "words": [w["text"] for w in ocr_words],
            "bboxes": [[min(1000, max(0, round(1000 * w["box"][0] / width))),
                        min(1000, max(0, round(1000 * w["box"][1] / height))),
                        min(1000, max(0, round(1000 * w["box"][2] / width))),
                        min(1000, max(0, round(1000 * w["box"][3] / height)))] for w in ocr_words],
            "ocr_scores": [round(w["score"], 3) for w in ocr_words],
            "labels": labels,
            "fields": record["fields"],
            "meta": record["meta"],
        }
        out[record["split"]].write(json.dumps(aligned, ensure_ascii=False) + "\n")
        if n % 25 == 0:
            print(f"  {n}/{len(paths)}", flush=True)
    for handle in out.values():
        handle.close()

    seconds.sort()
    info = {
        "invoices": len(paths),
        "ocr_words": words,
        "entities_recovered": round(found / max(total, 1), 4),
        "vendor_gstin_read_exactly": round(exact["VENDOR_GSTIN"] / max(exact["VENDOR_GSTIN_seen"], 1), 4),
        "invoice_no_read_exactly": round(exact["INVOICE_NO"] / max(exact["INVOICE_NO_seen"], 1), 4),
        "ocr_seconds_median": round(seconds[len(seconds) // 2], 2),
        "ocr_seconds_p95": round(seconds[int(len(seconds) * 0.95) - 1], 2),
    }
    (args.output / "alignment_info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    labels_file = args.input / "labels.json"
    if labels_file.exists():
        (args.output / "labels.json").write_text(labels_file.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
