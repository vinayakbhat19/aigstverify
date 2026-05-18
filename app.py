from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from PIL import Image

import re

from utils.ocr import extract_text
from utils.llm_extractor import extract_invoice_llm
from utils.validator import validate_gstin
from utils.gst_api import verify_gst_api
from utils.product_classifier import detect_product_category
from utils.gst_rate_validator import validate_gst_rate
from utils.duplicate_detector import detect_duplicate
from utils.fraud import predict_fraud
from utils.amount_validator import validate_amounts

from utils.database import (
    init_db,
    save_invoice
)

from utils.report_generator import generate_pdf

# =========================================
# FASTAPI APP
# =========================================

app = FastAPI()

# =========================================
# IN-MEMORY REPORT CACHE
# =========================================

report_cache = {}

templates = Jinja2Templates(
    directory="templates"
)

# =========================================
# DATABASE
# =========================================

init_db()

# =========================================
# STATIC FILES
# =========================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads"
)

app.mount(
    "/reports",
    StaticFiles(directory="reports"),
    name="reports"
)

# =========================================
# CLEAN NUMBER
# =========================================

def clean_number(value):

    try:

        return float(

            str(value)

            .replace("%", "")

            .replace(",", "")

            .replace("₹", "")

            .strip()
        )

    except:

        return 0.0

# =========================================
# HOME PAGE
# =========================================

@app.get(
    "/",
    response_class=HTMLResponse
)
async def home():

    return open(
        "templates/index.html",
        encoding="utf-8"
    ).read()

# =========================================
# UPLOAD ROUTE
# =========================================

