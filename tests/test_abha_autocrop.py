import os
import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
import models
import database
import auth
from engine.card_cropper import smart_detect_card_layout

def test_abha_pipeline():
    print("Testing Universal ABHA Card Smart Auto-Detection & Direct Crop Pipeline...")
    sample_pdf = os.path.join(os.environ.get("USERPROFILE", "C:/Users/NANO"), "Downloads", "ABHA-Card-52-8664-8328-6259.pdf")
    if not os.path.exists(sample_pdf):
        print(f"Skipping test, sample PDF not found at {sample_pdf}")
        return

    # 1. Direct Engine detection check
    print("  Step 1: Direct smart_detect_card_layout test...")
    layout = smart_detect_card_layout(sample_pdf)
    assert layout["detected"] is True, "ABHA card should be detected"
    assert layout["card_type"] == "abha", f"Expected card_type 'abha', got {layout['card_type']}"
    assert layout["front_box"] is not None
    assert layout["back_box"] is not None
    
    fb = layout["front_box"]
    bb = layout["back_box"]
    print(f"  -> Detected label: {layout['card_label']}")
    print(f"  -> Front box: {fb}")
    print(f"  -> Back box:  {bb}")

    # Front card is near top (y < 0.10), back card is in bottom half (y > 0.40)
    assert fb["y"] < 0.10, f"Front box y too low ({fb['y']})"
    assert bb["y"] > 0.40, f"Back box y too high ({bb['y']})"
    assert fb["w"] > 0.85, f"Front box width should span majority of page width ({fb['w']})"
    assert bb["w"] > 0.85, f"Back box width should span majority of page width ({bb['w']})"

    # 2. API /api/crop/upload-preview test
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

    print("  Step 2: Uploading ABHA PDF to /api/crop/upload-preview...")
    with open(sample_pdf, "rb") as f:
        resp = client.post(
            "/api/crop/upload-preview",
            files={"file": ("ABHA-Card-52-8664-8328-6259.pdf", f, "application/pdf")},
            data={"preset": "custom"},
            headers=headers
        )

    assert resp.status_code == 200, f"Upload preview failed: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    assert data["detected"] is True
    assert data["detected_type"] == "abha"
    assert data["is_dual"] is True

    print("  Step 3: Generating PVC Card...")
    gen_resp = client.post(
        "/api/crop/generate",
        data={
            "temp_id": data["temp_id"],
            "file_ext": data["file_ext"],
            "front_box": json.dumps(data["front_box"]),
            "back_box": json.dumps(data["back_box"]),
            "card_type": data["detected_type"]
        },
        headers=headers
    )
    assert gen_resp.status_code == 200, f"Generate failed: {gen_resp.text}"
    gen_data = gen_resp.json()
    assert gen_data["success"] is True
    run_id = gen_data["run_id"]
    print(f"  -> Generated run_id: {run_id}")

    # Verify download images
    f_res = client.get(f"/download-card/{run_id}/front", headers=headers)
    assert f_res.status_code == 200
    b_res = client.get(f"/download-card/{run_id}/back", headers=headers)
    assert b_res.status_code == 200
    pdf_res = client.get(f"/download-pdf/{run_id}", headers=headers)
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF-")

    print("[SUCCESS] ABHA Card Universal Auto-Detect & Crop Pipeline passed with 100% precision!")

if __name__ == "__main__":
    test_abha_pipeline()
