from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import getSampleStyleSheet


def generate_pdf(
    filename,
    data,
    fraud,
    gst_validation,
    gst_result,
    amount_validation
):

    doc = SimpleDocTemplate(filename)

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph(
            "GSTVision AI Report",
            styles['Title']
        )
    )

    elements.append(Spacer(1, 20))

    for key, value in data.items():

        elements.append(
            Paragraph(
                f"<b>{key}</b>: {value}",
                styles['BodyText']
            )
        )

    elements.append(Spacer(1, 20))

    elements.append(
        Paragraph(
            f"<b>Status:</b> {fraud['status']}",
            styles['BodyText']
        )
    )

    elements.append(
        Paragraph(
            f"<b>Fraud Probability:</b> {fraud['fraud_probability']}",
            styles['BodyText']
        )
    )

    elements.append(
        Paragraph(
            f"<b>GST Validation:</b> {gst_validation['message']}",
            styles['BodyText']
        )
    )

    elements.append(
        Paragraph(
            f"<b>GST Rule Match:</b> {gst_result['message']}",
            styles['BodyText']
        )
    )

    elements.append(
        Paragraph(
            f"<b>Amount Validation:</b> {amount_validation['message']}",
            styles['BodyText']
        )
    )

    doc.build(elements)