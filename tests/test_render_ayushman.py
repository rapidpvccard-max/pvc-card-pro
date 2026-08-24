import os
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

from engine.ayushman_extractor import extract_ayushman_data
from engine.data_mapper import map_ayushman_data
from engine.card_renderer import render_card

def test_both_pdfs():
    pdfs = [
        ("PDF 1 (Nishad Ganeshbhai)", r"C:\Users\NANO\.gemini\antigravity-ide\brain\843a6757-c64b-4e1a-82fc-3b111039ee96\.user_uploaded\media_1787310140549.pdf"),
        ("PDF 2 (Patil Mangal Naval)", r"C:\Users\NANO\.gemini\antigravity-ide\brain\843a6757-c64b-4e1a-82fc-3b111039ee96\.user_uploaded\media_1787321147539.pdf")
    ]
    
    for label, pdf_path in pdfs:
        print(f"\n==================== {label} ====================")
        engine_data = extract_ayushman_data(pdf_path)
        engine_dict = engine_data.to_json_safe_dict()
        
        # Print summary
        summary = {
            "name": engine_dict.get("name"),
            "yob": engine_dict.get("yob"),
            "gender": engine_dict.get("gender"),
            "pmjay_id": engine_dict.get("pmjay_id"),
            "mobile": engine_dict.get("mobile"),
            "district": engine_dict.get("district"),
            "state": engine_dict.get("state"),
            "ration_other_id": engine_dict.get("ration_other_id"),
            "photo_present": bool(engine_dict.get("photo_png_base64")),
            "qr_present": bool(engine_dict.get("qr_base64"))
        }
        print("Extracted fields:", json.dumps(summary, indent=2, ensure_ascii=False))
        
        mapped_data = map_ayushman_data(engine_dict)
        out_dir = os.path.abspath(f"static/renders/test_{os.path.basename(pdf_path).split('.')[0]}")
        os.makedirs(out_dir, exist_ok=True)
        
        front_path, back_path = render_card(mapped_data, engine_dict, out_dir, "ayushman")
        print(f"Rendered front: {front_path}")
        print(f"Rendered back: {back_path}")

if __name__ == "__main__":
    test_both_pdfs()
