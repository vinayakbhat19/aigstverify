"""Generate a synthetic Indian GST invoice dataset for LayoutLMv3-style token classification.

    python scripts/generate_invoices.py --count 300 --output data/synthetic

Each invoice gets an image and a JSON annotation holding its words, their boxes
(normalised to 0-1000), IOB2 labels and the ground-truth field values. The same
seed always produces the same dataset. See data/README.md for the format.
"""

import argparse
import json
import random
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datagen import ENTITY_TYPES, LABELS  # noqa: E402
from datagen.augment import degrade  # noqa: E402
from datagen.content import build_invoice, ground_truth  # noqa: E402
from datagen.gst import is_valid_gstin  # noqa: E402
from datagen.render import Renderer  # noqa: E402
from datagen.style import TEMPLATES, make_style  # noqa: E402


def entities(words, labels):
    """[(entity type, joined text)] for each B-/I- run."""
    found = []
    for word, label in zip(words, labels):
        if label.startswith("B-"):
            found.append([label[2:], word])
        elif label.startswith("I-") and found:
            found[-1][1] += " " + word
    return [(kind, text) for kind, text in found]


def as_number(text: str) -> Decimal:
    return Decimal(re.sub(r"[^0-9.]", "", text.replace("Rs.", "").replace("/-", "")) or "0")


