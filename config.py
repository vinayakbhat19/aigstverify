import os

# Do NOT store secrets in source. Set these as environment variables instead.
# Example (Linux/macOS): export GEMINI_API_KEY="your_key_here"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# (Optional) GSTIN registry lookup through a GSTIN verification provider.
# GST_API_URL must contain {gstin}; see utils/gst_api.py. Without it the
# registry check is reported as "Not checked".
GST_API_URL = os.getenv("GST_API_URL", "")
GST_API_KEY = os.getenv("GST_API_KEY", "")