"""PDF version of the invoice report."""

from xml.sax.saxutils import escape

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

STATE_LABEL = {"pass": "Passed", "fail": "FAILED", "skip": "Not checked"}


def safe_text(value):
    if isinstance(value, (list, tuple, set)):
        value = ", ".join(map(str, value))
    return escape(str(value))


def generate_pdf(filename, data, fraud, gst_validation, gst_result, amount_validation, checks=None):
    styles = getSampleStyleSheet()
    body, heading = styles["BodyText"], styles["Heading2"]
    elements = [Paragraph("GSTVision AI Report", styles["Title"]), Spacer(1, 12)]

    def line(label, value):
        elements.append(Paragraph(f"<b>{safe_text(label)}:</b> {safe_text(value)}", body))

    elements.append(Paragraph("Verdict", heading))
    line("Status", fraud.get("status", ""))
    line("Fraud risk", f"{fraud.get('fraud_probability', '')} ({fraud.get('risk_level', '')})")
    line("Assessment", fraud.get("final_assessment", ""))
    for label, _ in fraud.get("drivers", []):
        line("Reason", label)
    for warning in fraud.get("warnings", []):
        line("Warning", warning)

    elements.append(Paragraph("Checks", heading))
    if checks:
        for name, state, detail in checks:
            line(f"{name} ({STATE_LABEL.get(state, state)})", detail)
    else:
        line("GSTIN", gst_validation.get("message", ""))
        line("GST rate", gst_result.get("message", ""))
        line("Totals", amount_validation.get("message", ""))

    elements.append(Paragraph("Invoice fields", heading))
    for key, value in data.items():
        if key not in ("Field Confidence",):
            line(key, value)
    SimpleDocTemplate(filename).build(elements)
