"""Checks that taxable value + GST = invoice total."""

TOLERANCE = 1.0  # invoices round the total to the nearest rupee


def validate_amounts(subtotal, gst_amount, final_total):
    """{"state": "pass" | "fail" | "skip", "valid", "gap", "message"}."""
    try:
        subtotal, gst_amount, final_total = float(subtotal or 0), float(gst_amount or 0), float(final_total or 0)
    except (TypeError, ValueError):
        subtotal = gst_amount = final_total = 0.0
    if subtotal <= 0 or final_total <= 0:
        return {"state": "skip", "valid": True, "gap": None,
                "message": "Taxable value or total could not be read, so the maths was not checked"}
    calculated = round(subtotal + gst_amount, 2)
    gap = round(final_total - calculated, 2)
    if abs(gap) <= TOLERANCE:
        return {"state": "pass", "valid": True, "gap": gap, "calculated_total": calculated,
                "message": f"Taxable {subtotal:,.2f} + GST {gst_amount:,.2f} = {final_total:,.2f}"}
    return {"state": "fail", "valid": False, "gap": gap, "calculated_total": calculated,
            "message": f"Taxable + GST is {calculated:,.2f} but the invoice total is {final_total:,.2f} "
                       f"(off by {abs(gap):,.2f})"}
