"""Reads QR codes on the invoice and compares them with the printed fields.

Two kinds are understood:

* GST e-invoice QR (B2B invoices from businesses above the e-invoicing limit).
  It is a JWT signed by the Invoice Registration Portal whose payload holds
  SellerGstin, BuyerGstin, DocNo, DocDt, TotInvVal, ItemCnt, MainHsnCode and
  Irn. Editing the printed invoice without regenerating the QR leaves the two
  out of step, which is a strong tampering signal. The signature itself is not
  verified here (that needs the portal's public key), so a forged QR with
  matching values would pass.
* UPI payment QR (common on retail bills): "upi://pay?...&am=<amount>".
  The amount, when present, should equal the invoice total.
"""

import base64
import json
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np


def _decode_qr_texts(image) -> list:
    """Text of every QR code found in a PIL image (empty when none).

    OpenCV's ArUco-based detector decodes dense codes (an e-invoice QR holds
    500+ characters) that the classic detector finds but fails to read, so it
    is tried first.
    """
    array = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    detectors = [cv2.QRCodeDetectorAruco()] if hasattr(cv2, "QRCodeDetectorAruco") else []
    detectors.append(cv2.QRCodeDetector())
    for detector in detectors:
        try:
            ok, decoded, _, _ = detector.detectAndDecodeMulti(array)
            texts = [t for t in decoded if t] if ok else []
            if not texts:
                text = detector.detectAndDecode(array)[0]
                texts = [text] if text else []
        except cv2.error:
            texts = []
        if texts:
            return texts
    return []


def _jwt_payload(text: str):
    parts = text.strip().split(".")
    if len(parts) != 3:
        return None
    try:
        body = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body))
    except (ValueError, json.JSONDecodeError):
        return None
    data = payload.get("data", payload)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) and ("SellerGstin" in data or "Irn" in data) else None


def _same_number(a, b) -> bool:
    return str(a or "").replace(" ", "").upper() == str(b or "").replace(" ", "").upper()


def _iso(date_text: str) -> str:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(date_text), fmt).date().isoformat()
        except ValueError:
            pass
    return str(date_text or "")


def validate_qr(image, gstin="", invoice_number="", total=0.0, invoice_date="") -> dict:
    """{"state": "pass" | "fail" | "skip", "kind", "mismatches", "message", "qr": decoded fields}."""
    try:
        texts = _decode_qr_texts(image)
    except Exception as error:  # a QR problem must never stop the invoice being checked
        return {"state": "skip", "kind": "", "mismatches": [], "qr": {},
                "message": f"QR scan failed: {type(error).__name__}"}
    if not texts:
        return {"state": "skip", "kind": "", "mismatches": [], "qr": {}, "message": "No QR code found"}

    for text in texts:
        data = _jwt_payload(text)
        if data:
            mismatches = []
            if gstin and data.get("SellerGstin") and data["SellerGstin"].upper() != gstin.upper():
                mismatches.append(f"seller GSTIN {data['SellerGstin']} in QR vs {gstin} printed")
            if invoice_number and data.get("DocNo") and not _same_number(data["DocNo"], invoice_number):
                mismatches.append(f"invoice number {data['DocNo']} in QR vs {invoice_number} printed")
            if total and data.get("TotInvVal") not in (None, ""):
                try:
                    if abs(float(data["TotInvVal"]) - float(total)) > 1:
                        mismatches.append(f"total {float(data['TotInvVal']):,.2f} in QR vs {float(total):,.2f} printed")
                except (TypeError, ValueError):
                    pass
            if invoice_date and data.get("DocDt") and _iso(data["DocDt"]) != str(invoice_date)[:10]:
                mismatches.append(f"date {data['DocDt']} in QR vs {invoice_date} printed")
            irn = str(data.get("Irn", ""))
            return {"state": "fail" if mismatches else "pass", "kind": "e-invoice", "mismatches": mismatches,
                    "qr": data,
                    "message": ("E-invoice QR disagrees with the printed invoice: " + "; ".join(mismatches))
                    if mismatches else f"E-invoice QR matches the printed invoice (IRN {irn[:12]}…)"}

    for text in texts:
        if text.lower().startswith("upi://"):
            query = parse_qs(urlparse(text).query)
            amount = (query.get("am") or [""])[0]
            payee = (query.get("pn") or [""])[0]
            if amount and total:
                try:
                    if abs(float(amount) - float(total)) > 1:
                        return {"state": "fail", "kind": "upi", "qr": {"am": amount, "pn": payee},
                                "mismatches": [f"UPI amount {amount} vs total {float(total):,.2f}"],
                                "message": f"UPI QR asks for {amount}, but the invoice total is {float(total):,.2f}"}
                    return {"state": "pass", "kind": "upi", "qr": {"am": amount, "pn": payee}, "mismatches": [],
                            "message": f"UPI QR amount matches the total ({amount})"}
                except ValueError:
                    pass
            return {"state": "skip", "kind": "upi", "qr": {"pn": payee}, "mismatches": [],
                    "message": "UPI payment QR without an amount, nothing to compare"}

    return {"state": "skip", "kind": "other", "mismatches": [], "qr": {},
            "message": "QR code found, but it is not an e-invoice or UPI code"}
