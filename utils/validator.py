import re

def validate_gstin(gstin):

    pattern = re.compile(

        r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$'
    )

    if pattern.match(gstin):

        return {

            "valid": True,

            "message": "Valid GSTIN"
        }

    return {

        "valid": False,

        "message": "Invalid GSTIN"
    }

_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


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
