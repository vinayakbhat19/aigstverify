"""GSTVision AI: FastAPI app for GST invoice extraction, validation and fraud scoring."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
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
from utils.fraud import build_features, predict_fraud
from utils.gst_api import verify_gst_api
from utils.gst_rate_validator import validate_gst_rate
from utils.pipeline import extract_invoice
from utils.product_classifier import detect_product_category
from utils.qr_validator import validate_qr
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
# Same threshold the extractor uses to decide whether to trust a field.
MIN_FIELD_CONFIDENCE = float(os.getenv("EXTRACTION_MIN_CONFIDENCE", "0.80"))
# OCR and the layout model each use every CPU core already. Measured on a 4-core
# CPU, running two invoices at once took 46s for five invoices against 10s one at
# a time, so the default is one. Raise it only on a GPU or a many-core machine.
_extraction_slots = asyncio.Semaphore(int(os.getenv("BATCH_CONCURRENCY", "1")))
# All model work happens on these threads, so the OCR and PyTorch thread pools
# are always created and used from the same place.
_extraction_pool = ThreadPoolExecutor(max_workers=int(os.getenv("BATCH_CONCURRENCY", "1")),
                                      thread_name_prefix="extract")
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


def _scan_qr(image_path, gstin, invoice_number, total, invoice_date):
    with Image.open(image_path) as image:
        return validate_qr(image, gstin, invoice_number, total, invoice_date)


_COMPANY_WORDS = re.compile(r"\b(m/?s|messrs|pvt|private|ltd|limited|llp|co|company|and|the|india|enterprises?|traders?)\b")


def _name_tokens(name: str) -> set:
    return {t for t in re.sub(r"[^a-z0-9 ]", " ", _COMPANY_WORDS.sub(" ", str(name).lower())).split() if len(t) > 1}


def names_match(vendor: str, registry: dict):
    """True/False when the printed vendor name is/isn't the registered legal or trade name; None if unknown."""
    printed = _name_tokens(vendor)
    registered = [_name_tokens(registry.get(key, "")) for key in ("legal_name", "trade_name")]
    registered = [tokens for tokens in registered if tokens]
    if not printed or not registered:
        return None
    return any(len(printed & tokens) / min(len(printed), len(tokens)) >= 0.5 for tokens in registered)


def read_reliably(data: dict, *fields) -> tuple:
    """(reliable, lowest confidence) for the named fields of a local-model read.

    Values re-read by Gemini carry no per-field confidence and count as reliable.
    """
    confidence = data.get("Field Confidence") or {}
    if data.get("Extraction Source") == "gemini" or not confidence:
        return True, 1.0
    lowest = min(confidence.get(field, 0.0) for field in fields)
    return lowest >= MIN_FIELD_CONFIDENCE, lowest


def build_checks(gstin_check, registry, name_match, rate_check, amount_check, duplicate, qr_check):
    """(name, state, detail) for the report; state is "pass", "fail" or "skip"."""
    if gstin_check.get("missing") or gstin_check.get("uncertain"):
        gstin_state = "skip"
    else:
        gstin_state = "pass" if gstin_check["valid"] else "fail"
    checks = [
        ("GSTIN", gstin_state, gstin_check["message"]),
        ("GST registry", registry.get("state", "skip"), registry.get("message", "")),
    ]
    if name_match is not None:
        checks.append(("Registered name", "pass" if name_match else "fail",
                       "Vendor name matches the registry" if name_match else
                       f"Printed vendor name differs from the registered name "
                       f"({registry.get('legal_name') or registry.get('trade_name')})"))
    checks += [
        ("GST rate", rate_check["state"], rate_check["message"]),
        ("Totals add up", amount_check["state"], amount_check["message"]),
        ("Not a duplicate", "fail" if duplicate else "pass",
         "Already seen with the same GSTIN and invoice number" if duplicate else
         "First time this invoice is seen"),
        ("QR code", qr_check["state"], qr_check["message"]),
    ]
    return checks


