import os
import sys
import fitz

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.aadhaar_extractor import extract_aadhaar_data, verify_is_original_uidai_aadhaar
from app import format_extraction_error

def test_aadhaar_security_rules():
    print("=" * 65)
    print("STARTING STRICT UIDAI AADHAAR SECURITY & ORIGINALITY AUDIT")
    print("=" * 65)

    os.makedirs("tests_output", exist_ok=True)

    # 1. TEST UNENCRYPTED / UNLOCKED PDF REJECTION
    print("\n[TEST 1] Testing Unencrypted / Unlocked PDF Rejection...")
    unlocked_pdf_path = "tests/test_ayushman.pdf"
    assert os.path.exists(unlocked_pdf_path), "Sample PDF missing"
    
    r_unlocked = extract_aadhaar_data(unlocked_pdf_path, password="")
    assert r_unlocked.source == "failed", f"Expected failed, got: {r_unlocked.source}"
    err_msg, err_code = format_extraction_error(r_unlocked.to_json_safe_dict())
    assert err_code == "UNLOCKED_AADHAAR_NOT_ALLOWED", f"Expected UNLOCKED_AADHAAR_NOT_ALLOWED, got {err_code}"
    print(f"  [PASS] Code: {err_code}")
    print(f"  [PASS] Message: {err_msg}")

    # 2. TEST ENCRYPTED NON-UIDAI DOCUMENT REJECTION (e.g. Bank Statement or Utility Bill)
    print("\n[TEST 2] Testing Password-Protected Non-UIDAI Document Rejection...")
    non_uidai_path = "tests_output/test_non_uidai_encrypted.pdf"
    doc_non = fitz.open()
    page_non = doc_non.new_page()
    page_non.insert_text((50, 50), "State Bank of India - Account Statement for June 2026\nAccount No: 12345678901\nBalance: Rs. 50,000")
    doc_non.save(non_uidai_path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="BANK1234")
    doc_non.close()

    r_non_uidai = extract_aadhaar_data(non_uidai_path, password="BANK1234")
    assert r_non_uidai.source == "failed", f"Expected failed, got: {r_non_uidai.source}"
    err_msg2, err_code2 = format_extraction_error(r_non_uidai.to_json_safe_dict())
    assert err_code2 == "NOT_ORIGINAL_AADHAAR", f"Expected NOT_ORIGINAL_AADHAAR, got {err_code2}"
    print(f"  [PASS] Code: {err_code2}")
    print(f"  [PASS] Message: {err_msg2}")

    # 3. TEST AUTHENTIC UIDAI ENCRYPTED PDF (PASSWORD REQUIRED CHECK)
    print("\n[TEST 3] Testing Missing Password on Genuine e-Aadhaar...")
    uidai_pdf_path = "tests_output/test_genuine_uidai_encrypted.pdf"
    doc_uidai = fitz.open()
    page_u = doc_uidai.new_page()
    sample_uidai_text = """
    भारत सरकार
    Government of India
    भारतीय विशिष्ट पहचान प्राधिकरण
    Unique Identification Authority of India
    Enrollment No.: 2045/12345/67890
    To,
    Ramesh Chand Sharma
    DOB: 12/04/1988
    Gender: Male
    Address: House No. 102, Shanti Nagar, Ring Road, Jaipur, Rajasthan - 302015
    9876 5432 1098
    VID: 9123 4567 8901 2345
    मेरा आधार, मेरी पहचान
    help@uidai.gov.in | www.uidai.gov.in | 1947
    """
    page_u.insert_text((50, 50), sample_uidai_text)
    doc_uidai.save(uidai_pdf_path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="RAME1988")
    doc_uidai.close()

    r_no_pw = extract_aadhaar_data(uidai_pdf_path, password="")
    assert r_no_pw.source == "failed"
    err_msg3, err_code3 = format_extraction_error(r_no_pw.to_json_safe_dict())
    assert err_code3 == "PASSWORD_REQUIRED", f"Expected PASSWORD_REQUIRED, got {err_code3}"
    print(f"  [PASS] Code: {err_code3}")
    print(f"  [PASS] Message: {err_msg3}")

    # 4. TEST INCORRECT PASSWORD ON GENUINE E-AADHAAR
    print("\n[TEST 4] Testing Incorrect Password on Genuine e-Aadhaar...")
    r_wrong_pw = extract_aadhaar_data(uidai_pdf_path, password="WRONGPASSWORD")
    assert r_wrong_pw.source == "failed"
    err_msg4, err_code4 = format_extraction_error(r_wrong_pw.to_json_safe_dict())
    assert err_code4 == "INCORRECT_PASSWORD", f"Expected INCORRECT_PASSWORD, got {err_code4}"
    print(f"  [PASS] Code: {err_code4}")
    print(f"  [PASS] Message: {err_msg4}")

    # 5. TEST SUCCESSFUL VALIDATION WITH CORRECT PASSWORD
    print("\n[TEST 5] Testing Successful Validation with Correct Password...")
    r_valid = extract_aadhaar_data(uidai_pdf_path, password="RAME1988")
    assert r_valid.dob == "12/04/1988", f"Expected DOB 12/04/1988, got: {r_valid.dob}"
    print(f"  [PASS] Extraction succeeded for genuine e-Aadhaar!")
    print(f"  [PASS] DOB: {r_valid.dob}, Gender: {r_valid.gender}")

    print("\n" + "=" * 65)
    print("ALL 5 STRICT UIDAI SECURITY & ORIGINALITY TESTS PASSED! [5/5]")
    print("=" * 65)

if __name__ == "__main__":
    test_aadhaar_security_rules()
