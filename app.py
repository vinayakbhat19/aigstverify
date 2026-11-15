"""GSTVision AI: FastAPI app for GST invoice extraction, validation and fraud scoring."""

import asyncio
import html
import os
import re
import time
import traceback
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image

from utils.amount_validator import validate_amounts
from utils.database import init_db, save_invoice
from utils.duplicate_detector import detect_duplicate
from utils.fraud import predict_fraud
from utils.gst_api import verify_gst_api
from utils.gst_rate_validator import validate_gst_rate
from utils.pipeline import extract_invoice
from utils.product_classifier import detect_product_category
from utils.report_generator import generate_pdf
from utils.validator import validate_gstin

app = FastAPI()
templates = Jinja2Templates(directory="templates")
init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

# Report data kept in memory so the PDF can be built on demand.
report_cache = {}

MAX_BATCH = int(os.getenv("MAX_BATCH", "20"))
# OCR and the layout model already use several CPU threads each, so running
# many invoices at once only makes them fight for cores.
_extraction_slots = asyncio.Semaphore(int(os.getenv("BATCH_CONCURRENCY", "2")))
# Duplicate check and save must not interleave between invoices.
_db_lock = asyncio.Lock()


def clean_number(value) -> float:
    try:
        return float(str(value).replace("%", "").replace(",", "").replace("₹", "").strip())
    except ValueError:
        return 0.0


def safe_name(text: str, fallback: str) -> str:
    """File-system-safe name; never contains a path separator."""
    return re.sub(r"[^A-Za-z0-9._ -]", "", Path(str(text)).name).strip(" .") or fallback


async def store_upload(file: UploadFile) -> str:
    """Saves the upload under a unique name, so callers cannot choose the path."""
    name = f"{uuid.uuid4().hex[:8]}_{safe_name(file.filename or '', 'invoice')}"
    path = f"uploads/{name}"
    content = await file.read()
    await asyncio.to_thread(Path(path).write_bytes, content)
    return path


def _extract(image_path: str):
    with Image.open(image_path) as image:
        image.load()
        return extract_invoice(image)


async def analyse(image_path: str) -> dict:
    """Runs the whole pipeline for one stored invoice image."""
    started = time.perf_counter()

    # Extraction is CPU-heavy: run it off the event loop, a few at a time.
    async with _extraction_slots:
        data, text = await asyncio.to_thread(_extract, image_path)
    extracted_at = time.perf_counter()

    gstin = data.get("GSTIN", "")
    invoice_number = data.get("Invoice Number", "")
    subtotal = clean_number(data.get("Subtotal", 0))
    total_amount = clean_number(data.get("Total Amount", 0))
    gst_amount = clean_number(data.get("GST Amount", 0))
    gst_percentage = clean_number(data.get("GST Percentage", 0))

    # The two checks that can touch the network run side by side.
    gst_api, product = await asyncio.gather(
        asyncio.to_thread(verify_gst_api, gstin),
        asyncio.to_thread(detect_product_category, text, data.get("Category", "")),
    )
    gst_validation = validate_gstin(gstin)
    gst_result = validate_gst_rate(product.get("expected_gst", 18), gst_percentage)
    amount_validation = validate_amounts(subtotal, gst_amount, total_amount)

    async with _db_lock:
        duplicate = detect_duplicate(invoice_number, gstin)
        fraud = predict_fraud(total_amount, gst_amount, gst_validation["valid"],
                              gst_result["valid"], duplicate, amount_validation["valid"])
        match = re.search(r"\d+(\.\d+)?", str(fraud.get("fraud_probability", "0")))
        fraud_score = max(0, min(int(float(match.group())) if match else 0, 100))
        save_invoice(invoice_number, gstin, data.get("Vendor Name", "Unknown"),
                     total_amount, fraud_score, fraud.get("status", "Unknown"))

    # The upload's unique prefix keeps keys distinct when invoice numbers repeat.
    invoice_key = f"{safe_name(invoice_number, 'invoice')}_{Path(image_path).name[:8]}"
    report_cache[invoice_key] = {
        "data": data, "fraud": fraud, "gst_validation": gst_validation,
        "gst_result": gst_result, "amount_validation": amount_validation,
    }
    finished = time.perf_counter()
    return {
        "invoice_key": invoice_key,
        "image_path": image_path,
        "data": data,
        "total_amount": total_amount,
        "fraud_score": fraud_score,
        "fraud": fraud,
        "duplicate": duplicate,
        "gst_validation": gst_validation,
        "gst_api": gst_api,
        "gst_result": gst_result,
        "amount_validation": amount_validation,
        "category": product.get("category", ""),
        "seconds": {"extraction": round(extracted_at - started, 2),
                    "checks": round(finished - extracted_at, 2),
                    "total": round(finished - started, 2)},
    }


