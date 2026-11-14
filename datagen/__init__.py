"""Synthetic Indian GST invoice dataset generator (see scripts/generate_invoices.py)."""

# Entity types, in the order used to build the BIO label list.
ENTITY_TYPES = [
    "VENDOR_NAME",
    "VENDOR_GSTIN",
    "BUYER_NAME",
    "BUYER_GSTIN",
    "INVOICE_NO",
    "INVOICE_DATE",
    "ITEM_DESC",
    "HSN",
    "TAXABLE_VALUE",
    "CGST_RATE",
    "CGST_AMOUNT",
    "SGST_RATE",
    "SGST_AMOUNT",
    "IGST_RATE",
    "IGST_AMOUNT",
    "TOTAL_AMOUNT",
]

LABELS = ["O"] + [f"{p}-{e}" for e in ENTITY_TYPES for p in ("B", "I")]
