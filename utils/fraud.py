# =========================================
# FILE: utils/fraud.py
# =========================================

import joblib
import numpy as np

# =========================================
# LOAD TRAINED MODEL
# =========================================

model = joblib.load(
    "models/fraud_model.pkl"
)

# =========================================
# FRAUD PREDICTION
# =========================================

def predict_fraud(

    amount,

    gst,

    gst_valid,

    gst_match,

    duplicate,

    amount_valid=True
):

    # =====================================
    # SAFE CONVERSION
    # =====================================

    amount = float(amount)

    gst = float(gst)

    # =====================================
    # FEATURE ARRAY
    # =====================================

    features = np.array([

        [

            amount,

            gst,

            int(gst_valid),

            int(gst_match),

            int(duplicate)
        ]
    ])

    # =====================================
    # ML FRAUD PROBABILITY
    # =====================================

    probability = model.predict_proba(
        features
    )[0][1]

    # =====================================
    # TRUST SCORE REDUCTION
    # =====================================

    if gst_valid:
        probability *= 0.60

    if gst_match:
        probability *= 0.50

    if amount_valid:
        probability *= 0.50

    if not duplicate:
        probability *= 0.50

    # =====================================
    # EXTRA SAFE REDUCTION
    # =====================================

    if (
        gst_valid and
        gst_match and
        amount_valid and
        not duplicate
    ):

        probability *= 0.20

    # =====================================
    # LIMIT VALUES
    # =====================================

    probability = max(
        0.01,
        min(probability, 0.99)
    )

    # =====================================
    # FRAUD PERCENT
    # =====================================

    fraud_percent = round(

        probability * 100,

        2
    )

    # =====================================
    # RULE-BASED CHECKS
    # =====================================

    critical_issues = 0

    if not gst_valid:

        critical_issues += 1

    if not gst_match:

        critical_issues += 1

    if duplicate:

        critical_issues += 1

    if not amount_valid:

        critical_issues += 1

    # =====================================
    # FINAL STATUS
    # =====================================

    if critical_issues >= 2:

        status = "Suspicious"

    elif probability > 0.75:

        status = "Suspicious"

    else:

        status = "Valid"

    # =====================================
    # RISK LEVEL
    # =====================================

    if probability < 0.10:

        risk_level = "Low"

    elif probability < 0.40:

        risk_level = "Medium"

    else:

        risk_level = "High"

    # =====================================
    # FRAUD REASONS
    # =====================================

    reasons = []

    checks_passed = []

    warnings = []

    # =====================================
    # GST VALIDATION
    # =====================================

    if gst_valid:

        checks_passed.append(
            "Valid GSTIN"
        )

    else:

        reasons.append(
            "Invalid GSTIN"
        )

    # =====================================
    # GST RULE CHECK
    # =====================================

    if gst_match:

        checks_passed.append(
            "Correct GST percentage"
        )

    else:

        reasons.append(
            "GST percentage mismatch"
        )

    # =====================================
    # DUPLICATE CHECK
    # =====================================

    if duplicate:

        reasons.append(
            "Duplicate invoice detected"
        )

    else:

        checks_passed.append(
            "No duplicate invoice"
        )

    # =====================================
    # AMOUNT VALIDATION
    # =====================================

    if amount_valid:

        checks_passed.append(
            "Invoice total calculation correct"
        )

    else:

        reasons.append(
            "Invoice total mismatch"
        )

    # =====================================
    # HIGH VALUE WARNING
    # =====================================

    if amount > 100000:

        warnings.append(
            "High invoice amount detected"
        )

    # =====================================
    # GST > TOTAL CHECK
    # =====================================

    if gst > amount:

        reasons.append(
            "GST amount exceeds total amount"
        )

    # =====================================
    # NORMAL CLEAN INVOICE
    # =====================================

    if len(reasons) == 0:

        reasons.append(
            "Invoice follows normal GST patterns"
        )

    # =====================================
    # CONFIDENCE SCORE
    # =====================================

    confidence = round(

        (1 - probability) * 100,

        2
    )

    # =====================================
    # FINAL ASSESSMENT
    # =====================================

    if status == "Valid":

        final_assessment = (

            "Invoice complies with "
            "Indian GST rules and "
            "appears genuine."
        )

    else:

        final_assessment = (

            "Invoice shows suspicious "
            "patterns and requires "
            "manual verification."
        )

    # =====================================
    # RETURN FINAL RESULT
    # =====================================

    return {

        "status":

            status,

        "fraud_probability":

            f"{fraud_percent}%",

        "confidence_score":

            f"{confidence}%",

        "risk_level":

            risk_level,

        "checks_passed":

            checks_passed,

        "warnings":

            warnings,

        "reasons":

            reasons,

        "final_assessment":

            final_assessment
    }