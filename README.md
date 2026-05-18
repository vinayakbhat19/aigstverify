# GSTVision AI – Intelligent GST Invoice Verification System

An AI-powered GST invoice verification and fraud detection system built using Flask, OCR, Machine Learning, and Computer Vision.

---

## 🚀 Project Overview

GSTVision AI is designed to automate the verification of GST invoices by extracting invoice data using OCR, validating GST details, detecting anomalies, and generating intelligent risk analysis reports.

The system helps businesses and auditors identify:
- Fake invoices
- GST mismatches
- Tax calculation errors
- Fraudulent transactions
- Suspicious invoice patterns

---

## ✨ Features

- 📄 Invoice Upload & Processing
- 🔍 OCR-based Text Extraction using Tesseract
- 🧠 AI-Powered Risk Detection
- ✅ GSTIN Validation
- 📊 Interactive Dashboard & Analytics
- 📈 Fraud Probability Analysis
- 🧾 PDF Report Generation
- ⚡ Real-Time Invoice Verification
- 🎨 Modern Responsive UI
- 📂 Upload History & Reports

---

## 🛠️ Tech Stack

### Backend
- Python
- Flask

### AI / ML
- Scikit-learn
- Pandas
- NumPy

### OCR & Image Processing
- Tesseract OCR
- OpenCV
- Pillow

### Frontend
- HTML
- CSS
- JavaScript

### Database
- SQLite

---

## 📁 Project Structure

```text
aigstverify/
│
├── database/        # Database files
├── doc/             # Documentation and research papers
├── models/          # AI/ML models
├── reports/         # Generated reports
├── static/          # CSS, JS, images
├── templates/       # HTML templates
├── tessdata/        # OCR language data
├── uploads/         # Uploaded invoices
├── utils/           # Utility/helper functions
│
├── app.py           # Main Flask application
├── config.py        # Configuration settings
├── requirements.txt
├── README.md
└── .gitignore
