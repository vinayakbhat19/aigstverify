import requests

from config import GST_API_KEY


def verify_gst_api(gstin):

    # EMPTY GSTIN

    if not gstin:

        return {

            "gstin": "",

            "status": "Not Verified"
        }

    try:

        headers = {

            "Authorization": GST_API_KEY
        }

        # SAMPLE RESPONSE
        # Replace with real API later

        return {

            "gstin": gstin,

            "status": "Active"
        }

    except Exception as e:

        return {

            "gstin": gstin,

            "status": "API Error",

            "error": str(e)
        }