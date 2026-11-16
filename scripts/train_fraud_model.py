"""Train the fraud model on generated genuine and fraudulent invoices.

Genuine invoices come from the same generator as the LayoutLMv3 dataset, so
amounts, rates and GSTINs are realistic. Each one is then put through the
kinds of noise real extraction has (fields not read, a misread digit, checks
that could not run). Fraudulent invoices are genuine ones with one or two
known fraud patterns applied:

    fake GSTIN (bad check character)   malformed GSTIN
    cancelled / not-found registration  name differs from registry
    inflated tax                         total that does not add up
    wrong rate for the goods             duplicate invoice
    QR code edited out of step           impossible date
    fabricated round-number invoice

The labels come from these simulated patterns, not from real fraud cases, so
the model learns how strongly each signal (and each combination) should count,
including that some signals also appear on genuine invoices through OCR errors.
Retrain with real labelled cases when you have them.

    python scripts/train_fraud_model.py --count 20000
"""

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datagen import gst as gstdata  # noqa: E402
from datagen.content import build_invoice, ground_truth  # noqa: E402
from utils.fraud import FEATURES, MODEL_PATH, build_features, to_matrix  # noqa: E402
from utils.validator import validate_gstin  # noqa: E402

TODAY = date(2026, 11, 16)
FRAUD_TYPES = ["fake_gstin", "malformed_gstin", "registry_inactive", "name_mismatch",
               "inflated_tax", "tampered_total", "wrong_rate", "duplicate", "qr_mismatch",
               "bad_date", "round_fabricated"]


def genuine(rng) -> dict:
    inv = ground_truth(build_invoice(rng, rng.choice(list(gstdata.CATALOGUE)), rng.random() < 0.7))
    rates = set(inv["gst_rates"])
    return {
        "gstin": inv["vendor_gstin"],
        "taxable": inv["taxable_value"], "gst": inv["gst_amount"], "total": inv["total_amount"],
        "date": inv["invoice_date"],
        # Rate check: single-rate invoices with a known category usually pass; the
        # table cannot judge mixed-rate invoices or unknown categories.
        "rate_state": rng.choices(["pass", "skip", "fail"], [0.55, 0.42, 0.03])[0] if len(rates) == 1
        else rng.choices(["skip", "pass"], [0.85, 0.15])[0],
        "registry_state": rng.choices(["skip", "pass"], [0.6, 0.4])[0],
        "name_match": None,
        "duplicate": rng.random() < 0.005,  # the same genuine bill uploaded twice
        "qr_state": rng.choices(["skip", "pass"], [0.75, 0.25])[0],
    }


def apply_fraud(rng, row: dict, kind: str) -> None:
    if kind == "fake_gstin":
        good = row["gstin"]
        if len(good) != 15:  # an earlier pattern already broke the GSTIN
            return
        row["gstin"] = good[:14] + rng.choice([c for c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c != good[14]])
        row["registry_state"] = "skip"
    elif kind == "malformed_gstin":
        if len(row["gstin"]) != 15:
            return
        g = list(row["gstin"])
        g[rng.choice([0, 2, 7, 13])] = rng.choice("XQ7#")
        row["gstin"] = "".join(g)[: rng.choice([13, 14, 15])]
        row["registry_state"] = "skip"
    elif kind == "no_gstin":
        row["gstin"], row["registry_state"] = "", "skip"
    elif kind == "registry_inactive":
        row["registry_state"] = "fail"
    elif kind == "name_mismatch":
        row["registry_state"], row["name_match"] = "pass", False
    elif kind == "inflated_tax":
        row["gst"] = round(row["gst"] * rng.uniform(1.3, 2.5) + rng.uniform(10, 500), 2)
        row["total"] = round(row["taxable"] + row["gst"])
        row["rate_state"] = rng.choices(["skip", "fail"], [0.6, 0.4])[0]
    elif kind == "tampered_total":
        row["total"] = round(row["total"] * rng.uniform(1.04, 1.8))
    elif kind == "wrong_rate":
        row["rate_state"] = "fail"
    elif kind == "duplicate":
        row["duplicate"] = True
    elif kind == "qr_mismatch":
        row["qr_state"] = "fail"
    elif kind == "bad_date":
        row["date"] = (TODAY + timedelta(days=rng.randint(5, 400))).isoformat() if rng.random() < 0.6 \
            else date(rng.randint(2012, 2016), rng.randint(1, 12), rng.randint(1, 28)).isoformat()
    elif kind == "round_fabricated":
        row["total"] = float(rng.choice(range(5000, 200001, 1000)))
        rate = rng.choice([5, 12, 18, 28])
        row["taxable"] = round(row["total"] / (1 + rate / 100), 2)
        row["gst"] = round(row["total"] - row["taxable"], 2)
        row["rate_state"] = rng.choices(["skip", "fail", "pass"], [0.4, 0.4, 0.2])[0]


