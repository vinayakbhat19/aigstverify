from utils.database import invoice_exists


def detect_duplicate(invoice_number, gstin):
    """True when an invoice with the same number and GSTIN was seen before.

    Without both values there is nothing to match on, so this returns False
    rather than matching every other invoice that was also missing them.
    """
    if not str(invoice_number or "").strip() or not str(gstin or "").strip():
        return False
    return invoice_exists(invoice_number, gstin)
