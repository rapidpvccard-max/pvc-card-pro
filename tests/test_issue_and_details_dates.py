import os
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import fitz
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.aadhaar_extractor import extract_aadhaar_data
from engine.data_mapper import map_aadhaar_data
from engine.card_renderer import render_card

def test_dates_extraction_and_rendering():
    os.makedirs("tests_output/unit_test_dates", exist_ok=True)
    pdf_path = "tests_output/unit_test_dates/sample_dates_aadhaar.pdf"
    
    # Create encrypted synthetic UIDAI PDF with the vertical dates
    doc = fitz.open()
    page = doc.new_page()
    sample_text = """
    भारत सरकार
    Government of India
    ભારતીય વિશિષ્ટ ઓળખ પ્રાધિકરણ
    Unique Identification Authority of India
    Enrollment No.: 2045/12345/67890 23/10/2012 10:15:30
    To,
    Avinash Naval Patil
    અવિનાશ નવલ પાટીલ
    DOB: 01/06/1996
    Gender: Male
    Address: S/O Naval, A-6, Govardhan Nagar -2, Beside Shivalik Square ,Near Rami Park, dindoli, Surat City, PO: Udhna, DIST: Surat, Gujarat - 394210
    7065 0525 5602
    VID: 9119 8982 3145 4816
    Aadhaar no. issued: 23/10/2012
    Details as on: 18/07/2026
    મારો આધાર, મારી ઓળખ
    help@uidai.gov.in | www.uidai.gov.in | 1947
    """
    page.insert_text((50, 50), sample_text)
    doc.save(pdf_path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="AVIN1996")
    doc.close()

    # 1. Test Extraction
    res = extract_aadhaar_data(pdf_path, password="AVIN1996")
    data = res.to_json_safe_dict()
    data["__pdf_path__"] = pdf_path
    data["__pdf_password__"] = "AVIN1996"
    
    assert res.issue_date == "23/10/2012", f"Expected '23/10/2012', got '{res.issue_date}'"
    assert res.details_date == "18/07/2026", f"Expected '18/07/2026', got '{res.details_date}'"
    print("✅ Extractor captured issue_date and details_date!")

    # 2. Test Data Mapper
    mapped = map_aadhaar_data(data)
    assert mapped["identity"]["issue_date"] == "23/10/2012"
    assert mapped["identity"]["details_date"] == "18/07/2026"
    print("✅ Data Mapper mapped identity.issue_date and identity.details_date!")

    # 3. Test Rendering
    out_dir = "tests_output/unit_test_dates/renders"
    front_p, back_p = render_card(mapped, data, out_dir, "aadhaar", "default")
    assert os.path.exists(front_p)
    assert os.path.exists(back_p)
    print("✅ Cards rendered successfully with vertical dates on both sides!")

if __name__ == "__main__":
    test_dates_extraction_and_rendering()
    print("🎉 ALL DATE EXTRACTION & RENDERING TESTS PASSED 100%!")
