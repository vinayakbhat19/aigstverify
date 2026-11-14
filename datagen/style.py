"""Random look-and-feel and caption wording for one invoice."""

from decimal import Decimal

from .content import format_rate, indian_grouping

SANS = ["Liberation Sans", "DejaVu Sans", "Carlito", "Inter", "FreeSans"]
SERIF = ["Liberation Serif", "DejaVu Serif", "Caladea", "Bitstream Charter", "FreeSerif"]
MONO = ["Liberation Mono", "DejaVu Sans Mono", "Courier 10 Pitch", "FreeMono", "JetBrains Mono"]

ACCENTS = ["#1f3a8a", "#0f766e", "#9f1239", "#7c2d12", "#111827", "#4c1d95", "#14532d",
           "#b45309", "#0c4a6e", "#be123c", "#1e40af", "#374151"]

TEMPLATES = {
    # name: (weight, categories, share of B2B invoices)
    "classic": (18, ["electronics", "clothing", "hardware", "stationery", "auto_parts", "medical",
                     "grocery", "jewellery", "services"], 0.65),
    "tally": (14, ["electronics", "hardware", "stationery", "auto_parts", "medical", "grocery",
                   "clothing", "services"], 0.85),
    "modern": (12, ["services", "electronics", "clothing", "stationery", "jewellery"], 0.65),
    "ecommerce": (10, ["electronics", "clothing", "stationery", "grocery"], 0.25),
    "thermal": (18, ["restaurant", "restaurant", "restaurant", "grocery", "medical", "clothing"], 0.05),
    "letterhead": (10, ["services"], 0.9),
    "billbook": (9, ["hardware", "clothing", "jewellery", "grocery", "auto_parts", "stationery",
                     "medical"], 0.4),
    "columnar": (9, ["electronics", "hardware", "stationery", "auto_parts", "medical", "grocery",
                     "clothing", "services"], 0.75),
}

TERMS = [
    "Goods once sold will not be taken back or exchanged.",
    "Interest @ 18% p.a. will be charged if payment is not made within the due date.",
    "Subject to local jurisdiction only.",
    "Our responsibility ceases once the goods leave our premises.",
    "Warranty as per manufacturer terms.",
    "Please check the goods at the time of delivery.",
    "E. & O.E.",
    "Cheques are subject to realisation.",
]

NOTES = ["Thank you! Visit again", "THANK YOU - VISIT AGAIN", "Thank you for your business",
         "This is a computer generated invoice", "Have a nice day!", "E. & O.E.",
         "Subject to local jurisdiction", "Thanks for shopping with us"]


