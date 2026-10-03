import sys
import os
import io
import json
import uuid
from typing import Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from fastapi.testclient import TestClient
from app import app
import database, models, auth

client = TestClient(app)

def test_all_services_and_buttons():
    print("\n" + "=" * 75)
    print(" 🎯 COMPREHENSIVE 4-SERVICE & ALL-BUTTON FUNCTIONALITY AUDIT")
    print("=" * 75)

    passed_count = 0
    total_count = 0

    def assert_check(name: str, condition: bool, details: str = ""):
        nonlocal passed_count, total_count
        total_count += 1
        if condition:
            passed_count += 1
            print(f"  ✅ [PASS] {name} {details}")
        else:
            print(f"  ❌ [FAIL] {name} {details}")
            raise AssertionError(f"Check failed: {name} - {details}")

    # Set up authenticated test user with plenty of balance
    db = next(database.get_db())
    test_user = db.query(models.User).filter(models.User.email == "full_audit_user@rapidpvc.online").first()
    if not test_user:
        test_user = models.User(
            name="Full Audit Inspector",
            email="full_audit_user@rapidpvc.online",
            hashed_password=auth.get_password_hash("TestPass123!"),
            status="active"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

    uc = db.query(models.UserCredits).filter(models.UserCredits.user_id == test_user.id).first()
    if not uc:
        uc = models.UserCredits(
            user_id=test_user.id,
            wallet_balance=500.0,
            cost_per_card=0.95,
            total_generated=0
        )
        db.add(uc)
        db.commit()
    else:
        uc.wallet_balance = 500.0
        db.commit()

    token = auth.create_access_token({"sub": str(test_user.id)})
    client.cookies.set("access_token", token)

    # =========================================================================
    # SERVICE 1: AADHAAR (STANDARD) - Classic Official White (300 DPI CR80)
    # =========================================================================
    print("\n" + "-" * 60)
    print(" [SERVICE 1] Aadhaar (Standard) - White Layout Test")
    print("-" * 60)

    aadhaar_pdf_path = r"C:\Users\NANO\Downloads\EAadhaar_0000001199604720260809141658_01102026122844.pdf"
    if not os.path.exists(aadhaar_pdf_path):
        aadhaar_pdf_path = "tests_output/test_genuine_uidai_encrypted.pdf"
        aadhaar_pw = "RAME1988"
    else:
        aadhaar_pw = "SHRA1987"

    assert_check("Aadhaar test PDF exists", os.path.exists(aadhaar_pdf_path))

    # Test wrong password rejection
    with open(aadhaar_pdf_path, "rb") as f:
        res_wrong = client.post(
            "/generate",
            data={"document_type": "aadhaar", "template_style": "default", "password": "WRONGPASSWORD"},
            files={"file": (os.path.basename(aadhaar_pdf_path), f, "application/pdf")}
        )
    assert_check("Wrong password rejected with 400", res_wrong.status_code == 400)
    assert_check("Wrong password code is INCORRECT_PASSWORD", res_wrong.json().get("code") == "INCORRECT_PASSWORD")

    # Test correct generation
    balance_before = float(uc.wallet_balance)
    with open(aadhaar_pdf_path, "rb") as f:
        res1 = client.post(
            "/generate",
            data={"document_type": "aadhaar", "template_style": "default", "password": aadhaar_pw},
            files={"file": (os.path.basename(aadhaar_pdf_path), f, "application/pdf")}
        )
    assert_check("Aadhaar Standard HTTP 200", res1.status_code == 200)
    d1 = res1.json()
    assert_check("Aadhaar Standard success=True", d1.get("success") is True)
    assert_check("Aadhaar Standard front_url returned", bool(d1.get("front_url")))
    assert_check("Aadhaar Standard back_url returned", bool(d1.get("back_url")))
    assert_check("Aadhaar Standard pdf_url returned", bool(d1.get("pdf_url")))

    # Verify download endpoints
    r_front = client.get(d1["front_url"])
    assert_check("Download Front Card 200 OK", r_front.status_code == 200 and len(r_front.content) > 10000)
    r_back = client.get(d1["back_url"])
    assert_check("Download Back Card 200 OK", r_back.status_code == 200 and len(r_back.content) > 10000)
    r_a4 = client.get(d1["pdf_url"])
    assert_check("Download A4 Print PDF 200 OK", r_a4.status_code == 200 and len(r_a4.content) > 10000)

    db.refresh(uc)
    assert_check("Wallet deducted exactly ₹0.95", round(balance_before - float(uc.wallet_balance), 2) == 0.95)

    # =========================================================================
    # SERVICE 2: AADHAAR (COLOURFUL) - HD Vibrant Gradient
    # =========================================================================
    print("\n" + "-" * 60)
    print(" [SERVICE 2] Aadhaar (Colourful) - HD Gradient Test")
    print("-" * 60)

    balance_before = float(uc.wallet_balance)
    with open(aadhaar_pdf_path, "rb") as f:
        res2 = client.post(
            "/generate",
            data={"document_type": "aadhaar_color", "template_style": "color", "password": aadhaar_pw},
            files={"file": (os.path.basename(aadhaar_pdf_path), f, "application/pdf")}
        )
    assert_check("Aadhaar Colourful HTTP 200", res2.status_code == 200)
    d2 = res2.json()
    assert_check("Aadhaar Colourful success=True", d2.get("success") is True)
    assert_check("Aadhaar Colourful front_url returned", bool(d2.get("front_url")))
    assert_check("Aadhaar Colourful back_url returned", bool(d2.get("back_url")))
    assert_check("Aadhaar Colourful pdf_url returned", bool(d2.get("pdf_url")))

    r_cfront = client.get(d2["front_url"])
    assert_check("Download Colourful Front Card 200 OK", r_cfront.status_code == 200)
    r_cback = client.get(d2["back_url"])
    assert_check("Download Colourful Back Card 200 OK", r_cback.status_code == 200)
    r_ca4 = client.get(d2["pdf_url"])
    assert_check("Download Colourful A4 Print PDF 200 OK", r_ca4.status_code == 200)

    db.refresh(uc)
    assert_check("Wallet deducted exactly ₹0.95 for colour", round(balance_before - float(uc.wallet_balance), 2) == 0.95)

    # =========================================================================
    # SERVICE 3: AYUSHMAN PVC CARD - PMJAY Golden Layout
    # =========================================================================
    print("\n" + "-" * 60)
    print(" [SERVICE 3] Ayushman PVC Card - PMJAY Golden Layout Test")
    print("-" * 60)

    ayushman_pdf = "tests/test_ayushman.pdf"
    assert_check("Ayushman sample PDF exists", os.path.exists(ayushman_pdf))

    balance_before = float(uc.wallet_balance)
    with open(ayushman_pdf, "rb") as f:
        res3 = client.post(
            "/generate",
            data={"document_type": "ayushman", "template_style": "default"},
            files={"file": ("test_ayushman.pdf", f, "application/pdf")}
        )
    assert_check("Ayushman Generation HTTP 200", res3.status_code == 200)
    d3 = res3.json()
    assert_check("Ayushman success=True", d3.get("success") is True)
    assert_check("Ayushman front_url returned", bool(d3.get("front_url")))
    assert_check("Ayushman back_url returned", bool(d3.get("back_url")))
    assert_check("Ayushman pdf_url returned", bool(d3.get("pdf_url")))

    r_afront = client.get(d3["front_url"])
    assert_check("Download Ayushman Front Card 200 OK", r_afront.status_code == 200)
    r_aback = client.get(d3["back_url"])
    assert_check("Download Ayushman Back Card 200 OK", r_aback.status_code == 200)
    r_aa4 = client.get(d3["pdf_url"])
    assert_check("Download Ayushman A4 Print PDF 200 OK", r_aa4.status_code == 200)

    db.refresh(uc)
    assert_check("Wallet deducted exactly ₹0.95 for Ayushman", round(balance_before - float(uc.wallet_balance), 2) == 0.95)

    # =========================================================================
    # SERVICE 4: AUTO CARD CROPPER - Voter, e-Shram, PAN, DL, MahaSarathi, etc.
    # =========================================================================
    print("\n" + "-" * 60)
    print(" [SERVICE 4] Auto Card Cropper - Multi-Card & Password Test")
    print("-" * 60)

    mahasarathi_pdf = r"C:\Users\NANO\Downloads\MahaSarathiCard_1178-2421-627.pdf"
    if os.path.exists(mahasarathi_pdf):
        print("  [*] Testing Password-Protected MahaSarathi Card...")
        
        # 1. Preview API without password -> should ask for password
        with open(mahasarathi_pdf, "rb") as f:
            res_no_pw = client.post(
                "/api/crop/upload-preview",
                data={"preset": "custom"},
                files={"file": ("MahaSarathiCard_1178-2421-627.pdf", f, "application/pdf")}
            )
        assert_check("Locked card without password triggers 400", res_no_pw.status_code == 400)
        assert_check("Error code is PASSWORD_REQUIRED", res_no_pw.json().get("code") == "PASSWORD_REQUIRED")

        # 2. Preview API with password -> should unlock and auto-detect
        with open(mahasarathi_pdf, "rb") as f:
            res_preview = client.post(
                "/api/crop/upload-preview",
                data={"password": "VIHA2021", "preset": "custom"},
                files={"file": ("MahaSarathiCard_1178-2421-627.pdf", f, "application/pdf")}
            )
        assert_check("Locked card with password unlocks HTTP 200", res_preview.status_code == 200)
        p_data = res_preview.json()
        assert_check("MahaSarathi auto-detection success=True", p_data.get("success") is True)
        assert_check("MahaSarathi detected=True", p_data.get("detected") is True)
        assert_check("Front box detected", bool(p_data.get("front_box")))
        assert_check("Back box detected", bool(p_data.get("back_box")))

        # 3. Direct Cropper Generation via /api/crop/generate
        temp_id = p_data["temp_id"]
        res_crop_gen = client.post(
            "/api/crop/generate",
            data={
                "temp_id": temp_id,
                "file_ext": p_data.get("file_ext", ".pdf"),
                "front_box": json.dumps(p_data["front_box"]),
                "back_box": json.dumps(p_data["back_box"]),
                "card_type": "custom",
                "password": "VIHA2021"
            }
        )
        assert_check("Cropper generation HTTP 200", res_crop_gen.status_code == 200)
        cg_data = res_crop_gen.json()
        assert_check("Cropper generation success=True", cg_data.get("success") is True)
        assert_check("Cropper front_url returned", bool(cg_data.get("front_url")))
        assert_check("Cropper back_url returned", bool(cg_data.get("back_url")))
        assert_check("Cropper pdf_url returned", bool(cg_data.get("pdf_url")))

        # Verify downloads
        r_crop_f = client.get(cg_data["front_url"])
        assert_check("Download Cropper Front Card 200 OK", r_crop_f.status_code == 200 and len(r_crop_f.content) > 5000)
        r_crop_b = client.get(cg_data["back_url"])
        assert_check("Download Cropper Back Card 200 OK", r_crop_b.status_code == 200 and len(r_crop_b.content) > 5000)
        r_crop_pdf = client.get(cg_data["pdf_url"])
        assert_check("Download Cropper A4 Print PDF 200 OK", r_crop_pdf.status_code == 200 and len(r_crop_pdf.content) > 5000)

        # 4. 1-Click Direct Pipeline via /generate with document_type="crop"
        print("  [*] Testing 1-Click Direct Pipeline via /generate (document_type=crop)...")
        with open(mahasarathi_pdf, "rb") as f:
            res_direct_crop = client.post(
                "/generate",
                data={"document_type": "crop", "password": "VIHA2021"},
                files={"file": ("MahaSarathiCard_1178-2421-627.pdf", f, "application/pdf")}
            )
        assert_check("1-Click Direct /generate crop HTTP 200", res_direct_crop.status_code == 200)
        dc_data = res_direct_crop.json()
        assert_check("1-Click Direct crop success=True", dc_data.get("success") is True)
        assert_check("1-Click Direct crop front_url", bool(dc_data.get("front_url")))
        assert_check("1-Click Direct crop back_url", bool(dc_data.get("back_url")))
        assert_check("1-Click Direct crop pdf_url", bool(dc_data.get("pdf_url")))

    # Test Cropper with Kisan / Ration Card
    kisan_pdf = "tests_output/synthetic_kisan_card.pdf"
    if os.path.exists(kisan_pdf):
        print("  [*] Testing Unlocked Kisan Card in Cropper...")
        with open(kisan_pdf, "rb") as f:
            res_kisan = client.post(
                "/api/crop/upload-preview",
                data={"preset": "kisan"},
                files={"file": ("synthetic_kisan_card.pdf", f, "application/pdf")}
            )
        assert_check("Kisan card preview HTTP 200", res_kisan.status_code == 200)
        assert_check("Kisan card detected=True", res_kisan.json().get("detected") is True)

    # =========================================================================
    # MODULE 5: SECURITY GUARDS IN CROPPER (DISALLOW AADHAAR & AYUSHMAN)
    # =========================================================================
    print("\n" + "-" * 60)
    print(" [SECURITY] Cropper Disallowed Cards Audit")
    print("-" * 60)

    # Aadhaar in Cropper -> Blocked
    with open(aadhaar_pdf_path, "rb") as f:
        res_crop_aadhaar = client.post(
            "/api/crop/upload-preview",
            data={"password": aadhaar_pw},
            files={"file": (os.path.basename(aadhaar_pdf_path), f, "application/pdf")}
        )
    assert_check("Aadhaar blocked in cropper HTTP 400", res_crop_aadhaar.status_code == 400)
    assert_check("Aadhaar blocked code is AADHAAR_NOT_ALLOWED_IN_CROPPER", res_crop_aadhaar.json().get("code") == "AADHAAR_NOT_ALLOWED_IN_CROPPER")

    # Ayushman in Cropper -> Blocked
    with open(ayushman_pdf, "rb") as f:
        res_crop_ayushman = client.post(
            "/api/crop/upload-preview",
            files={"file": ("test_ayushman.pdf", f, "application/pdf")}
        )
    assert_check("Ayushman blocked in cropper HTTP 400", res_crop_ayushman.status_code == 400)
    assert_check("Ayushman blocked code is AYUSHMAN_NOT_ALLOWED_IN_CROPPER", res_crop_ayushman.json().get("code") == "AYUSHMAN_NOT_ALLOWED_IN_CROPPER")

    print("\n" + "=" * 75)
    print(f" 🏆 ALL AUDIT CHECKS COMPLETED: {passed_count}/{total_count} PASSED (100% SUCCESS)!")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    test_all_services_and_buttons()
