from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import (
    getSampleStyleSheet
)

# =========================================
# SAFE STRING CONVERTER
# =========================================

def safe_text(value):

    try:

        # LIST → STRING

        if isinstance(value, list):

            return ", ".join(
                map(str, value)
            )

        # DICT → STRING

        if isinstance(value, dict):

            return str(value)

        return str(value)

    except:

        return "N/A"

# =========================================
# PDF GENERATOR
# =========================================

def generate_pdf(

    filename,

    data,

    fraud,

    gst_validation,

    gst_result,

    amount_validation
):

    doc = SimpleDocTemplate(
        filename
    )

    styles = getSampleStyleSheet()

    elements = []

    # =====================================
    # TITLE
    # =====================================

    elements.append(

        Paragraph(

            "GSTVision AI Report",

            styles['Title']
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    # =====================================
    # INVOICE DATA
    # =====================================

    for key, value in data.items():

        safe_value = safe_text(
            value
        )

        elements.append(

            Paragraph(

                f"<b>{safe_text(key)}</b>: {safe_value}",

                styles['BodyText']
            )
        )

        elements.append(
            Spacer(1, 8)
        )

    elements.append(
        Spacer(1, 20)
    )

    # =====================================
    # FRAUD DETAILS
    # =====================================

    elements.append(

        Paragraph(

            f"<b>Status:</b> {safe_text(fraud.get('status'))}",

            styles['BodyText']
        )
    )

    elements.append(

        Paragraph(

            f"<b>Fraud Probability:</b> {safe_text(fraud.get('fraud_probability'))}",

            styles['BodyText']
        )
    )

    elements.append(

        Paragraph(

            f"<b>GST Validation:</b> {safe_text(gst_validation.get('message'))}",

            styles['BodyText']
        )
    )

    elements.append(

        Paragraph(

            f"<b>GST Rule Match:</b> {safe_text(gst_result.get('message'))}",

            styles['BodyText']
        )
    )

    elements.append(

        Paragraph(

            f"<b>Amount Validation:</b> {safe_text(amount_validation.get('message'))}",

            styles['BodyText']
        )
    )

    # =====================================
    # BUILD PDF
    # =====================================

    doc.build(elements)