def make_style(rng, template: str, inv: dict):
    """Returns (S, L, m, r): style knobs, caption wording, money and rate formatters."""
    thermal = template == "thermal"
    font = rng.choice(MONO if thermal else SANS + SANS + SERIF + (MONO[:2] if template == "billbook" else []))
    accent = rng.choice(ACCENTS)
    mono_look = rng.random() < 0.35  # plain black-and-white print

    cur_sep, cur_att, cur_suffix = rng.choice(
        [("", "", "")] * 9 + [("₹ ", "", ""), ("Rs. ", "", ""), ("Rs ", "", ""), ("", "₹", ""),
                              ("", "Rs.", ""), ("", "", "/-"), ("INR ", "", "")])
    grouped = rng.random() < 0.7
    two_dp_rate = rng.random() < 0.15
    parens = rng.random() < 0.15

    def m(value) -> str:
        value = Decimal(value)
        return indian_grouping(value) if grouped else f"{value:.2f}"

    def r(value) -> str:
        value = Decimal(value)
        return f"{value:.2f}" if two_dp_rate else format_rate(value)

    S = {
        "font": f"'{font}', sans-serif",
        "size": round(rng.uniform(11, 12.6) if thermal else rng.uniform(11, 13.5), 1),
        "leading": round(rng.uniform(1.25, 1.5), 2),
        "width": rng.randint(300, 370) if thermal else 794,
        "min_height": 0 if thermal else (rng.choice([520, 560, 620]) if template == "billbook" else 1123),
        "pad": rng.randint(10, 16) if thermal else rng.randint(26, 46),
        "cell_pad": rng.randint(3, 6),
        "scale": 2.2 if thermal else 1.5,
        "ink": rng.choice(["#000", "#111", "#1a1a1a", "#222"]),
        "muted": "#555",
        "paper": rng.choice(["#fff", "#fff", "#fff", "#fdfdf8", "#fbfaf4"]) if not thermal else "#fff",
        "accent": "#000" if mono_look else accent,
        "tint": "#eee" if mono_look else rng.choice(["#eef2f7", "#f1f5f9", "#f5f0e8", "#eef6f0", "#f3f4f6"]),
        "line": rng.choice(["#000", "#333", "#666", "#999"]),
        "bw": rng.choice([1, 1, 1, 2]),
        "rule": rng.choice(["dashed", "dashed", "solid", "dotted"]),
        "sign_gap": rng.randint(26, 56),
        "fill_font": rng.choice(["'Courier 10 Pitch', monospace", "'Liberation Mono', monospace", "inherit"]),
        "fill_ink": rng.choice(["#1e3a8a", "#111", "#0f172a"]),
        "cur_sep": cur_sep, "cur_att": cur_att, "cur_suffix": cur_suffix,
        "pct": rng.choice(["%", "%", "%", "%", " %"]),
        "rate_open": "(" if parens else "", "rate_close": ")" if parens else "",
        "upper": rng.random() < 0.4,
        "flip": rng.random() < 0.35,
        "center": rng.random() < 0.5,
        "title_first": rng.random() < 0.4,
        "title": rng.choice(
            ["TAX INVOICE", "RETAIL INVOICE", "CASH BILL", "Tax Invoice", "GST INVOICE", "CASH MEMO"]
            if thermal or template == "billbook" else
            ["Tax Invoice/Bill of Supply/Cash Memo", "Tax Invoice"] if template == "ecommerce" else
            ["TAX INVOICE", "TAX INVOICE", "Tax Invoice", "GST INVOICE", "INVOICE", "GST TAX INVOICE"]),
        "show_hsn": rng.random() < (0.3 if thermal else 0.8),
        "show_gst_col": rng.random() < 0.35,
        "show_unit": rng.random() < 0.5,
        "show_bank": inv["b2b"] and rng.random() < 0.7,
        "show_terms": rng.random() < 0.6,
        "show_words": rng.random() < 0.75,
        "show_pan": rng.random() < 0.4,
        "show_pos": rng.random() < 0.6,
        "show_pay": rng.random() < 0.5,
        "show_eway": rng.random() < 0.3,
        "show_state": rng.random() < 0.5,
        "show_note": rng.random() < 0.5,
        "show_buyer": (not thermal) or inv["b2b"] or rng.random() < 0.3,
        "buyer_addr": rng.random() < 0.5,
        "gstin_top": rng.random() < 0.65,
        "filler_rows": rng.choice([0, 0, 1, 2, 3, 5]),
        "terms": rng.sample(TERMS, k=rng.randint(2, 4)),
        "note": rng.choice(NOTES),
        "transport": rng.choice(["By Road", "Own Vehicle", "Courier", "Transport", "Hand Delivery"]),
        "marketplace": rng.choice(["BazaarOne", "QuickCart", "DesiMart Online", "ShopNest", "KiranaKing"]),
        "order_no": f"{rng.randint(100, 999)}-{rng.randint(1000000, 9999999)}-{rng.randint(1000000, 9999999)}",
        "order_date": inv["date"].strftime("%d.%m.%Y"),
        "txn": "".join(rng.choice("0123456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(18)),
    }

    tax_names = rng.choice(
        [("CGST", "SGST", "IGST")] * 6 + [
            ("Central Tax", "State Tax", "Integrated Tax"), ("CGST", "SGST/UTGST", "IGST"),
            ("Add: CGST", "Add: SGST", "Add: IGST"), ("C.G.S.T.", "S.G.S.T.", "I.G.S.T."),
            ("Output CGST", "Output SGST", "Output IGST")])
    services = inv["category"] == "services"
    L = {
        "sep": rng.choice([":", ":", ":", " :", "", " -", ".:"]),
        "gstin": rng.choice(["GSTIN", "GSTIN", "GSTIN", "GSTIN No", "GST No", "GSTIN/UIN", "GST IN",
                             "GST Reg No", "GSTIN No.", "GST NO"]),
        "inv_no": rng.choice(["Invoice No", "Invoice No.", "Inv No", "Bill No", "Invoice #",
                              "Invoice Number", "Bill No.", "Inv. No.", "Memo No"]),
        "date": rng.choice(["Date", "Date", "Invoice Date", "Dated", "Bill Date", "Dt", "Inv Date"]),
        "buyer": rng.choice(["Bill To", "Buyer", "Billed To", "Customer", "Party", "Buyer (Bill to)",
                             "M/s", "Customer Name", "To", "Name"]),
        "sno": rng.choice(["S.No", "Sl No", "Sr.", "#", "S.N.", "Sl."]),
        "desc": rng.choice(["Description of Services", "Particulars", "Description"] if services else
                           ["Description", "Particulars", "Description of Goods", "Item", "Item Name",
                            "Product", "Item Description"]),
        "hsn": rng.choice(["SAC", "HSN/SAC", "SAC Code"] if services else
                          ["HSN", "HSN/SAC", "HSN Code", "HSN"]),
        "qty": rng.choice(["Qty", "Qty", "Quantity", "Qty.", "Nos"]),
        "rate": rng.choice(["Rate", "Rate", "Price", "Unit Price", "MRP"]),
        "amount": rng.choice(["Amount", "Amount", "Total", "Value", "Amt"]),
        "gross": rng.choice(["Gross Amount", "Sub Total", "Total"]),
        "discount": rng.choice(["Less: Discount", "Discount", "Trade Discount"]),
        "taxable": rng.choice(["Taxable Value", "Taxable Amount", "Sub Total", "Total Before Tax",
                               "Taxable Amt", "Net Amount", "Subtotal", "Assessable Value"]),
        "cgst": tax_names[0], "sgst": tax_names[1], "igst": tax_names[2],
        "at": " " if parens else rng.choice([" @ ", " @ ", " ", " "]),
        "on": "on",
        "total_word": "Total",
        "round_off": rng.choice(["Round Off", "Rounded Off", "Round off (+/-)", "R/O"]),
        "total": rng.choice(["Grand Total", "Total", "Total Amount", "Net Payable", "Amount Payable",
                             "Invoice Total", "Bill Amount", "TOTAL", "GRAND TOTAL", "Net Amount Payable"]),
        "words": rng.choice(["Amount in Words", "Rupees in words", "Amount Chargeable (in words)",
                             "In Words", "Total Invoice Value (in words)"]),
        "bank": rng.choice(["Bank Details", "Company's Bank Details", "Our Bank Details"]),
        "terms": rng.choice(["Terms & Conditions", "Terms and Conditions", "Note"]),
        "signatory": rng.choice(["Authorised Signatory", "Authorized Signatory", "Proprietor",
                                 "Signature", "Auth. Signatory"]),
    }
    # "Sub Total" must not caption two different amounts on one invoice.
    if L["gross"] == L["taxable"] or (L["gross"] == "Total" and L["total"] in ("Total", "TOTAL")):
        L["gross"] = "Gross Amount"
    if L["taxable"] == "Net Amount" and "Net" in L["total"]:
        L["taxable"] = "Taxable Value"
    return S, L, m, r
