import re

def extract_invoice_data(text):

    data = {}

    gstin = re.findall(

        r'\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z0-9]{3}',

        text
    )

    amounts = re.findall(
        r'\d+\.\d+',
        text
    )

    total = max(
        [float(a) for a in amounts],
        default=0
    )

    gst = round(
        total * 0.05,
        2
    )

    data["GSTIN"] = (

        gstin[0]

        if gstin

        else "Not Found"
    )

    data["Invoice Number"] = "AUTO"

    data["Total Amount"] = total

    data["GST Amount"] = gst

    data["GST Percentage"] = 5

    return data