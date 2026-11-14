# Synthetic Indian GST invoice dataset

300 generated invoices with word-level annotations, for fine-tuning a
layout-aware token classifier (LayoutLMv3, LiLT) to extract GST invoice fields.
Every company, person, GSTIN and amount is fictional.

## Regenerate

```bash
pip install -r requirements-datagen.txt
```

```bash
playwright install chromium
```

```bash
python scripts/generate_invoices.py --count 300 --output data/synthetic
```

The same `--seed` (default 42) gives the same invoices. Pixels can differ
slightly between machines because fonts and Chromium versions differ; the
templates fall back to a default sans-serif font when a named font is missing.

To check annotations by eye:

```bash
python scripts/preview_annotations.py data/synthetic/annotations/invoice_0001.json preview.png
```

## Layout

```text
data/synthetic/
  images/invoice_0001.jpg        clean renders are .png, degraded ones .jpg
  annotations/invoice_0001.json  one record per invoice
  train.jsonl  val.jsonl  test.jsonl   the same records, one per line
  labels.json                    label list, index = class id
  dataset_info.json              counts per split, layout, category, entity
```

## Record format

```json
{
  "id": "invoice_0001",
  "image": "images/invoice_0001.jpg",
  "width": 1295, "height": 1789,
  "split": "train",
  "words":     ["GSTIN", "No.:", "10NPOFZ0438W1Z5", "..."],
  "bboxes":    [[312, 124, 385, 135], "..."],
  "bboxes_px": [[404.1, 221.8, 498.6, 241.5], "..."],
  "labels":    ["O", "O", "B-VENDOR_GSTIN", "..."],
  "fields":    {"vendor_gstin": "10NPOFZ0438W1Z5", "total_amount": 16166.0, "...": "..."},
  "meta":      {"template": "classic", "b2b": true, "degradations": ["warp", "noise", "jpeg87"]}
}
```

- `bboxes` are `[x0, y0, x1, y1]` normalised to 0-1000, which is what the
  LayoutLMv3 processor expects. `bboxes_px` are the same boxes in image pixels.
- `words` are in reading order (top to bottom, left to right), as an OCR engine
  would emit them.
- `labels` use IOB2. `fields` holds the canonical values, independent of how
  they are printed, for end-to-end scoring.

## Labels

| Entity | What is labelled |
| --- | --- |
| `VENDOR_NAME`, `VENDOR_GSTIN` | The seller. The name is labelled wherever it is printed, including the "For ..." signature line. |
| `BUYER_NAME`, `BUYER_GSTIN` | The recipient. Absent on many retail bills. |
| `INVOICE_NO`, `INVOICE_DATE` | Order numbers and order dates are not labelled. |
| `ITEM_DESC`, `HSN` | One entity per line item. Quantity, unit price and line amount are not labelled. |
| `TAXABLE_VALUE` | Invoice-level pre-tax total only, not line amounts. |
| `CGST_AMOUNT`, `SGST_AMOUNT`, `IGST_AMOUNT` | Invoice-level total of each tax. On invoices with several rates, the per-rate amounts are left as `O` and only the total row is labelled. |
| `CGST_RATE`, `SGST_RATE`, `IGST_RATE` | Every printed component rate (summary lines, per-item columns, HSN summary). The combined rate is CGST + SGST. |
| `TOTAL_AMOUNT` | Final payable amount, after round-off. |

## What varies

- **Layouts (8):** bordered classic, Tally-style, modern, marketplace, thermal
  receipt, service letterhead, bill book, and a per-item tax-column layout.
  The last one (`columnar`) appears only in the test split, so test scores on
  it measure generalisation to an unseen layout. `meta.template` lets you
  score seen and unseen layouts separately.
- **Content:** 10 business categories, B2B and retail, 18 states, intra-state
  (CGST + SGST) and inter-state (IGST) supply, single- and mixed-rate
  invoices, discounts, round-off.
- **Wording and format:** caption variants ("Invoice No" / "Bill No" / "Inv
  No"), date formats, Indian digit grouping, currency prefixes, fonts.
- **Image quality:** about two thirds of images are degraded with rotation,
  perspective, shadows, blur, noise, fading, low resolution and JPEG
  compression. Word boxes follow the geometry.

## Known limits

- GSTINs have valid checksums and state codes, but belong to nobody.
- GST rates are indicative. Invoices dated before 22 September 2025 use the
  older slabs (0/3/5/12/18/28) and later ones the simplified slabs. Do not use
  the catalogue as a rate reference.
- English only; no handwriting, stamps, logos or QR codes.
- Word boxes come from the renderer, not from OCR. Real OCR output splits and
  merges words differently and makes character errors, so re-OCR the images and
  align the labels before the final fine-tune.
- A model trained only on this data will lean on these eight layouts. Measure
  on hand-labelled real invoices before trusting any accuracy number.

## OCR-aligned copy (`data/synthetic_ocr`)

`data/synthetic` has exact word boxes from the renderer. At inference the model
sees OCR output instead, so `data/synthetic_ocr` holds the same invoices with
words and boxes from the app's OCR (`utils/ocr.py`) and labels carried over by
box overlap:

```bash
python scripts/ocr_align.py --input data/synthetic --output data/synthetic_ocr
```

Records have the same fields plus `ocr_scores`; `image` points back into
`data/synthetic/images`. Train on this copy:

```bash
python scripts/train_layoutlmv3.py --data data/synthetic_ocr --output models/layoutlmv3-gst
```

Differences from the exact copy that the model has to cope with:

- OCR sometimes glues neighbouring words ("NumberTX/9792/23-24"), so a labelled
  word can carry a few caption characters. Clean values after extraction.
- Characters are misread (O/0, I/1), so labelled text does not always equal the
  ground truth in `fields`. `alignment_info.json` records how often the vendor
  GSTIN and invoice number were read exactly.
- Word boxes are estimated from line boxes by character count, so they are
  approximate.
