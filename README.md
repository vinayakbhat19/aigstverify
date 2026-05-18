# GSTVision AI – Intelligent GST Invoice Verification System

An advanced AI-powered GST invoice verification and fraud detection system designed to automate compliance checks, extract structured data, and detect anomalies. Built using **FastAPI**, **Google Generative AI (Gemini)**, **Tesseract OCR**, and **Machine Learning**.

---

## 🚀 Project Overview

GSTVision AI streamlines the auditing and verification of Indian GST invoices. It leverages a hybrid approach—combining state-of-the-art Large Language Models (LLMs) with robust OCR, regex fallbacks, and Machine Learning models—to identify:
- Fake or tampered invoices
- GSTIN format violations and mismatches
- Tax calculation errors (Subtotal vs Total)
- Dynamic GST rate anomalies (CGST/SGST/IGST mapping)
- Fraudulent transaction patterns and duplicate invoices

---

## ✨ Key Features

- **📄 Hybrid Invoice Data Extraction**: Uses **Gemini 2.5 Flash/Vision** for structured extraction, augmented by rigorous regex and arithmetic fallback validation to ensure maximum accuracy.
- **🔍 Smart OCR Augmentation**: Integrates **Tesseract OCR** with automated positional correction logic to fix common character misinterpretations (e.g., digit/letter confusion like O/0, I/1) in GSTINs.
- **📊 Dynamic GST Rate Detection**: A format-agnostic system that handles varied tax formats (IGST/CGST/SGST) and maps them to standard Indian GST slabs (0%, 3%, 5%, 12%, 18%, 28%).
- **🧠 ML-Powered Fraud Prediction**: A custom `Scikit-Learn` model evaluates multiple risk vectors (amounts, GST mismatches, duplicates) to generate a concrete fraud probability score.
- **🏷️ AI-Driven Categorization**: Uses intent mapping for accurate categorical classification of invoices rather than relying on fragile, hard-coded keyword lists.
- **✅ GSTIN & Amount Validation**: Ensures rigorous statutory compliance and detects mathematical discrepancies.
- **🧾 PDF Report Generation**: Automatically generates downloadable PDF compliance and risk analysis reports on demand.
- **⚡ Fast API Backend**: Built with **FastAPI** for asynchronous, high-performance request handling.
- **🎨 Interactive Dashboard**: A responsive modern UI for uploading invoices and viewing real-time verification results.

---

## 🛠️ Tech Stack

### Backend & API
- **Python 3**
- **FastAPI** & **Uvicorn**
- **Jinja2** (Templates)

### AI, ML & Extraction
- **Google Generative AI (Gemini 2.5 Flash)**
- **Scikit-learn**, **Pandas**, **NumPy**
- **Joblib** (Model loading)

### OCR & Image Processing
- **Tesseract OCR** (`pytesseract`)
- **Pillow (PIL)**

### Frontend
- **HTML5**, **CSS3**, **JavaScript**

### Database
- **SQLite3**

---

## 📁 Project Structure

```text
GSTVision_AI/
│
├── database/        # SQLite database files
├── models/          # Trained AI/ML models (fraud_model.pkl)
├── reports/         # Generated PDF reports
├── static/          # CSS, JS, and image assets
├── templates/       # HTML templates for the UI
├── uploads/         # Uploaded invoice images
├── utils/           # Core logic (LLM extraction, validation, ML fraud detection)
│   ├── llm_extractor.py
│   ├── ocr.py
│   ├── fraud.py
│   ├── amount_validator.py
│   ├── gst_rate_validator.py
│   └── ...
│
├── app.py           # Main FastAPI application
├── config.py        # API Keys configuration
└── README.md        # Project documentation
```

---

## ⚙️ Setup & Installation

### 1. Prerequisites
- **Python 3.8+** installed on your system.
- **Tesseract OCR** installed. 
  - *Windows*: Download from [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) and ensure it's added to your system `PATH`.
  - *Linux*: `sudo apt install tesseract-ocr`
  - *Mac*: `brew install tesseract`

### 2. Clone the Repository
```bash
git clone <your-repository-url>
cd GSTVision_AI
```

### 3. Install Dependencies
Install the required Python packages (ensure you are in a virtual environment if preferred):
```bash
pip install fastapi uvicorn google-generativeai pytesseract Pillow scikit-learn pandas numpy python-multipart jinja2
```

### 4. Configuration
Open `config.py` and add your valid API Keys:
```python
GEMINI_API_KEY = "your_gemini_api_key_here"
GST_API_KEY = "your_gst_api_key_here"
```

### 5. Run the Application
Start the FastAPI server using Uvicorn:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```
- Open your browser and navigate to `http://localhost:8000` to access the application.

---

## 🤝 Contributing
Contributions are welcome! Feel free to open an issue or submit a Pull Request if you'd like to improve the extraction logic, enhance the ML models, or build new features.