def error_page(message: str, status_code: int = 500) -> HTMLResponse:
    return HTMLResponse(
        f"""<html><body style="background:#111827;color:white;font-family:Arial;padding:40px;">
        <h1>Error Processing Invoice</h1><br><pre>{html.escape(message)}</pre>
        <p><a href="/" style="color:#93c5fd">Back</a></p></body></html>""",
        status_code=status_code)


@app.get("/", response_class=HTMLResponse)
async def home():
    return Path("templates/index.html").read_text(encoding="utf-8")


@app.post("/upload", response_class=HTMLResponse)
async def upload_invoice(request: Request, file: UploadFile = File(...)):
    try:
        result = await analyse(await store_upload(file))
    except Exception as error:
        traceback.print_exc()
        return error_page(f"{type(error).__name__}: {error}")

    data = result["data"]
    return templates.TemplateResponse(request, "report.html", {
        "fraud_score": result["fraud_score"],
        "invoice_key": result["invoice_key"],
        "report": {
            "invoice": {
                "vendor": data.get("Vendor Name", "Unknown"),
                "gstin": data.get("GSTIN", ""),
                "invoice_number": data.get("Invoice Number", ""),
                "total": result["total_amount"],
            },
            "gst_validation": result["gst_validation"].get("message", ""),
            "gst_api": result["gst_api"].get("status", ""),
            "gst_rule_check": result["gst_result"].get("message", ""),
            "fraud_analysis": result["fraud"].get("status", ""),
        },
        "image_path": result["image_path"],
    })


@app.post("/upload-batch")
async def upload_batch(files: List[UploadFile] = File(...)):
    """Processes several invoices concurrently. One bad file does not fail the batch."""
    if len(files) > MAX_BATCH:
        return {"error": f"At most {MAX_BATCH} invoices per batch", "results": []}
    started = time.perf_counter()

    async def one(file: UploadFile) -> dict:
        try:
            result = await analyse(await store_upload(file))
        except Exception as error:
            traceback.print_exc()
            return {"file": file.filename, "ok": False, "error": f"{type(error).__name__}: {error}"}
        data = result["data"]
        return {
            "file": file.filename,
            "ok": True,
            "invoice_key": result["invoice_key"],
            "vendor": data.get("Vendor Name", "Unknown"),
            "gstin": data.get("GSTIN", ""),
            "invoice_number": data.get("Invoice Number", ""),
            "invoice_date": data.get("Invoice Date", ""),
            "subtotal": clean_number(data.get("Subtotal", 0)),
            "gst_amount": clean_number(data.get("GST Amount", 0)),
            "gst_percentage": clean_number(data.get("GST Percentage", 0)),
            "total": result["total_amount"],
            "category": result["category"],
            "fraud_score": result["fraud_score"],
            "status": result["fraud"].get("status", ""),
            "risk_level": result["fraud"].get("risk_level", ""),
            "reasons": result["fraud"].get("reasons", []),
            "duplicate": result["duplicate"],
            "gstin_check": result["gst_validation"].get("message", ""),
            "rate_check": result["gst_result"].get("message", ""),
            "amount_check": result["amount_validation"].get("message", ""),
            "extraction_source": data.get("Extraction Source", ""),
            "fallback_reasons": data.get("Fallback Reasons", []),
            "seconds": result["seconds"],
        }

    results = await asyncio.gather(*(one(file) for file in files))
    return {
        "count": len(results),
        "succeeded": sum(r["ok"] for r in results),
        "seconds": round(time.perf_counter() - started, 2),
        "results": results,
    }


@app.post("/generate-report", response_class=FileResponse)
async def generate_report(request: Request):
    form = await request.form()
    invoice_key = safe_name(form.get("invoice_key", "invoice"), "invoice")
    cached = report_cache.get(invoice_key)
    if not cached:
        return HTMLResponse("<h2>Report data expired. Please re-upload the invoice.</h2>", status_code=404)
    try:
        pdf_path = f"reports/{invoice_key}.pdf"
        await asyncio.to_thread(generate_pdf, pdf_path, cached["data"], cached["fraud"],
                                cached["gst_validation"], cached["gst_result"], cached["amount_validation"])
        return FileResponse(pdf_path, media_type="application/pdf",
                            filename=f"GSTVision_Report_{invoice_key}.pdf")
    except Exception as error:
        traceback.print_exc()
        return HTMLResponse(f"<h2>Error generating report: {html.escape(str(error))}</h2>", status_code=500)
