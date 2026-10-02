import os
import sys
from fastapi.testclient import TestClient
import fitz

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
import models, database, auth

def test_api_security():
    print("=" * 65)
    print("TESTING FASTAPI /GENERATE AND /EXTRACT WITH UIDAI RULES")
    print("=" * 65)

    client = TestClient(app)
    db = next(database.get_db())

    # Ensure a test user exists
    test_user = db.query(models.User).filter(models.User.email == "uidai_tester@test.com").first()
    if not test_user:
        test_user = models.User(
            name="UIDAI Test User",
            email="uidai_tester@test.com",
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

    # 1. Test Unlocked PDF on Standard Aadhaar
    print("\n[API TEST 1] POST /generate with Unlocked PDF (Standard Aadhaar)...")
    with open("tests/test_ayushman.pdf", "rb") as f:
        res = client.post(
            "/generate",
            data={"document_type": "aadhaar", "password": ""},
            files={"file": ("unlocked.pdf", f, "application/pdf")}
        )
    assert res.status_code == 400
    json_data = res.json()
    assert json_data["code"] == "UNLOCKED_AADHAAR_NOT_ALLOWED"
    print(f"  [PASS] Status: {res.status_code}, Code: {json_data['code']}")

    # 2. Test Unlocked PDF on Colourful Aadhaar
    print("\n[API TEST 2] POST /generate with Unlocked PDF (Colourful Aadhaar)...")
    with open("tests/test_ayushman.pdf", "rb") as f:
        res2 = client.post(
            "/generate",
            data={"document_type": "aadhaar_color", "template_style": "color", "password": ""},
            files={"file": ("unlocked.pdf", f, "application/pdf")}
        )
    assert res2.status_code == 400
    json_data2 = res2.json()
    assert json_data2["code"] == "UNLOCKED_AADHAAR_NOT_ALLOWED"
    print(f"  [PASS] Status: {res2.status_code}, Code: {json_data2['code']}")

    # 3. Test Non-UIDAI Encrypted Document
    print("\n[API TEST 3] POST /generate with Encrypted Non-UIDAI Document...")
    with open("tests_output/test_non_uidai_encrypted.pdf", "rb") as f:
        res3 = client.post(
            "/generate",
            data={"document_type": "aadhaar", "password": "BANK1234"},
            files={"file": ("bank_statement.pdf", f, "application/pdf")}
        )
    assert res3.status_code == 400
    json_data3 = res3.json()
    assert json_data3["code"] == "NOT_ORIGINAL_AADHAAR"
    print(f"  [PASS] Status: {res3.status_code}, Code: {json_data3['code']}")

    # 4. Test Ayushman PDF on Ayushman Tab (Must still succeed)
    print("\n[API TEST 4] POST /generate with Ayushman PDF on Ayushman Option...")
    with open("tests/test_ayushman.pdf", "rb") as f:
        res4 = client.post(
            "/generate",
            data={"document_type": "ayushman"},
            files={"file": ("ayushman.pdf", f, "application/pdf")}
        )
    assert res4.status_code == 200, f"Expected 200, got {res4.text}"
    print(f"  [PASS] Status: {res4.status_code}, Card successfully generated for Ayushman!")

    print("\n" + "=" * 65)
    print("ALL API SECURITY TESTS PASSED! [4/4]")
    print("=" * 65)

if __name__ == "__main__":
    test_api_security()
