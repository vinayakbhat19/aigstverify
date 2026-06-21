import os

# Do NOT store secrets in source. Set these as environment variables instead.
# Example (Linux/macOS): export GEMINI_API_KEY="your_key_here"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# (Optional) GST API key — keep in env if used in production
GST_API_KEY = os.getenv("GST_API_KEY", "")