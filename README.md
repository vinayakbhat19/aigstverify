# GSTVision AI

Reads Indian GST invoices on your own machine, checks the GSTIN, works out the
GST rate, and scores the invoice for fraud. No invoice data leaves the machine
unless you configure a GSTIN registry API.

## How an invoice is processed

```text
image ─► OpenCV clean-up ─► Qwen3-VL-4B (local) ─► fields as JSON ─► checks ─► fraud score ─► report
         deskew, contrast,    vision-language model    with a confidence    │
         resize               reads the page            per field            ├─ GSTIN pattern, state code, check character
                                                                             ├─ GST registry (if an API is configured)
                                                                             ├─ GST rate for the items (by date and HSN)
                                                                             ├─ taxable value + GST = total
                                                                             ├─ duplicate (same number + GSTIN)
                                                                             └─ e-invoice / UPI QR code vs printed values
```

1. **OpenCV** straightens a tilted scan, evens out shadows and limits the image size.
2. **Qwen3-VL-4B-Instruct** (Apache-2.0) reads the image and returns the fields as JSON. It is told to copy values as printed and never calculate them, so a tampered total stays visible to the checks. Each field gets a confidence from the model's own token probabilities.
3. **Checks** run on the JSON. A check only *fails* when the values behind it were read with confidence ≥ 0.80; otherwise it is reported as *not checked*, so misreads are not called fraud.
4. **Fraud engine**: an XGBoost model trained on 20,000 generated genuine and fraudulent invoices turns the check results into a risk score. The report shows the main reasons from the model's own per-feature contributions (SHAP values).
5. **PDF**: built only when you press *Download PDF report*.

The earlier extractor (PaddleOCR + a fine-tuned LayoutLMv3, with an optional Gemini fallback) is still available with `EXTRACTOR=layoutlmv3`.

## Run it

Python 3.10–3.13 (on a Mac, use Python 3.12: newer versions lack some wheels).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Open http://localhost:8000. The first invoice downloads the model (about 9 GB) unless you download it first:

```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-VL-4B-Instruct')"
```

### Faster on a Mac: Ollama

The Hugging Face model runs on the Apple GPU (MPS) at 16-bit. Ollama runs a 4-bit version, which needs about 3–4 GB of memory and is usually faster on a MacBook Air:

```bash
ollama pull qwen3-vl:4b
VLM_BACKEND=ollama python -m uvicorn app:app --reload
```

## Settings (environment variables)

| Variable | Default | What it does |
| --- | --- | --- |
| `EXTRACTOR` | `vlm` | `vlm` (Qwen3-VL) or `layoutlmv3` (PaddleOCR + LayoutLMv3) |
| `VLM_BACKEND` | `transformers` | `transformers` or `ollama` |
| `VLM_MODEL` | `Qwen/Qwen3-VL-4B-Instruct` (`qwen3-vl:4b` for Ollama) | any Qwen3-VL size |
| `VLM_DEVICE` | auto | `mps`, `cuda` or `cpu` |
| `VLM_MAX_SIDE` | `1280` | longest image side in pixels; smaller is faster |
| `EXTRACTION_MIN_CONFIDENCE` | `0.80` | below this a field is not used as fraud evidence |
| `GST_API_URL`, `GST_API_KEY`, `GST_API_KEY_HEADER` | unset | GSTIN registry lookup through a GSTIN verification provider; `GST_API_URL` contains `{gstin}` |
| `BATCH_CONCURRENCY` | `1` | invoices processed at once |

## Project layout

```text
app.py                       FastAPI app: upload, batch upload, report, PDF
utils/vlm_extractor.py       OpenCV clean-up + Qwen3-VL extraction with per-field confidence
utils/pipeline.py            chooses the extractor, cleans and reconciles amounts, reviews the result
utils/validator.py           GSTIN pattern, state code and mod-36 check character
utils/gst_api.py             GSTIN registry lookup (only when configured)
utils/gst_rates.py           expected rates by item, HSN chapter and date (22 Sept 2025 rate change)
utils/qr_validator.py        e-invoice (signed JWT) and UPI QR codes vs printed values
utils/fraud.py               fraud features, XGBoost scoring, SHAP reasons
scripts/train_fraud_model.py trains models/fraud_model.json on generated cases
scripts/generate_invoices.py synthetic annotated GST invoices (for LayoutLMv3 and testing)
scripts/train_layoutlmv3.py  fine-tunes LayoutLMv3 (the alternative extractor)
```

## Limits

- The fraud model learns from simulated fraud patterns, not real fraud cases; retrain it with real labelled invoices when you have them.
- The rate table is a screening aid. The legal rate is the one notified for each HSN/SAC code; unknown items skip the rate check.
- The QR check compares values but does not verify the e-invoice signature (that needs the portal's public key).
- Without `GST_API_URL` the registry check reports *Not checked*: the checksum proves a GSTIN is well-formed, not that it is registered.
