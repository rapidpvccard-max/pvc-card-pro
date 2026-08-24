# PVC Card Pro (Python Edition)

PVC Card Pro is an enterprise-grade utility that extracts data from standard encrypted Aadhaar PDF files and generates high-resolution, print-ready PVC cards (CR80) mapped gracefully across local language boundaries.

## Features
- **Local Layout Mapping**: Seamless Unicode support for English, Hindi, Gujarati, and Telugu text.
- **Native Data Preservation**: Lossless extraction of the original demographic photo and verifiable QR code payload without mutating data.
- **High Resolution Outputs**: Exact 1016 × 638 pixel outputs designed for standard 300 DPI CR80 PVC printers.
- **Print-Ready PDFs**: Generates automated A4 multi-card sheet layouts (2 columns × 5 rows) configured for automatic long-edge duplex printing.

## Prerequisites
- Python 3.9+
- Windows (Recommended) or Linux/macOS
- Valid Aadhaar PDF (supports encrypted files via password)

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd PVC_Python_Tool
   ```

2. **Create a Virtual Environment:**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Browser Engine (Playwright):**
   The application uses Chromium for deterministic pixel-perfect HTML-to-PNG rendering.
   ```bash
   playwright install chromium
   ```

## Running the Server

Start the internal Uvicorn server:
```bash
python -m uvicorn app:app --reload
```
Navigate to `http://localhost:8000/` in your web browser to access the application.

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | API liveness check |
| `POST`| `/upload` | Legacy endpoint to store PDFs (isolated to `/uploads`) |
| `POST`| `/extract`| Extracts canonical JSON mappings and original base64 imagery directly from the PDF |
| `POST`| `/generate`| Orchestrates full extraction + rendering to produce PVC Front and Back PNGs |
| `POST`| `/generate-a4`| Packages existing Front/Back runs into a 300DPI layout PDF for physical printing |

## Security Notes
- **Privacy First**: Files are never stored permanently. Generated outputs are logically isolated by unique UUID run paths.
- **No Logging**: Sensitive variables (Aadhaar numbers, payload bytes, passwords) are restricted from standard output and filesystem trails.
- **Network Safe**: Extraction and decoding run strictly locally. No AI, OCR, or third-party web translation services are integrated.

## Testing
Run the automated pipeline integrations directly:
```bash
python test_full_pipeline.py
python test_a4_print.py
```
*(Requires active development PDFs placed appropriately for tests)*

## Documentation
- `engine/aadhaar_extractor.py`: The powerhouse core extraction algorithm.
- `engine/card_renderer.py`: Translates canonical dictionaries into CSS/HTML layouts and controls Chromium.
- `engine/data_mapper.py`: Connects raw extraction schemas to the rendering payload.
- `engine/qr_recovery.py`: Extracts and rescues untampered QR candidate bytes.
- `engine/a4_print.py`: Assembles 1016x638 runs into exact A4 prints via PIL.