def extraction_noise(rng, row: dict) -> None:
    """What a real OCR + model pass does to the values it reads."""
    for key, p in (("taxable", 0.15), ("gst", 0.15), ("total", 0.05)):
        if rng.random() < p:
            row[key] = 0.0
    if rng.random() < 0.04 and row["total"]:  # one digit misread
        row["total"] = round(row["total"] * rng.choice([0.1, 10, 1.1, 0.9, 1.01]), 2)
    if rng.random() < 0.03:
        row["gstin"] = ""
    if rng.random() < 0.08:
        row["date"] = ""
    if row["gstin"] and rng.random() < 0.08:
        # GSTIN misread by the extractor (a character changed or dropped) and flagged
        # as uncertain, so the checks cannot use it; happens to any invoice.
        g, i = row["gstin"], rng.randrange(len(row["gstin"]))
        row["gstin"] = g[:i] + g[i + 1:] if rng.random() < 0.4 else g[:i] + rng.choice("0O1IZ2S5B8") + g[i + 1:]
        row["gstin_uncertain"] = True
    if row["registry_state"] == "pass" and row["name_match"] is None and rng.random() < 0.5:
        # Registered legal names often differ from the trade name on the bill.
        row["name_match"] = rng.random() < 0.9


def features_of(row: dict) -> dict:
    gstin_check = validate_gstin(row["gstin"])
    if row.get("gstin_uncertain") and not gstin_check["valid"]:
        gstin_check = {**gstin_check, "uncertain": True}
    taxable, gst, total = row["taxable"], row["gst"], row["total"]
    return build_features(gstin_check=gstin_check, registry={"state": row["registry_state"]},
                          rate_check={"state": row["rate_state"]}, taxable=taxable, gst=gst, total=total,
                          duplicate=row["duplicate"], qr_check={"state": row["qr_state"]},
                          invoice_date=row["date"], name_match=row["name_match"], today=TODAY)


def make_dataset(count: int, seed: int):
    rng = random.Random(seed)
    rows, labels, kinds = [], [], []
    for _ in range(count):
        row = genuine(rng)
        fraud = rng.random() < 0.5
        applied = []
        if fraud:
            applied = rng.sample(FRAUD_TYPES, 2 if rng.random() < 0.3 else 1)
            for kind in applied:
                apply_fraud(rng, row, kind)
        extraction_noise(rng, row)
        rows.append(features_of(row))
        labels.append(int(fraud))
        kinds.append("+".join(applied) or "genuine")
    return to_matrix(rows), np.array(labels), kinds


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    import xgboost as xgb
    from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

    X, y, kinds = make_dataset(args.count, args.seed)
    split = int(len(y) * 0.8)
    model = xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.9,
                              colsample_bytree=0.9, eval_metric="logloss", random_state=args.seed)
    model.fit(X[:split], y[:split])

    p = model.predict_proba(X[split:])[:, 1]
    predicted = (p >= 0.5).astype(int)
    truth, test_kinds = y[split:], kinds[split:]
    per_kind = {}
    for kind in ["genuine"] + FRAUD_TYPES:
        idx = [i for i, k in enumerate(test_kinds) if k.split("+")[0] == kind]
        if idx:
            hit = predicted[idx] == truth[idx]
            per_kind[kind] = {"cases": len(idx), "correct": round(float(hit.mean()), 3)}
    metrics = {
        "train_rows": split, "test_rows": len(truth),
        "roc_auc": round(float(roc_auc_score(truth, p)), 4),
        "precision": round(float(precision_score(truth, predicted)), 4),
        "recall": round(float(recall_score(truth, predicted)), 4),
        "f1": round(float(f1_score(truth, predicted)), 4),
        "by_case": per_kind,
        "features": FEATURES,
    }
    MODEL_PATH.parent.mkdir(exist_ok=True)
    model.save_model(MODEL_PATH)
    MODEL_PATH.with_name("fraud_model_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps({k: v for k, v in metrics.items() if k != "features"}, indent=2))
    print(f"Saved {MODEL_PATH}")


if __name__ == "__main__":
    main()
