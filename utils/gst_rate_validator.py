"""Compares the invoice's GST rate with the rates expected for its category."""


def validate_gst_rate(expected_rates, detected_rate, category=""):
    """{"state": "pass" | "fail" | "skip", "valid", "message"}.

    "skip" means there was not enough information to judge, and is not
    treated as a problem (valid is True).
    """
    try:
        detected = float(detected_rate or 0)
    except (TypeError, ValueError):
        detected = 0.0
    label = category or "this category"
    if not expected_rates:
        return {"state": "skip", "valid": True,
                "message": "Category not recognised, so the rate was not checked"}
    if detected <= 0:
        if 0 in expected_rates:
            return {"state": "pass", "valid": True, "message": f"No GST charged, allowed for {label}"}
        return {"state": "skip", "valid": True,
                "message": "GST rate could not be read (possibly several rates on one invoice)"}
    allowed = ", ".join(f"{r:g}%" for r in sorted(expected_rates))
    if any(abs(detected - rate) < 0.01 for rate in expected_rates):
        return {"state": "pass", "valid": True, "message": f"{detected:g}% is a valid rate for {label}"}
    if len(expected_rates) > 1 and min(expected_rates) < detected < max(expected_rates):
        return {"state": "skip", "valid": True,
                "message": f"{detected:g}% looks like a mix of {allowed} items, so it was not judged"}
    return {"state": "fail", "valid": False,
            "message": f"{detected:g}% charged, but {label} is taxed at {allowed}"}
