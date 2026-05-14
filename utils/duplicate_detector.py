from utils.database import invoice_exists


def detect_duplicate(
    invoice_number,
    gstin
):

    return invoice_exists(
        invoice_number,
        gstin
    )