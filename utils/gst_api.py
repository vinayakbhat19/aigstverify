import requests

from config import GST_API_KEY


def verify_gst_api(gstin):

    headers = {
        "Authorization": GST_API_KEY
    }

    return {
        "gstin": gstin,
        "status": "Active"
    }