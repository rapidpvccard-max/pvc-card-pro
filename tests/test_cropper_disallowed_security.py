import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
import models, database, auth

def test_cropper_disallowed_security():
    print("=" * 70)
    print("TESTING STRICT DISALLOWED CARD RULES (AADHAAR & AYUSHMAN) IN CROPPER")
    print("=" * 70)

    client = TestClient(app)
    db = next(database.get_db())

    # Ensure a test user exists
    test_user = db.query(models.User).filter(models.User.email == "cropper_tester@test.com").first()
    if not test_user:
        test_user = models.User(
            name="Cropper Test User",
            email="cropper_tester@test.com",
            hashed_password=auth.get_password_hash("testpass123")
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

    uc = db.query(models.UserCredits).filter(models.UserCredits.user_id == test_user.id).first()
    if not uc:
        uc = models.UserCredits(
            user_id=test_user.id,
            wallet_balance=100.0,
            cost_per_card=0.95
        )
        db.add(uc)
        db.commit()
    else:
        uc.wallet_balance = 100.0
        db.commit()

    token = auth.create_access_token({"sub": str(test_user.id)})
    client.cookies.set("access_token", token)

    # 1. AYUSHMAN PDF TEST IN CROPPER
    print("\n[TEST 1] Upload Ayushman PDF to /api/crop/upload-preview...")
    with open("tests/test_ayushman.pdf", "rb") as f:
        res = client.post(
            "/api/crop/upload-preview",
            data={"preset": "voter", "password": ""},
            files={"file": ("ayushman_card.pdf", f, "application/pdf")}
        )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    j1 = res.json()
    assert j1["success"] is False
    assert j1["code"] == "AYUSHMAN_NOT_ALLOWED_IN_CROPPER", f"Expected AYUSHMAN_NOT_ALLOWED_IN_CROPPER, got {j1.get('code')}"
    print(f"  [PASS] Status: {res.status_code}, Code: {j1['code']}")
    print(f"  [PASS] Message: {j1['error']}")

    # 2. ENCRYPTED GENUINE AADHAAR WITH PASSWORD IN CROPPER
    print("\n[TEST 2] Upload Password-Protected Genuine Aadhaar to /api/crop/upload-preview...")
    with open("tests_output/test_genuine_uidai_encrypted.pdf", "rb") as f:
        res = client.post(
            "/api/crop/upload-preview",
            data={"preset": "custom", "password": "RAME1988"},
            files={"file": ("document_secret.pdf", f, "application/pdf")}
        )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    j2 = res.json()
    assert j2["success"] is False
    assert j2["code"] == "AADHAAR_NOT_ALLOWED_IN_CROPPER", f"Expected AADHAAR_NOT_ALLOWED_IN_CROPPER, got {j2.get('code')}"
    print(f"  [PASS] Status: {res.status_code}, Code: {j2['code']}")
    print(f"  [PASS] Message: {j2['error']}")

    # 3. UNLOCKED AADHAAR IN CROPPER
    print("\n[TEST 3] Upload Unlocked Aadhaar to /api/crop/upload-preview...")
    with open("tests_output/unlocked_sample_aadhaar.pdf", "rb") as f:
        res = client.post(
            "/api/crop/upload-preview",
            data={"preset": "voter", "password": ""},
            files={"file": ("unlocked_aadhaar.pdf", f, "application/pdf")}
        )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    j3 = res.json()
    assert j3["success"] is False
    assert j3["code"] == "AADHAAR_NOT_ALLOWED_IN_CROPPER", f"Expected AADHAAR_NOT_ALLOWED_IN_CROPPER, got {j3.get('code')}"
    print(f"  [PASS] Status: {res.status_code}, Code: {j3['code']}")
    print(f"  [PASS] Message: {j3['error']}")

    # 4. AADHAAR DETECTED BY FILENAME IN CROPPER
    print("\n[TEST 4] Upload PDF with 'eAadhaar' filename to /api/crop/upload-preview...")
    with open("tests_output/synthetic_kisan_card.pdf", "rb") as f:
        res = client.post(
            "/api/crop/upload-preview",
            data={"preset": "voter", "password": ""},
            files={"file": ("eaadhaar_987654321012.pdf", f, "application/pdf")}
        )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    j4 = res.json()
    assert j4["success"] is False
    assert j4["code"] == "AADHAAR_NOT_ALLOWED_IN_CROPPER", f"Expected AADHAAR_NOT_ALLOWED_IN_CROPPER, got {j4.get('code')}"
    print(f"  [PASS] Status: {res.status_code}, Code: {j4['code']}")

    # 5. ALLOWED CARD TEST 1: KISAN CREDIT CARD (KCC)
    print("\n[TEST 5] Upload Kisan Card to /api/crop/upload-preview (Should succeed)...")
    with open("tests_output/synthetic_kisan_card.pdf", "rb") as f:
        res = client.post(
            "/api/crop/upload-preview",
            data={"preset": "kisan", "password": ""},
            files={"file": ("kisan_credit_card.pdf", f, "application/pdf")}
        )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    j5 = res.json()
    assert j5["success"] is True, f"Expected success=True, got {j5}"
    assert "preview_url" in j5
    print(f"  [PASS] Status: {res.status_code}, Detected: {j5.get('detected')}, Type: {j5.get('detected_type')}")

    # 6. ALLOWED CARD TEST 2: SMART RATION CARD
    print("\n[TEST 6] Upload Ration Card to /api/crop/upload-preview (Should succeed)...")
    with open("tests_output/synthetic_ration_card.pdf", "rb") as f:
        res = client.post(
            "/api/crop/upload-preview",
            data={"preset": "ration", "password": ""},
            files={"file": ("smart_ration_card.pdf", f, "application/pdf")}
        )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    j6 = res.json()
    assert j6["success"] is True, f"Expected success=True, got {j6}"
    assert "preview_url" in j6
    print(f"  [PASS] Status: {res.status_code}, Detected: {j6.get('detected')}, Type: {j6.get('detected_type')}")

    print("\n" + "=" * 70)
    print("ALL 6 CROPPER SECURITY AND ALLOWED-CARD AUDITS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    test_cropper_disallowed_security()
