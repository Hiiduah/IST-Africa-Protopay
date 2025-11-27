import json
from pathlib import Path
from typing import Dict, Any

import pdfplumber
import pytesseract
from PIL import Image


def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception:
        text = ""
    return text


def extract_text_from_image(file_path: str) -> str:
    try:
        img = Image.open(file_path)
        return pytesseract.image_to_string(img)
    except Exception:
        return ""


def extract_proforma_metadata(file_path: str) -> Dict[str, Any]:
    text = ""
    if file_path.lower().endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    else:
        text = extract_text_from_image(file_path)

    # Naive parsing heuristics; in production use robust parsers/LLMs
    vendor = ""
    terms = ""
    items = []
    total = 0.0

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        if line.lower().startswith("vendor") or "vendor:" in line.lower():
            vendor = line.split(":", 1)[-1].strip()
        if line.lower().startswith("terms") or "terms:" in line.lower():
            terms = line.split(":", 1)[-1].strip()
        # naive item pattern: Item - qty x price
        if "x" in line and any(c.isdigit() for c in line):
            try:
                parts = line.split(" ")
                name = parts[0]
                qty = int([p for p in parts if p.isdigit()][0])
                price_tokens = [p for p in parts if p.replace(".", "", 1).isdigit()]
                unit_price = float(price_tokens[-1])
                items.append({"name": name, "quantity": qty, "unit_price": unit_price})
                total += qty * unit_price
            except Exception:
                continue

    return {"vendor": vendor, "terms": terms, "items": items, "total": round(total, 2)}


def generate_po_document(po_number: str, data: Dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{po_number}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"po_number": po_number, **data}, f, indent=2)
    return out_path


def validate_receipt_against_po(receipt_path: str, po_data: Dict[str, Any]) -> Dict[str, Any]:
    text = ""
    if receipt_path.lower().endswith(".pdf"):
        text = extract_text_from_pdf(receipt_path)
    else:
        text = extract_text_from_image(receipt_path)

    result = {"matches": True, "issues": []}
    # naive checks
    if po_data.get("vendor") and po_data["vendor"].lower() not in text.lower():
        result["matches"] = False
        result["issues"].append("Vendor mismatch")

    # check totals approx
    # try find a number resembling total in receipt
    numbers = []
    for token in text.replace(",", " ").split():
        try:
            numbers.append(float(token))
        except Exception:
            continue
    if numbers:
        approx_total = max(numbers)
        if abs(approx_total - float(po_data.get("total", 0))) > 0.01:
            result["matches"] = False
            result["issues"].append("Total amount mismatch")

    return result