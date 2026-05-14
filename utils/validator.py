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