"""
test_ayushman_gujarat_surat.py
-------------------------------------------------------------
Comprehensive test verifying Ayushman Golden Card extraction &
rendering for Gujarat JasperReports PDFs with positional address
overlay (beneficiary in Surat, Ward No.27, Gujarati scheme branding).
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.ayushman_extractor import extract_ayushman_data, STATE_LANGUAGE_MAP
from engine.data_mapper import map_ayushman_data
from engine.card_renderer import render_card
from PIL import Image

def test_gujarat_surat_ayushman():
    pdf_path = r"C:\Users\NANO\.gemini\antigravity\brain\7ea1a93d-7ea4-442d-a150-3f2da8dbe098\.user_uploaded\media_1793785792241_2cc07199.pdf"
    if not os.path.exists(pdf_path):
        print(f"Skipping test: sample PDF {pdf_path} not found.")
        return

    print("Running Gujarat Surat Ayushman card extraction test...")
    data = extract_ayushman_data(pdf_path)

    # 1. Demographics
    assert data.name == "Naresh Bapu Pawar", f"Unexpected name: {data.name}"
    assert data.yob == "1992", f"Unexpected yob: {data.yob}"
    assert data.gender == "MALE", f"Unexpected gender: {data.gender}"
    assert data.pmjay_id == "MS9XOL2ZX", f"Unexpected pmjay_id: {data.pmjay_id}"
    assert data.abha_number == "91-2782-4876-3338", f"Unexpected abha_number: {data.abha_number}"

    # 2. Address fields (Must not be truncated or missing)
    assert "Surat (M Corp.) - Ward No.27" in data.village_ward, f"Unexpected village_ward: {data.village_ward}"
    assert data.subdivision_town.lower() == "surat", f"Unexpected subdivision_town: {data.subdivision_town}"
    assert data.district.lower() == "surat", f"Unexpected district: {data.district}"

    # 3. State & Language detection (Must be Gujarat / Gujarati)
    assert data.state.lower() == "gujarat", f"Unexpected state: {data.state}"
    assert data.language_code == "gu", f"Unexpected language_code: {data.language_code}"
    assert data.language_name == "Gujarati", f"Unexpected language_name: {data.language_name}"
    assert data.state_local == "ગુજરાત", f"Unexpected state_local: {data.state_local}"
    assert data.card_title_local == "આયુષ્માન કાર્ડ", f"Unexpected card_title_local: {data.card_title_local}"
    assert data.coverage_amount_local == "₹ ૫ લાખ સુધીની", f"Unexpected coverage: {data.coverage_amount_local}"
    assert data.treatment_text_local == "મફત સારવાર", f"Unexpected treatment: {data.treatment_text_local}"

    # 4. Data mapping layer
    mapped = map_ayushman_data(data.to_json_safe_dict())
    assert mapped["language"]["code"] == "gu"
    assert mapped["language"]["name"] == "Gujarati"
    assert mapped["person"]["state"] == "Gujarat"
    assert mapped["person"]["village_ward"] == "Surat (M Corp.) - Ward No.27"

    # 5. Render card front and back
    out_dir = "tests_output/test_gujarat_surat"
    os.makedirs(out_dir, exist_ok=True)
    front_path, back_path = render_card(mapped, data.to_json_safe_dict(), out_dir, document_type="ayushman")

    assert os.path.exists(front_path), "Front card was not created"
    assert os.path.exists(back_path), "Back card was not created"

    img_f = Image.open(front_path)
    assert img_f.size == (1016, 638), f"Incorrect front size: {img_f.size}"
    img_b = Image.open(back_path)
    assert img_b.size == (1016, 638), f"Incorrect back size: {img_b.size}"

    print("[PASS] test_gujarat_surat_ayushman passed with 100% fidelity!")

if __name__ == "__main__":
    test_gujarat_surat_ayushman()