def _extract(image_path: str):
    with Image.open(image_path) as image:
        image.load()
        return extract_invoice(image)


async def analyse(image_path: str) -> dict:
    """Runs the whole pipeline for one stored invoice image."""
    queued_at = time.perf_counter()

    # Extraction is CPU-heavy: run it off the event loop, a few at a time.
    async with _extraction_slots:
        started = time.perf_counter()
        data, text = await asyncio.get_running_loop().run_in_executor(_extraction_pool, _extract, image_path)
    extracted_at = time.perf_counter()

    gstin = data.get("GSTIN", "")
    invoice_number = data.get("Invoice Number", "")
    invoice_date = data.get("Invoice Date", "")
    subtotal = clean_number(data.get("Subtotal", 0))
    total_amount = clean_number(data.get("Total Amount", 0))
    gst_amount = clean_number(data.get("GST Amount", 0))
    gst_percentage = clean_number(data.get("GST Percentage", 0))

    # Registry lookup, category and QR scan are independent: run them side by side.
    gst_api, product, qr_check = await asyncio.gather(
        asyncio.to_thread(verify_gst_api, gstin),
        asyncio.to_thread(detect_product_category, text, data.get("Detected Products"), invoice_date,
                          data.get("HSN Codes")),
        asyncio.to_thread(_scan_qr, image_path, gstin, invoice_number, total_amount, invoice_date),
    )
    gst_validation = validate_gstin(gstin)
    gst_result = validate_gst_rate(product.get("expected_rates"), gst_percentage, product.get("category", ""))
    amount_validation = validate_amounts(subtotal, gst_amount, total_amount)

    # A failed check is evidence of fraud only if the values behind it were read
    # reliably; otherwise it is far more likely to be a misread.
    gstin_reliable, gstin_conf = read_reliably(data, "vendor_gstin")
    if not gst_validation["valid"] and not gst_validation["missing"] and not gstin_reliable:
        gst_validation = {**gst_validation, "uncertain": True,
                          "message": f"{gst_validation['message']}; but the GSTIN was read with low confidence "
                                     f"({gstin_conf:.2f}), so compare it with the invoice by eye"}
    amounts_reliable, amounts_conf = read_reliably(data, "taxable_value", "gst_amount", "total_amount")
    total_reliable, _ = read_reliably(data, "total_amount")
    if not amounts_reliable:
        note = f"amounts were read with low confidence ({amounts_conf:.2f})"
        if amount_validation["state"] == "fail":
            amount_validation = {**amount_validation, "state": "skip", "valid": True,
                                 "message": amount_validation["message"] + f"; not judged because the {note}"}
        if gst_result["state"] == "fail":
            gst_result = {**gst_result, "state": "skip", "valid": True,
                          "message": gst_result["message"] + f"; not judged because the rate came from {note}"}
    name_match = names_match(data.get("Vendor Name", ""), gst_api) if gst_api.get("state") == "pass" else None

    async with _db_lock:
        duplicate = detect_duplicate(invoice_number, gstin)
        checks = build_checks(gst_validation, gst_api, name_match, gst_result, amount_validation,
                              duplicate, qr_check)
        features = build_features(gstin_check=gst_validation, registry=gst_api, rate_check=gst_result,
                                  taxable=subtotal if amounts_reliable else 0,
                                  gst=gst_amount if amounts_reliable else 0,
                                  total=total_amount if total_reliable else 0, duplicate=duplicate,
                                  qr_check=qr_check, invoice_date=invoice_date, name_match=name_match)
        missing = [label for label, value in (("GSTIN", gstin), ("Invoice number", invoice_number),
                                              ("Taxable value", subtotal), ("GST amount", gst_amount),
                                              ("Total", total_amount)) if not value]
        fraud = predict_fraud(features, total_amount,
                              [detail for _, state, detail in checks if state == "fail"], missing)
        fraud_score = fraud["score"]
        save_invoice(invoice_number, gstin, data.get("Vendor Name", "Unknown"),
                     total_amount, fraud_score, fraud.get("status", "Unknown"))

    # The upload's unique prefix keeps keys distinct when invoice numbers repeat.
    invoice_key = f"{safe_name(invoice_number, 'invoice')}_{Path(image_path).name[:8]}"
    report_cache[invoice_key] = {
        "data": data, "fraud": fraud, "gst_validation": gst_validation,
        "gst_result": gst_result, "amount_validation": amount_validation, "checks": checks,
    }
    finished = time.perf_counter()
    print(f"[invoice] {Path(image_path).name}: read by {data.get('Extraction Source', '?')} in "
          f"{finished - queued_at:.1f}s | vendor={data.get('Vendor Name')!r} gstin={gstin!r} "
          f"no={invoice_number!r} date={data.get('Invoice Date')!r} taxable={subtotal} gst={gst_amount} "
          f"rate={gst_percentage} total={total_amount} | fraud={fraud_score}%"
          + (f" | why not trusted: {'; '.join(data.get('Fallback Reasons') or [])}" if data.get("Fallback Reasons") else ""),
          flush=True)
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
        "checks": checks,
        "qr": qr_check,
        "seconds": {"queued": round(started - queued_at, 2),
                    "extraction": round(extracted_at - started, 2),
                    "checks": round(finished - extracted_at, 2),
                    "total": round(finished - queued_at, 2)},
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
    fraud = result["fraud"]
    source = data.get("Extraction Source", "")
    return templates.TemplateResponse(request, "report.html", {
        "invoice_key": result["invoice_key"],
        "image_path": result["image_path"],
        "score": result["fraud_score"],
        "status": fraud.get("status", ""),
        "risk_level": fraud.get("risk_level", ""),
        "assessment": fraud.get("final_assessment", ""),
        "invoice": {
            "vendor": data.get("Vendor Name") or "Unknown",
            "gstin": data.get("GSTIN") or "Not found",
            "number": data.get("Invoice Number") or "Not found",
            "date": data.get("Invoice Date") or "Not found",
            "buyer": data.get("Buyer Name") or "",
            "buyer_gstin": data.get("Buyer GSTIN") or "",
            "category": result["category"] or "General",
            "subtotal": clean_number(data.get("Subtotal", 0)),
            "gst_amount": clean_number(data.get("GST Amount", 0)),
            "gst_rate": clean_number(data.get("GST Percentage", 0)),
            "total": result["total_amount"],
        },
        "checks": result["checks"],
        "gst_api": result["gst_api"].get("status", ""),
        "drivers": fraud.get("drivers", []),
        "warnings": fraud.get("warnings", []),
        "source": {"vlm": "Qwen3-VL (local)", "vlm-unverified": "Qwen3-VL (local), unverified",
                   "layoutlmv3": "LayoutLMv3 (local)", "gemini": "Gemini (fallback)",
                   "layoutlmv3-unverified": "LayoutLMv3 (local), unverified",
                   "none": "Not read"}.get(source, source),
        "fallback_reasons": data.get("Fallback Reasons", []),
        "cleanup": data.get("Image Clean-up") or [],
        "seconds": result["seconds"],
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
            "checks": [{"name": n, "state": st, "detail": d} for n, st, d in result["checks"]],
            "registry": result["gst_api"].get("status", ""),
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
                                cached["gst_validation"], cached["gst_result"], cached["amount_validation"],
                                cached.get("checks"))
        return FileResponse(pdf_path, media_type="application/pdf",
                            filename=f"GSTVision_Report_{invoice_key}.pdf")
    except Exception as error:
        traceback.print_exc()
        return HTMLResponse(f"<h2>Error generating report: {html.escape(str(error))}</h2>", status_code=500)