def check(record: dict) -> list:
    """Cross-checks an annotation against its ground truth. Returns a list of problems."""
    problems = []
    fields, width, height = record["fields"], record["width"], record["height"]
    if not (len(record["words"]) == len(record["bboxes"]) == len(record["labels"]) == len(record["bboxes_px"])):
        problems.append("length mismatch")
    for box, px in zip(record["bboxes"], record["bboxes_px"]):
        if not (0 <= box[0] <= box[2] <= 1000 and 0 <= box[1] <= box[3] <= 1000):
            problems.append(f"box out of range {box}")
        if not (0 <= px[0] < px[2] <= width and 0 <= px[1] < px[3] <= height):
            problems.append(f"pixel box out of image {px}")
    found = entities(record["words"], record["labels"])
    by_kind = {}
    for kind, text in found:
        by_kind.setdefault(kind, []).append(text)

    for kind, key in (("VENDOR_GSTIN", "vendor_gstin"), ("BUYER_GSTIN", "buyer_gstin"),
                      ("INVOICE_NO", "invoice_no"), ("INVOICE_DATE", "invoice_date_text")):
        for text in by_kind.get(kind, []):
            if text != fields[key]:
                problems.append(f"{kind}: printed {text!r}, expected {fields[key]!r}")
    for kind in ("VENDOR_GSTIN", "INVOICE_NO", "INVOICE_DATE", "TOTAL_AMOUNT", "TAXABLE_VALUE", "VENDOR_NAME"):
        if kind not in by_kind:
            problems.append(f"{kind} missing")
    if bool(fields["buyer_gstin"]) != ("BUYER_GSTIN" in by_kind):
        problems.append("BUYER_GSTIN presence mismatch")
    for gstin in by_kind.get("VENDOR_GSTIN", []) + by_kind.get("BUYER_GSTIN", []):
        if not is_valid_gstin(gstin):
            problems.append(f"bad GSTIN checksum {gstin}")
    for kind, key in (("TOTAL_AMOUNT", "total_amount"), ("TAXABLE_VALUE", "taxable_value"),
                      ("CGST_AMOUNT", "cgst_amount"), ("SGST_AMOUNT", "sgst_amount"),
                      ("IGST_AMOUNT", "igst_amount")):
        for text in by_kind.get(kind, []):
            if as_number(text) != Decimal(str(fields[key])).quantize(Decimal("0.01")):
                problems.append(f"{kind}: printed {text!r}, expected {fields[key]}")
    intra = fields["supply_type"] == "intra-state"
    if intra != ("CGST_AMOUNT" in by_kind) or intra == ("IGST_AMOUNT" in by_kind):
        problems.append("tax type does not match supply type")
    # Vendor/buyer names may wrap across lines, so compare the words only.
    for kind, key in (("VENDOR_NAME", "vendor_name"), ("BUYER_NAME", "buyer_name")):
        printed = " ".join(by_kind.get(kind, [])).upper().split()
        if any(word not in fields[key].upper().split() for word in printed):
            problems.append(f"{kind}: unexpected words {printed}")
    expected_items = sorted(item["description"] for item in fields["items"])
    if "ITEM_DESC" in by_kind and len(by_kind["ITEM_DESC"]) == len(expected_items):
        if sorted(by_kind["ITEM_DESC"]) != expected_items:
            problems.append("ITEM_DESC text mismatch")
    total = Decimal(str(fields["taxable_value"])) + Decimal(str(fields["gst_amount"])) + Decimal(str(fields["round_off"]))
    if abs(total - Decimal(str(fields["total_amount"]))) > Decimal("0.005"):
        problems.append("total does not add up")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--output", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--clean-fraction", type=float, default=0.35,
                        help="share of invoices kept as clean renders (the rest are degraded)")
    parser.add_argument("--holdout-template", default="columnar", choices=list(TEMPLATES) + ["none"],
                        help="layout that appears only in the test split")
    args = parser.parse_args()

    out = args.output
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "annotations").mkdir(parents=True, exist_ok=True)
    for stale in list((out / "images").glob("invoice_*")) + list((out / "annotations").glob("invoice_*")):
        stale.unlink()

    master = random.Random(args.seed)
    names = list(TEMPLATES)
    plan = master.choices(names, weights=[TEMPLATES[n][0] for n in names], k=args.count)

    # Held-out layout goes to test; everything else is split 85/10/5.
    rest = [i for i, name in enumerate(plan) if name != args.holdout_template]
    master.shuffle(rest)
    n_val, n_test = round(len(rest) * 0.10), round(len(rest) * 0.05)
    split = {i: "test" for i in range(args.count)}
    split.update({i: "val" for i in rest[:n_val]})
    split.update({i: "train" for i in rest[n_val + n_test:]})

    renderer = Renderer()
    records, failures = [], 0
    try:
        for i, template in enumerate(plan):
            rng = random.Random(f"{args.seed}:{i}")
            _, categories, b2b_share = TEMPLATES[template]
            inv = build_invoice(rng, rng.choice(categories), rng.random() < b2b_share)
            S, L, m, r = make_style(rng, template, inv)
            png, words = renderer.render(template, inv, S, L, m, r)

            boxes = [w["box"] for w in words]
            if rng.random() < args.clean_fraction:
                import cv2
                import numpy as np
                shape = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR).shape
                data, ext, steps, (width, height) = png, "png", [], (shape[1], shape[0])
            else:
                data, ext, boxes, steps, (width, height) = degrade(png, boxes, rng)

            name = f"invoice_{i + 1:04d}"
            (out / "images" / f"{name}.{ext}").write_bytes(data)
            px = [[round(v, 1) for v in box] for box in boxes]
            record = {
                "id": name,
                "image": f"images/{name}.{ext}",
                "width": width,
                "height": height,
                "split": split[i],
                "words": [w["text"] for w in words],
                "bboxes": [[min(1000, max(0, int(round(1000 * b[0] / width)))),
                            min(1000, max(0, int(round(1000 * b[1] / height)))),
                            min(1000, max(0, int(round(1000 * b[2] / width)))),
                            min(1000, max(0, int(round(1000 * b[3] / height))))] for b in boxes],
                "bboxes_px": px,
                "labels": [w["label"] for w in words],
                "fields": ground_truth(inv),
                "meta": {"template": template, "b2b": inv["b2b"], "degradations": steps,
                         "font": S["font"].split("'")[1], "seed": f"{args.seed}:{i}"},
            }
            problems = check(record)
            if problems:
                failures += 1
                print(f"{name} ({template}): " + "; ".join(problems[:4]), file=sys.stderr)
            (out / "annotations" / f"{name}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
            records.append(record)
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{args.count}")
    finally:
        renderer.close()

    for part in ("train", "val", "test"):
        with open(out / f"{part}.jsonl", "w", encoding="utf-8") as fh:
            for record in records:
                if record["split"] == part:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    (out / "labels.json").write_text(json.dumps(LABELS, indent=1), encoding="utf-8")

    tags = Counter(label[2:] for rec in records for label in rec["labels"] if label.startswith("B-"))
    info = {
        "count": len(records),
        "seed": args.seed,
        "splits": dict(Counter(rec["split"] for rec in records)),
        "templates": dict(Counter(rec["meta"]["template"] for rec in records)),
        "holdout_template": args.holdout_template,
        "categories": dict(Counter(rec["fields"]["category"] for rec in records)),
        "supply_type": dict(Counter(rec["fields"]["supply_type"] for rec in records)),
        "clean_images": sum(1 for rec in records if not rec["meta"]["degradations"]),
        "words": sum(len(rec["words"]) for rec in records),
        "entities": {kind: tags.get(kind, 0) for kind in ENTITY_TYPES},
    }
    (out / "dataset_info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info, indent=1))
    print(f"\nWrote {len(records)} invoices to {out}/ ({failures} failed self-checks)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
