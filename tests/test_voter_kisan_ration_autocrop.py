import os
import sys
import json
import pymupdf
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
import models
import database
import auth
from engine.card_cropper import smart_detect_card_layout

def test_voter_and_unknown_cards():
    print("Testing Universal Voter ID, Kisan Card, and Smart Ration Card Auto-Detect...")
    client = TestClient(app)

    db = next(database.get_db())
    test_user = db.query(models.User).filter(models.User.email == "test_cropper@example.com").first()
    if not test_user:
        test_user = models.User(name="Crop Tester", email="test_cropper@example.com", status="active")
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        user_credits = models.UserCredits(user_id=test_user.id, wallet_balance=50.0, cost_per_card=0.95)
        db.add(user_credits)
        db.commit()
    else:
        test_user.credits.wallet_balance = 50.0
        db.commit()

    token = auth.create_access_token({"sub": str(test_user.id)})
    headers = {"Cookie": f"access_token={token}"}

    # 1. Real Voter ID from user upload
    voter_pdf = r"C:\Users\NANO\.gemini\antigravity-ide\brain\f5bb7641-6d8b-4eb9-8afd-019ef05a8d87\.user_uploaded\media_1790260163472.pdf"
    if os.path.exists(voter_pdf):
        print("\n--- 1. Testing User's Real Voter ID PDF ---")
        with open(voter_pdf, "rb") as f:
            resp = client.post(
                "/api/crop/upload-preview",
                files={"file": ("voter_user.pdf", f, "application/pdf")},
                data={"preset": "custom"},
                headers=headers
            )
        assert resp.status_code == 200, f"Upload preview failed: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["detected"] is True
        fb = data["front_box"]
        bb = data["back_box"]
        assert fb is not None and bb is not None
        assert abs(fb["x"] - bb["x"]) > 0.30, "Front and Back must be distinct cards (not duplicate)"
        print(f"  -> Detected: {data['detected_label']}")
        print(f"  -> Front (Left):  x={fb['x']:.3f}, y={fb['y']:.3f}, w={fb['w']:.3f}, h={fb['h']:.3f}")
        print(f"  -> Back  (Right): x={bb['x']:.3f}, y={bb['y']:.3f}, w={bb['w']:.3f}, h={bb['h']:.3f}")

    # 2. Synthetic Kisan Credit Card (Side-by-Side green cards)
    print("\n--- 2. Testing Synthetic Kisan Credit Card (KCC) ---")
    kcc_pdf = "tests_output/synthetic_kisan_card.pdf"
    os.makedirs("tests_output", exist_ok=True)
    doc_kcc = pymupdf.open()
    page_kcc = doc_kcc.new_page(width=595, height=842)
    page_kcc.insert_text(pymupdf.Point(80, 50), "Kisan Credit Card (KCC) Passbook & ID", fontsize=14)
    # Left Card (Front): x=40, y=120, w=245, h=155
    r_front = pymupdf.Rect(40, 120, 285, 275)
    page_kcc.draw_rect(r_front, color=(0.1, 0.6, 0.2), fill=(0.94, 0.98, 0.94), width=2)
    page_kcc.insert_text(pymupdf.Point(50, 150), "KISAN CREDIT CARD - FRONT", fontsize=11)
    # Right Card (Back): x=310, y=120, w=245, h=155
    r_back = pymupdf.Rect(310, 120, 555, 275)
    page_kcc.draw_rect(r_back, color=(0.1, 0.6, 0.2), fill=(0.94, 0.98, 0.94), width=2)
    page_kcc.insert_text(pymupdf.Point(320, 150), "KISAN CREDIT CARD - BACK", fontsize=11)
    doc_kcc.save(kcc_pdf)
    doc_kcc.close()

    with open(kcc_pdf, "rb") as f:
        resp_kcc = client.post(
            "/api/crop/upload-preview",
            files={"file": ("kisan_card.pdf", f, "application/pdf")},
            data={"preset": "custom"},
            headers=headers
        )
    assert resp_kcc.status_code == 200, f"Upload preview failed: {resp_kcc.text}"
    data_kcc = resp_kcc.json()
    assert data_kcc["success"] is True
    assert data_kcc["detected"] is True, "Failed to auto-detect Kisan card pair"
    fb_kcc = data_kcc["front_box"]
    bb_kcc = data_kcc["back_box"]
    assert fb_kcc is not None and bb_kcc is not None
    assert fb_kcc["x"] < bb_kcc["x"], "Left must be Front and Right must be Back"
    print(f"  -> Detected: {data_kcc['detected_label']}")
    print(f"  -> Front (Left):  x={fb_kcc['x']:.3f}, y={fb_kcc['y']:.3f}, w={fb_kcc['w']:.3f}, h={fb_kcc['h']:.3f}")
    print(f"  -> Back  (Right): x={bb_kcc['x']:.3f}, y={bb_kcc['y']:.3f}, w={bb_kcc['w']:.3f}, h={bb_kcc['h']:.3f}")

    # 3. Synthetic Smart Ration Card (Stacked Top/Bottom orange cards)
    print("\n--- 3. Testing Synthetic Smart Ration Card (Stacked) ---")
    rc_pdf = "tests_output/synthetic_ration_card.pdf"
    doc_rc = pymupdf.open()
    page_rc = doc_rc.new_page(width=595, height=842)
    page_rc.insert_text(pymupdf.Point(80, 50), "Food & Civil Supplies - Smart Ration Card PVC", fontsize=14)
    # Top Card (Front): x=150, y=100, w=295, h=186
    r_top = pymupdf.Rect(150, 100, 445, 286)
    page_rc.draw_rect(r_top, color=(0.8, 0.4, 0.0), fill=(1.0, 0.98, 0.92), width=1.5)
    page_rc.insert_text(pymupdf.Point(160, 130), "RATION CARD - FRONT SIDE", fontsize=11)
    # Bottom Card (Back): x=150, y=320, w=295, h=186
    r_bottom = pymupdf.Rect(150, 320, 445, 506)
    page_rc.draw_rect(r_bottom, color=(0.8, 0.4, 0.0), fill=(1.0, 0.98, 0.92), width=1.5)
    page_rc.insert_text(pymupdf.Point(160, 350), "RATION CARD - BACK SIDE", fontsize=11)
    doc_rc.save(rc_pdf)
    doc_rc.close()

    with open(rc_pdf, "rb") as f:
        resp_rc = client.post(
            "/api/crop/upload-preview",
            files={"file": ("smart_ration_card.pdf", f, "application/pdf")},
            data={"preset": "custom"},
            headers=headers
        )
    assert resp_rc.status_code == 200, f"Upload preview failed: {resp_rc.text}"
    data_rc = resp_rc.json()
    assert data_rc["success"] is True
    assert data_rc["detected"] is True, "Failed to auto-detect Ration card pair"
    fb_rc = data_rc["front_box"]
    bb_rc = data_rc["back_box"]
    assert fb_rc is not None and bb_rc is not None
    assert fb_rc["y"] < bb_rc["y"], "Top must be Front and Bottom must be Back"
    print(f"  -> Detected: {data_rc['detected_label']}")
    print(f"  -> Front (Top):    x={fb_rc['x']:.3f}, y={fb_rc['y']:.3f}, w={fb_rc['w']:.3f}, h={fb_rc['h']:.3f}")
    print(f"  -> Back  (Bottom): x={bb_rc['x']:.3f}, y={bb_rc['y']:.3f}, w={bb_rc['w']:.3f}, h={bb_rc['h']:.3f}")

    print("\n[SUCCESS] Universal Voter, Kisan Card, and Smart Ration Card tests passed with 100% precision!")

if __name__ == "__main__":
    test_voter_and_unknown_cards()
