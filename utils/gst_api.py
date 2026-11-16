"""GSTIN registry lookup through a GSTIN verification API.

The GST Network has no free public API, so this calls whichever provider you
configure (a GST Suvidha Provider or a paid GSTIN verification service):

    GST_API_URL         URL with {gstin} where the GSTIN goes,
                        e.g. https://api.example.com/gstin/{gstin}
    GST_API_KEY         the provider's key (never commit it)
    GST_API_KEY_HEADER  header that carries the key (default: Authorization)

Without GST_API_URL nothing is sent and the status is "Not checked"; the app
never reports a GSTIN as active unless a registry said so.
"""

import os
from datetime import date

import requests

from utils.validator import gstin_checksum_ok

TIMEOUT_SECONDS = 8
_cache = {}

# Field names used by the GSTN taxpayer search and most providers that wrap it.
_STATUS_KEYS = ("sts", "status", "gstinStatus", "taxpayerStatus")
_LEGAL_KEYS = ("lgnm", "legalName", "legal_name")
_TRADE_KEYS = ("tradeNam", "tradeName", "trade_name")
_REGISTERED_KEYS = ("rgdt", "registrationDate", "registration_date")
_CANCELLED_KEYS = ("cxdt", "cancellationDate", "cancellation_date")


def _find(payload, keys):
    """First value of any of keys, searching nested dicts (providers wrap the record differently)."""
    if isinstance(payload, dict):
        for key in keys:
            if payload.get(key) not in (None, ""):
                return payload[key]
        for value in payload.values():
            found = _find(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find(value, keys)
            if found not in (None, ""):
                return found
    return None


def _result(gstin, state, status, message, **extra):
    # state: "pass" (active), "fail" (cancelled, suspended or not found), "skip" (not checked)
    return {"gstin": gstin, "state": state, "status": status, "message": message, **extra}


def verify_gst_api(gstin):
    gstin = str(gstin or "").strip().upper()
    url = os.getenv("GST_API_URL", "")
    if not gstin:
        return _result(gstin, "skip", "Not checked", "No GSTIN to look up")
    if not gstin_checksum_ok(gstin):
        return _result(gstin, "skip", "Not checked", "GSTIN is not valid, so it was not looked up")
    if not url:
        return _result(gstin, "skip", "Not checked",
                       "No registry API configured (set GST_API_URL and GST_API_KEY)")
    if gstin in _cache:
        return _cache[gstin]

    headers = {}
    key = os.getenv("GST_API_KEY", "")
    if key:
        headers[os.getenv("GST_API_KEY_HEADER", "Authorization")] = key
    try:
        response = requests.get(url.replace("{gstin}", gstin), headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as error:
        return _result(gstin, "skip", "Not checked", f"Registry lookup failed: {type(error).__name__}")
    if response.status_code == 404:
        result = _result(gstin, "fail", "Not found", "The registry has no taxpayer with this GSTIN")
        _cache[gstin] = result
        return result
    if response.status_code != 200:
        return _result(gstin, "skip", "Not checked", f"Registry returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        return _result(gstin, "skip", "Not checked", "Registry reply was not JSON")

    status = str(_find(payload, _STATUS_KEYS) or "").strip()
    legal_name = _find(payload, _LEGAL_KEYS) or ""
    trade_name = _find(payload, _TRADE_KEYS) or ""
    registered_on = _find(payload, _REGISTERED_KEYS) or ""
    cancelled_on = _find(payload, _CANCELLED_KEYS) or ""
    if not status:
        return _result(gstin, "skip", "Not checked", "Registry reply had no status field")
    active = status.lower() == "active"
    detail = ", ".join(part for part in (legal_name, trade_name and f"trading as {trade_name}",
                                         registered_on and f"registered {registered_on}",
                                         cancelled_on and f"cancelled {cancelled_on}") if part)
    result = _result(gstin, "pass" if active else "fail", status.title(),
                     f"Registry says {status.lower()}" + (f": {detail}" if detail else ""),
                     legal_name=legal_name, trade_name=trade_name, registered_on=registered_on,
                     checked_on=date.today().isoformat())
    _cache[gstin] = result
    return result
