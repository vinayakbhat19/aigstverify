"""GSTIN checks: shape, state code and the mod-36 check character."""

import re

GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$")
_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# 01-38 are states and union territories, 97 is "other territory", 99 is the Centre.
_STATE_CODES = {f"{n:02d}" for n in range(1, 39)} | {"97", "99"}


def gstin_checksum_ok(gstin):
    """True when the 15th character matches the checksum of the first 14."""
    gstin = str(gstin).strip().upper()
    if len(gstin) != 15 or any(ch not in _GSTIN_CHARS for ch in gstin):
        return False
    total = 0
    for i, ch in enumerate(gstin[:14]):
        product = _GSTIN_CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _GSTIN_CHARS[(36 - total % 36) % 36] == gstin[14]


def validate_gstin(gstin):
    """{"valid", "format_ok", "checksum_ok", "message"}. valid needs all three checks."""
    gstin = str(gstin or "").strip().upper()
    if not gstin:
        return {"valid": False, "format_ok": False, "checksum_ok": False, "missing": True,
                "message": "No GSTIN found on the invoice"}
    format_ok = bool(GSTIN_PATTERN.match(gstin)) and gstin[:2] in _STATE_CODES
    checksum_ok = format_ok and gstin_checksum_ok(gstin)
    if not format_ok:
        message = "Not a valid GSTIN pattern (15 characters: state code, PAN, entity number, Z, check character)"
    elif not checksum_ok:
        message = "Check character does not match: the GSTIN is mistyped, misread or made up"
    else:
        message = "Pattern, state code and check character are all valid"
    return {"valid": checksum_ok, "format_ok": format_ok, "checksum_ok": checksum_ok,
            "missing": False, "message": message}
