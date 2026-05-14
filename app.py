# Fixed GSTVision AI FastAPI Code


from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

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

app = FastAPI()

init_db()

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


@app.get(
    "/",
    response_class=HTMLResponse
)
async def home():

    return open(
        "templates/index.html",
        encoding="utf-8"
    ).read()


@app.post(
    "/upload",
    response_class=HTMLResponse
)
async def upload_invoice(
    file: UploadFile = File(...)
):

    try:

        image_path = f"uploads/{file.filename}"

        with open(image_path, "wb") as f:

            f.write(await file.read())

        image = Image.open(image_path)

        text = extract_text(image)

        data = extract_invoice_llm(text)

        subtotal = clean_number(
            data.get("Subtotal", 0)
        )

        total_amount = clean_number(
            data.get("Total Amount", 0)
        )

        gst_amount = clean_number(
            data.get("GST Amount", 0)
        )

        gst_percentage = clean_number(
            data.get("GST Percentage", 0)
        )

        gst_validation = validate_gstin(
            data["GSTIN"]
        )

        gst_api = verify_gst_api(
            data["GSTIN"]
        )

        product = detect_product_category(text)

        gst_result = validate_gst_rate(
            product["expected_gst"],
            gst_percentage
        )

        amount_validation = validate_amounts(
            subtotal,
            gst_amount,
            total_amount
        )

        duplicate = detect_duplicate(
            data["Invoice Number"],
            data["GSTIN"]
        )

        fraud = predict_fraud(
            total_amount,
            gst_amount,
            gst_validation["valid"],
            gst_result["valid"],
            duplicate,
            amount_validation["valid"]
        )

        save_invoice(
            data['Invoice Number'],
            data['GSTIN'],
            data['Vendor Name'],
            total_amount,
            fraud['fraud_probability'],
            fraud['status']
        )

        pdf_path = f"reports/{data['Invoice Number']}.pdf"

        generate_pdf(
            pdf_path,
            data,
            fraud,
            gst_validation,
            gst_result,
            amount_validation
        )

        fraud_percent = float(
            fraud['fraud_probability'].replace('%', '')
        )

        circle = 565 - (
            565 * fraud_percent / 100
        )

        return f'''

        <html>

        <head>

        <title>
        GSTVision AI
        </title>

        <link
        rel="stylesheet"
        href="/static/style.css"
        >

        <script
        src="/static/app.js">
        </script>

        </head>

        <body>

        <div class="header">

        <h1>
        GSTVision AI
        </h1>

        <p>
        AI-Powered GST Fraud Detection System
        </p>

        <br>

        <button onclick="toggleDarkMode()">
        Toggle Dark Mode
        </button>

        </div>

        <div class="grid">

        <div class="card">
        <h2>
        AI Fraud Meter
        </h2>

        <svg width="220" height="220">

        <circle
        cx="110"
        cy="110"
        r="90"
        stroke="#e5e7eb"
        stroke-width="18"
        fill="none"
        />

        <circle
        cx="110"
        cy="110"
        r="90"
        stroke="#ef4444"
        stroke-width="18"
        fill="none"
        stroke-dasharray="565"
        stroke-dashoffset="{circle}"
        stroke-linecap="round"
        transform="rotate(-90 110 110)"
        />

        <text
        x="50%"
        y="50%"
        text-anchor="middle"
        dy="10"
        font-size="28"
        font-weight="bold"
        >
        {fraud['fraud_probability']}
        </text>

        </svg>

        </div>

        <div class="card">

        <h2>
        Invoice Details
        </h2>

        <div class="item">
        <b>Vendor</b>
        <span>{data['Vendor Name']}</span>
        </div>

        <div class="item">
        <b>GSTIN</b>
        <span>{data['GSTIN']}</span>
        </div>

        <div class="item">
        <b>Invoice Number</b>
        <span>{data['Invoice Number']}</span>
        </div>

        <div class="item">
        <b>Category</b>
        <span>{product['category']}</span>
        </div>

        <div class="item">
        <b>Subtotal</b>
        <span>₹ {subtotal}</span>
        </div>

        <div class="item">
        <b>GST Amount</b>
        <span>₹ {gst_amount}</span>
        </div>

        <div class="item">
        <b>Total</b>
        <span>₹ {total_amount}</span>
        </div>

        <div class="item">
        <b>GST Validation</b>
        <span>{gst_validation['message']}</span>
        </div>

        <div class="item">
        <b>GST API Status</b>
        <span>{gst_api.get('status', 'Not Verified')}</span>
        </div>

        <div class="item">
        <b>GST Rate Check</b>
        <span>{gst_result['message']}</span>
        </div>

        <div class="item">
        <b>Amount Validation</b>
        <span>{amount_validation['message']}</span>
        </div>

        <div class="item">
        <b>Duplicate Invoice</b>
        <span>{'Yes' if duplicate else 'No'}</span>
        </div>

        <div class="item">
        <b>Fraud Status</b>
        <span>{fraud['status']}</span>
        </div>

        <br>

        <a href="/{pdf_path}" target="_blank">
        <button>
        Download PDF Report
        </button>
        </a>

        </div>

        <div class="card">

        <h2>
        Invoice Preview
        </h2>

        <img
        src="/{image_path}"
        style="width:100%; border-radius:10px;"
        />

        </div>

        </div>

        </body>

        </html>

        '''

    except Exception as e:

        return f'''
        <html>
        <body>
        <h2>Error Processing Invoice</h2>
        <p>{str(e)}</p>
        </body>
        </html>
        '''


