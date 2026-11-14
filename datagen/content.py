"""Builds the content of one random, internally consistent GST invoice."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from . import gst

DATE_START = date(2023, 4, 1)
DATE_END = date(2026, 10, 31)

ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
        "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
        "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _below_thousand(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(ONES[n // 100] + " Hundred")
        n %= 100
    if n >= 20:
        parts.append(TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else ""))
    elif n:
        parts.append(ONES[n])
    return " ".join(parts)


def amount_in_words(amount: Decimal) -> str:
    """Indian-system words, e.g. 'Rupees One Lakh Two Thousand and Paise Fifty Only'."""
    rupees, paise = int(amount), int((amount - int(amount)) * 100)
    parts = []
    for size, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        if rupees >= size:
            parts.append(_below_thousand(rupees // size) + " " + name)
            rupees %= size
    if rupees:
        parts.append(_below_thousand(rupees))
    words = "Rupees " + (" ".join(parts) or "Zero")
    if paise:
        words += " and Paise " + _below_thousand(paise)
    return words + " Only"


def indian_grouping(amount: Decimal) -> str:
    """1234567.5 -> '12,34,567.50'"""
    whole, frac = f"{amount:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{whole}.{frac}"


def format_rate(rate: Decimal) -> str:
    return f"{rate.normalize():f}" if rate != rate.to_integral() else str(int(rate))


def _date_text(rng, d: date) -> str:
    return rng.choice([
        d.strftime("%d/%m/%Y"), d.strftime("%d/%m/%Y"), d.strftime("%d-%m-%Y"),
        d.strftime("%d.%m.%Y"), d.strftime("%d-%b-%Y"), d.strftime("%d-%b-%y"),
        d.strftime("%d %b %Y"), d.strftime("%d %B %Y"), d.strftime("%d/%m/%y"),
        f"{d.day} {d.strftime('%b')}, {d.year}",
    ])


def _invoice_no(rng, d: date) -> str:
    fy = d.year if d.month >= 4 else d.year - 1
    fy_short = f"{fy % 100:02d}-{(fy + 1) % 100:02d}"
    n = rng.randint(1, 9999)
    prefix = rng.choice(["INV", "GST", "TI", "SI", "BL", "RTL", "A", "B", "TX", "SL"])
    return rng.choice([
        f"{prefix}-{n:04d}", f"{prefix}/{fy_short}/{n:04d}", f"{prefix}{n:05d}",
        f"{n}", f"{fy_short}/{n:03d}", f"{prefix}/{n}/{fy_short}", f"{prefix}-{d.year}-{n:05d}",
        f"{rng.choice('ABCDEFGH')}{n:04d}", f"{n:06d}", f"{prefix}{fy % 100}{(fy + 1) % 100}{n:04d}",
    ])


def _address(rng, state) -> dict:
    code, name, cities = state
    city = rng.choice(cities)
    line1 = rng.choice([
        f"No. {rng.randint(1, 480)}, {rng.choice(gst.STREETS)}",
        f"#{rng.randint(1, 99)}/{rng.choice('ABCD')}, {rng.choice(gst.STREETS)}",
        f"Shop No. {rng.randint(1, 60)}, {rng.choice(gst.STREETS)}",
        f"Plot {rng.randint(1, 250)}, {rng.choice(gst.STREETS)}",
        f"{rng.randint(1, 30)}, {rng.choice(['1st', '2nd', '3rd', '4th'])} Floor, {rng.choice(gst.STREETS)}",
    ])
    pin = f"{rng.randint(11, 85)}{rng.randint(0, 9999):04d}"
    return {
        "line1": line1,
        "city": city,
        "state": name,
        "state_code": code,
        "pin": pin,
        "line2": f"{city} - {pin}, {name}",
        "phone": f"{rng.choice('6789')}{rng.randint(0, 999999999):09d}",
    }


def _vendor_name(rng, category: str) -> str:
    root = rng.choice(gst.NAME_ROOTS)
    if rng.random() < 0.2:
        root = f"{root} {rng.choice(gst.NAME_ROOTS)}"
    name = f"{root} {rng.choice(gst.VENDOR_SUFFIXES[category])}"
    if category not in ("restaurant", "medical") and not name.endswith("& Co"):
        name += rng.choice(gst.COMPANY_FORMS)
    return rng.choice(["M/s ", "", "", "", "", ""]) + name


def _person(rng) -> str:
    return f"{rng.choice(gst.FIRST_NAMES)} {rng.choice(gst.LAST_NAMES)}"


def build_invoice(rng, category: str, b2b: bool) -> dict:
    """Random invoice. All amounts are Decimal and add up exactly as printed."""
    d = DATE_START + timedelta(days=rng.randrange((DATE_END - DATE_START).days + 1))
    post_reform = d >= gst.RATE_REFORM_DATE

    vendor_state = rng.choice(gst.STATES)
    vendor = _address(rng, vendor_state)
    vendor["name"] = _vendor_name(rng, category)
    vendor["gstin"] = gst.make_gstin(rng, vendor_state[0])
    vendor["pan"] = vendor["gstin"][2:12]
    vendor["email"] = rng.choice(["accounts", "sales", "info", "billing"]) + "@" + "".join(
        ch for ch in vendor["name"].lower().replace("m/s ", "") if ch.isalpha())[:14] + ".example"
    vendor["bank"] = {
        "name": rng.choice(gst.BANKS),
        "account": "".join(rng.choice("0123456789") for _ in range(rng.choice([11, 12, 14]))),
        "ifsc": "".join(rng.choice("ABCDEFGHIKLMNPRSTUV") for _ in range(4)) + "0"
                + "".join(rng.choice("0123456789") for _ in range(6)),
    }

    # Local sale is the norm; B2B sales cross state lines more often.
    interstate = rng.random() < (0.35 if b2b else 0.06)
    if category == "restaurant":
        interstate = False
    buyer_state = rng.choice([s for s in gst.STATES if s != vendor_state]) if interstate else vendor_state
    buyer = _address(rng, buyer_state)
    if b2b:
        buyer_category = rng.choice(list(gst.VENDOR_SUFFIXES))
        buyer["name"] = _vendor_name(rng, buyer_category)
        buyer["gstin"] = gst.make_gstin(rng, buyer_state[0])
    else:
        buyer["name"] = rng.choice([_person(rng)] * 4 + ["Cash", "Cash Sale", "Walk-in Customer"])
        buyer["gstin"] = ""

    # Line items
    max_items = {"restaurant": 8, "grocery": 9, "medical": 7, "jewellery": 2, "services": 3}.get(category, 5)
    pool = gst.CATALOGUE[category]
    chosen = rng.sample(pool, k=min(len(pool), rng.randint(1, max_items)))
    single_rate = rng.random() < 0.6
    if single_rate:
        first_rate = chosen[0][3 if post_reform else 2]
        chosen = [c for c in chosen if c[3 if post_reform else 2] == first_rate]

    items = []
    for desc, hsn, pre, post, lo, hi, unit, max_qty in chosen:
        qty = rng.randint(1, max(1, max_qty if b2b else min(max_qty, 6)))
        price = rng.uniform(lo, hi)
        price = money(round(price / 5) * 5 if price > 200 or category == "restaurant" else round(price, 1))
        gross = money(price * qty)
        discount = Decimal("0.00")
        if b2b and rng.random() < 0.15:
            discount = money(gross * Decimal(rng.choice(["0.02", "0.05", "0.10"])))
        taxable = gross - discount
        rate = Decimal(post if post_reform else pre)
        items.append({
            "desc": desc, "hsn": hsn, "qty": qty, "unit": unit, "price": price,
            "gross": gross, "discount": discount, "taxable": taxable, "rate": rate,
        })

    # Tax is computed per rate group on the group's taxable value.
    groups = []
    for rate in sorted({it["rate"] for it in items}):
        taxable = sum((it["taxable"] for it in items if it["rate"] == rate), Decimal("0.00"))
        if interstate:
            igst, cgst, sgst = money(taxable * rate / 100), Decimal("0.00"), Decimal("0.00")
        else:
            cgst = sgst = money(taxable * rate / 200)
            igst = Decimal("0.00")
        groups.append({
            "rate": rate, "half_rate": rate / 2, "taxable": taxable,
            "cgst": cgst, "sgst": sgst, "igst": igst, "tax": cgst + sgst + igst,
            "hsn": next(it["hsn"] for it in items if it["rate"] == rate),
        })

    # Per-item tax (for columnar layouts); the last item of each group absorbs rounding.
    for g in groups:
        members = [it for it in items if it["rate"] == g["rate"]]
        left = {"cgst": g["cgst"], "sgst": g["sgst"], "igst": g["igst"]}
        for idx, it in enumerate(members):
            for key in left:
                if idx == len(members) - 1:
                    share = left[key]
                else:
                    divisor = 100 if key == "igst" else 200
                    share = min(money(it["taxable"] * g["rate"] / divisor), left[key])
                it[key] = share
                left[key] -= share
            it["tax"] = it["cgst"] + it["sgst"] + it["igst"]
            it["total"] = it["taxable"] + it["tax"]

    taxable = sum((g["taxable"] for g in groups), Decimal("0.00"))
    cgst = sum((g["cgst"] for g in groups), Decimal("0.00"))
    sgst = sum((g["sgst"] for g in groups), Decimal("0.00"))
    igst = sum((g["igst"] for g in groups), Decimal("0.00"))
    exact_total = taxable + cgst + sgst + igst
    round_off = Decimal("0.00")
    if rng.random() < 0.65:
        round_off = exact_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP) - exact_total
    total = exact_total + round_off

    return {
        "category": category,
        "b2b": b2b,
        "interstate": interstate,
        "date": d,
        "date_text": _date_text(rng, d),
        "number": _invoice_no(rng, d),
        "vendor": vendor,
        "buyer": buyer,
        "place_of_supply": f"{buyer_state[1]} ({buyer_state[0]})",
        "items": items,
        "groups": groups,
        "taxable": taxable,
        "gross": sum((it["gross"] for it in items), Decimal("0.00")),
        "discount": sum((it["discount"] for it in items), Decimal("0.00")),
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "tax": cgst + sgst + igst,
        "round_off": round_off,
        "total": total,
        "total_words": amount_in_words(total),
        "total_qty": sum(it["qty"] for it in items),
        "payment_mode": rng.choice(["Cash", "UPI", "Card", "Credit", "NEFT", "Cheque"]),
        "due_days": rng.choice([7, 15, 30, 45]),
        "eway": "".join(rng.choice("0123456789") for _ in range(12)),
        "table_no": rng.randint(1, 30),
        "token": rng.randint(100, 9999),
        "time_text": f"{rng.randint(8, 22):02d}:{rng.randint(0, 59):02d}",
        "cashier": rng.choice(gst.FIRST_NAMES),
    }


def ground_truth(inv: dict) -> dict:
    """Canonical field values for an invoice, independent of how they are printed."""
    return {
        "vendor_name": inv["vendor"]["name"],
        "vendor_gstin": inv["vendor"]["gstin"],
        "buyer_name": inv["buyer"]["name"],
        "buyer_gstin": inv["buyer"]["gstin"],
        "invoice_no": inv["number"],
        "invoice_date": inv["date"].isoformat(),
        "invoice_date_text": inv["date_text"],
        "taxable_value": float(inv["taxable"]),
        "cgst_amount": float(inv["cgst"]),
        "sgst_amount": float(inv["sgst"]),
        "igst_amount": float(inv["igst"]),
        "gst_amount": float(inv["tax"]),
        "round_off": float(inv["round_off"]),
        "total_amount": float(inv["total"]),
        "gst_rates": [float(g["rate"]) for g in inv["groups"]],
        "supply_type": "inter-state" if inv["interstate"] else "intra-state",
        "category": inv["category"],
        "items": [
            {
                "description": it["desc"], "hsn": it["hsn"], "quantity": it["qty"],
                "unit_price": float(it["price"]), "taxable_value": float(it["taxable"]),
                "gst_rate": float(it["rate"]),
            }
            for it in inv["items"]
        ],
    }
