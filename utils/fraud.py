"""Fraud scoring: turns the results of the invoice checks into a risk score.

The score comes from an XGBoost model (models/fraud_model.json) trained by
scripts/train_fraud_model.py on generated genuine and fraudulent invoices.
There are no hand-set multipliers: the model's probability is the score, and
the reasons shown are the features that pushed that particular score up, read
from the model's own per-feature contributions (SHAP values).

build_features() is shared by training and scoring, so both always describe an
invoice the same way. Unknown values are NaN, which XGBoost handles natively:
a check that could not run is not counted for or against the invoice.
"""

import math
from datetime import date
from pathlib import Path

import numpy as np

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "fraud_model.json"
SLABS = (0, 0.25, 3, 5, 12, 18, 28, 40)
GST_START = date(2017, 7, 1)

FEATURES = [
    "gstin_missing", "gstin_bad_format", "gstin_bad_checksum",
    "registry_inactive", "registry_name_mismatch",
    "rate_mismatch", "total_gap_ratio", "tax_share", "off_slab",
    "log_total", "duplicate", "qr_mismatch", "future_date", "pre_gst_date", "round_total",
]

# What each feature means when it raises the score, for the report.
EXPLAIN = {
    "gstin_missing": "No GSTIN on the invoice",
    "gstin_bad_format": "GSTIN does not have a valid pattern",
    "gstin_bad_checksum": "GSTIN check character is wrong (mistyped or made up)",
    "registry_inactive": "GST registry says this GSTIN is not active",
    "registry_name_mismatch": "Vendor name differs from the registered name",
    "rate_mismatch": "GST rate is wrong for this category",
    "total_gap_ratio": "Taxable value + GST does not equal the total",
    "tax_share": "Tax is an unusual share of the total",
    "off_slab": "Tax amount does not match any GST slab",
    "log_total": "Invoice amount is unusual",
    "duplicate": "Same invoice number and GSTIN seen before",
    "qr_mismatch": "QR code disagrees with the printed invoice",
    "future_date": "Invoice is dated in the future",
    "pre_gst_date": "Invoice is dated before GST started (1 July 2017)",
    "round_total": "Total is a suspiciously round number",
}


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return math.nan
    return value if value > 0 else math.nan


def _flag(state, bad="fail"):
    """1 when a check failed, 0 when it passed, NaN when it did not run."""
    if state == bad:
        return 1.0
    return 0.0 if state == "pass" else math.nan


def build_features(*, gstin_check, registry, rate_check, taxable, gst, total, duplicate,
                   qr_check, invoice_date="", name_match=None, today=None) -> dict:
    """Feature dict for one invoice. Inputs are the outputs of the individual checks."""
    today = today or date.today()
    taxable, gst, total = _number(taxable), _number(gst), _number(total)
    missing = bool(gstin_check.get("missing"))
    # A GSTIN that was misread rather than invalid gives no evidence either way.
    unknown = missing or bool(gstin_check.get("uncertain"))
    features = {
        "gstin_missing": 1.0 if missing else 0.0,
        "gstin_bad_format": math.nan if unknown else float(not gstin_check.get("format_ok")),
        "gstin_bad_checksum": math.nan if unknown or not gstin_check.get("format_ok")
        else float(not gstin_check.get("checksum_ok")),
        "registry_inactive": _flag(registry.get("state")),
        "registry_name_mismatch": math.nan if name_match is None else float(not name_match),
        "rate_mismatch": _flag(rate_check.get("state")),
        "total_gap_ratio": math.nan, "tax_share": math.nan, "off_slab": math.nan,
        "log_total": math.log10(total) if not math.isnan(total) else math.nan,
        "duplicate": float(bool(duplicate)),
        "qr_mismatch": _flag(qr_check.get("state")),
        "future_date": math.nan, "pre_gst_date": math.nan,
        "round_total": math.nan if math.isnan(total) else float(total >= 5000 and total % 1000 == 0),
    }
    if not math.isnan(taxable) and not math.isnan(total):
        features["total_gap_ratio"] = min(abs(total - taxable - (0 if math.isnan(gst) else gst)) / total, 1.0)
    if not math.isnan(gst) and not math.isnan(total):
        features["tax_share"] = min(gst / total, 1.0)
    if not math.isnan(gst) and not math.isnan(taxable):
        rate = gst / taxable * 100
        features["off_slab"] = min(min(abs(rate - slab) for slab in SLABS), 40.0)
    try:
        when = date.fromisoformat(str(invoice_date)[:10])
        features["future_date"] = float(when > today)
        features["pre_gst_date"] = float(when < GST_START)
    except ValueError:
        pass
    return features


def to_matrix(rows: list) -> np.ndarray:
    return np.array([[row[name] for name in FEATURES] for row in rows], dtype=float)


_model = None


def _load():
    global _model
    if _model is None:
        import xgboost as xgb

        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"{MODEL_PATH} is missing: run python scripts/train_fraud_model.py")
        _model = xgb.XGBClassifier()
        _model.load_model(MODEL_PATH)
    return _model


def predict_fraud(features: dict, total=0.0, failed_checks=(), missing=()) -> dict:
    """Score one invoice. failed_checks are the human-readable messages of checks that failed."""
    import xgboost as xgb

    model = _load()
    matrix = to_matrix([features])
    probability = float(model.predict_proba(matrix)[0][1])
    contributions = model.get_booster().predict(xgb.DMatrix(matrix, feature_names=FEATURES),
                                                pred_contribs=True)[0][:-1]
    drivers = [(EXPLAIN[name], round(float(value), 2))
               for name, value in sorted(zip(FEATURES, contributions), key=lambda pair: -pair[1])
               if value > 0.3]

    score = int(round(probability * 100))
    status = "Suspicious" if probability >= 0.5 else "Valid"
    risk_level = "Low" if probability < 0.2 else "Medium" if probability < 0.6 else "High"
    reasons = list(failed_checks) or ["No check failed"]
    warnings = [f"{name} could not be read, so checks that need it were skipped" for name in missing]
    if _number(total) > 100000:
        warnings.append("High-value invoice (over Rs 1,00,000): worth a second look")
    assessment = ("The checks found problems that are typical of fake or altered invoices. Verify it manually."
                  if status == "Suspicious" else
                  "No strong fraud signals. " + ("Some checks could not run, so confirm the details."
                                                 if missing else "The invoice is consistent."))
    return {
        "status": status,
        "score": score,
        "fraud_probability": f"{score}%",
        "risk_level": risk_level,
        "drivers": drivers[:3],
        "reasons": reasons,
        "warnings": warnings,
        "final_assessment": assessment,
    }
