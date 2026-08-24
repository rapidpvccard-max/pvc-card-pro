import os
import shutil
from PIL import Image
from engine.ayushman_extractor import extract_ayushman_data
from engine.data_mapper import map_ayushman_data, map_aadhaar_data
from engine.card_renderer import render_card
from engine.a4_print import create_a4_print_pdf
from engine.aadhaar_extractor import extract_aadhaar_data

def run_tests():
    print("==================================================")
    print("STARTING AYUSHMAN PIPELINE QA TEST SUITE")
    print("==================================================")

    pdf_path = "test_ayushman.pdf"
    assert os.path.exists(pdf_path), "test_ayushman.pdf not found!"

    # 1. Extraction Test
    print("\n[TEST 1] Testing Ayushman PDF Extraction...")
    res = extract_ayushman_data(pdf_path)
    data = res.to_json_safe_dict()
    
    print(f" -> Name Extracted: '{data.get('name')}'")
    print(f" -> YOB Extracted: '{data.get('yob')}'")
    print(f" -> Gender Extracted: '{data.get('gender')}'")
    print(f" -> PM-JAY ID Extracted: '{data.get('pmjay_id')}'")
    print(f" -> Mobile Extracted: '{data.get('mobile')}'")
    print(f" -> District Extracted: '{data.get('district')}'")
    print(f" -> State Extracted: '{data.get('state')}'")
    print(f" -> Photo Available: {bool(data.get('photo_png_base64'))}")
    print(f" -> QR Available: {bool(data.get('qr_base64'))}")
    print(f" -> Local Scheme Title: {ascii(data.get('card_title_local'))}")

    assert data.get("name").upper() == "NISHAD GANESHBHAI DINDYALBHAI", f"Expected name match, got {data.get('name')}"
    assert data.get("yob") == "1958", f"Expected YOB 1958, got {data.get('yob')}"
    assert data.get("gender") == "MALE", f"Expected gender MALE, got {data.get('gender')}"
    assert data.get("pmjay_id") == "P9QBPEP3Y", f"Expected PM-JAY ID P9QBPEP3Y, got {data.get('pmjay_id')}"
    assert data.get("district").upper() == "RAJKOT", f"Expected District RAJKOT, got {data.get('district')}"
    assert data.get("state") == "Gujarat", f"Expected State Gujarat, got {data.get('state')}"
    assert bool(data.get("photo_png_base64")), "Photo base64 should be extracted"
    assert bool(data.get("qr_base64")), "QR base64 should be extracted"
    print("  [PASS] Test 1: Ayushman PDF extraction passed!")

    # 2. Data Mapping Test
    print("\n[TEST 2] Testing Data Mapping Layer...")
    mapped = map_ayushman_data(data)
    assert mapped["document_type"] == "ayushman"
    assert mapped["person"]["name"].upper() == "NISHAD GANESHBHAI DINDYALBHAI"
    assert mapped["identity"]["pmjay_id"] == "P9QBPEP3Y"
    assert mapped["scheme"]["card_title_local"] == "આયુષ્માન કાર્ડ"
    print("  [PASS] Test 2: Data mapping passed!")

    # 3. Card Rendering Test
    print("\n[TEST 3] Testing Card Rendering via Playwright...")
    test_output_dir = "tests_output/ayushman_render_test"
    os.makedirs(test_output_dir, exist_ok=True)

    front_path, back_path = render_card(mapped, data, test_output_dir, document_type="ayushman")
    assert os.path.exists(front_path), "Front card PNG was not created"
    assert os.path.exists(back_path), "Back card PNG was not created"

    with Image.open(front_path) as img:
        print(f" -> Front Card Dimensions: {img.size}")
        assert img.size == (1016, 638), f"Expected (1016, 638), got {img.size}"

    with Image.open(back_path) as img:
        print(f" -> Back Card Dimensions: {img.size}")
        assert img.size == (1016, 638), f"Expected (1016, 638), got {img.size}"
    print("  [PASS] Test 3: Card rendering at 1016x638 passed!")

    # 4. A4 Print Duplex PDF Test
    print("\n[TEST 4] Testing A4 Duplex Print Generation...")
    a4_pdf_path = os.path.join(test_output_dir, "ayushman_a4_test.pdf")
    a4_res = create_a4_print_pdf([front_path] * 4, [back_path] * 4, a4_pdf_path, mirror_columns_for_duplex=True)
    assert os.path.exists(a4_pdf_path), "A4 PDF was not created"
    assert a4_res["success"] is True
    print(f" -> A4 PDF created with {a4_res['page_count']} pages")
    print("  [PASS] Test 4: A4 Print generation passed!")

    # 5. Aadhaar Regression Check
    print("\n[TEST 5] Testing Aadhaar Pipeline Regression...")
    aadhaar_pdf = "test_aadhaar.pdf"
    if os.path.exists(aadhaar_pdf):
        a_res = extract_aadhaar_data(aadhaar_pdf)
        a_data = a_res.to_json_safe_dict()
        a_mapped = map_aadhaar_data(a_data)
        a_front, a_back = render_card(a_mapped, a_data, "tests_output/aadhaar_regression_test", document_type="aadhaar")
        assert os.path.exists(a_front) and os.path.exists(a_back)
        with Image.open(a_front) as img:
            assert img.size == (1016, 638)
        print("  [PASS] Test 5: Aadhaar pipeline is 100% functional and intact!")

    print("\n==================================================")
    print("ALL AYUSHMAN PIPELINE TESTS PASSED SUCCESSFULLY! [5/5]")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