@app.post(
    "/upload",
    response_class=HTMLResponse
)
async def upload_invoice(

    request: Request,

    file: UploadFile = File(...)
):

    try:

        # =====================================
        # SAVE IMAGE
        # =====================================

        image_path = f"uploads/{file.filename}"

        with open(image_path, "wb") as f:

            f.write(
                await file.read()
            )

        # =====================================
        # OPEN IMAGE
        # =====================================

        image = Image.open(
            image_path
        )

        # =====================================
        # OCR
        # =====================================

        text = extract_text(image)

        print("\n===== OCR TEXT =====\n")

        print(text)

        print("\n====================\n")

        # =====================================
        # DATA EXTRACTION
        # =====================================

        data = extract_invoice_llm(
            text,
            image=image
        )

        print("\n===== EXTRACTED DATA =====\n")

        print(data)

        print("\n==========================\n")

        # =====================================
        # CLEAN VALUES
        # =====================================

        subtotal = clean_number(
            data.get(
                "Subtotal",
                0
            )
        )

        total_amount = clean_number(
            data.get(
                "Total Amount",
                0
            )
        )

        gst_amount = clean_number(
            data.get(
                "GST Amount",
                0
            )
        )

        gst_percentage = clean_number(
            data.get(
                "GST Percentage",
                0
            )
        )

        # =====================================
        # GST VALIDATION
        # =====================================

        gst_validation = validate_gstin(

            data.get(
                "GSTIN",
                ""
            )
        )

        gst_api = verify_gst_api(

            data.get(
                "GSTIN",
                ""
            )
        )

        # =====================================
        # PRODUCT CATEGORY
        # =====================================

        product = detect_product_category(
            text,
            ai_category=data.get("Category", "")
        )

        # =====================================
        # GST RATE VALIDATION
        # =====================================

        gst_result = validate_gst_rate(

            product.get(
                "expected_gst",
                18
            ),

            gst_percentage
        )

        # =====================================
        # AMOUNT VALIDATION
        # =====================================

        amount_validation = validate_amounts(

            subtotal,

            gst_amount,

            total_amount
        )

        # =====================================
        # DUPLICATE CHECK
        # =====================================

        duplicate = detect_duplicate(

            data.get(
                "Invoice Number",
                ""
            ),

            data.get(
                "GSTIN",
                ""
            )
        )

        # =====================================
        # FRAUD PREDICTION
        # =====================================

        fraud = predict_fraud(

            total_amount,

            gst_amount,

            gst_validation["valid"],

            gst_result["valid"],

            duplicate,

            amount_validation["valid"]
        )

        # =====================================
        # FRAUD SCORE
        # =====================================

        raw_score = str(

            fraud.get(
                "fraud_probability",
                "0"
            )
        )

        match = re.search(

            r"\d+(\.\d+)?",

            raw_score
        )

        if match:

            fraud_score = int(

                float(
                    match.group()
                )
            )

        else:

            fraud_score = 0

        fraud_score = max(

            0,

            min(
                fraud_score,
                100
            )
        )

        # =====================================
        # SAVE DATABASE
        # =====================================

        save_invoice(

            data.get(
                "Invoice Number",
                ""
            ),

            data.get(
                "GSTIN",
                ""
            ),

            data.get(
                "Vendor Name",
                "Unknown"
            ),

            total_amount,

            fraud_score,

            fraud.get(
                "status",
                "Unknown"
            )
        )

        # =====================================
        # SAFE PDF NAME
        # =====================================

        safe_invoice = re.sub(

            r'[<>:"/\\\\|?*]',

            '',

            data.get(
                "Invoice Number",
                "invoice"
            )
        )

        safe_invoice = safe_invoice.strip()

        if not safe_invoice:

            safe_invoice = "invoice"

        # =====================================
        # CACHE REPORT DATA (PDF on demand)
        # =====================================

        report_cache[safe_invoice] = {
            "data": data,
            "fraud": fraud,
            "gst_validation": gst_validation,
            "gst_result": gst_result,
            "amount_validation": amount_validation
        }

        return templates.TemplateResponse(

    request,

    "report.html",

    {

        "fraud_score": fraud_score,

        "invoice_key": safe_invoice,

        "report": {

            "invoice": {

                "vendor":
                data.get(
                    "Vendor Name",
                    "Unknown"
                ),

                "gstin":
                data.get(
                    "GSTIN",
                    ""
                ),

                "invoice_number":
                data.get(
                    "Invoice Number",
                    ""
                ),

                "total":
                total_amount
            },

            "gst_validation":
            gst_validation.get(
                "message",
                ""
            ),

            "gst_api":
            gst_api.get(
                "status",
                ""
            ),

            "gst_rule_check":
            gst_result.get(
                "message",
                ""
            ),

            "fraud_analysis":
            fraud.get(
                "status",
                ""
            )
        },

        "image_path":
        image_path
    }
)
    except Exception as e:

        import traceback

        print("\n===== FULL ERROR =====\n")

        traceback.print_exc()

        print("\n======================\n")

        return f"""

        <html>

        <body
        style="
        background:#111827;
        color:white;
        font-family:Arial;
        padding:40px;
        ">

        <h1>
        Error Processing Invoice
        </h1>

        <br>

        <pre>
        {traceback.format_exc()}
        </pre>

        </body>

        </html>

        """

# =========================================
# GENERATE PDF ON DEMAND
# =========================================

@app.post(
    "/generate-report",
    response_class=FileResponse
)
async def generate_report(request: Request):

    try:

        form = await request.form()

        invoice_key = form.get(
            "invoice_key",
            "invoice"
        )

        cached = report_cache.get(invoice_key)

        if not cached:
            return HTMLResponse(
                "<h2>Report data expired. Please re-upload the invoice.</h2>",
                status_code=404
            )

        pdf_path = f"reports/{invoice_key}.pdf"

        generate_pdf(

            pdf_path,

            cached["data"],

            cached["fraud"],

            cached["gst_validation"],

            cached["gst_result"],

            cached["amount_validation"]
        )

        return FileResponse(

            pdf_path,

            media_type="application/pdf",

            filename=f"GSTVision_Report_{invoice_key}.pdf"
        )

    except Exception as e:

        import traceback
        traceback.print_exc()

        return HTMLResponse(
            f"<h2>Error generating report: {str(e)}</h2>",
            status_code=500
        )