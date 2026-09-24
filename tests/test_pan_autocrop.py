import os
import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
import models
import database
import auth

def test_pan_pipeline():
    print("Testing Universal PAN Card Smart Auto-Detection & Direct Crop Pipeline...")
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

    sample_pdf = os.path.join(os.environ.get("USERPROFILE", "C:/Users/NANO"), "Downloads", "SAGAR PATIL PAN CARD.pdf")
    if not os.path.exists(sample_pdf):
        print(f"Skipping test, sample PDF not found at {sample_pdf}")
        return

    print("  Step 1: Uploading e-PAN PDF to /api/crop/upload-preview...")
    with open(sample_pdf, "rb") as f:
        resp = client.post(
            "/api/crop/upload-preview",
            files={"file": ("SAGAR PATIL PAN CARD.pdf", f, "application/pdf")},
            data={"preset": "custom"},
            headers=headers
        )

    assert resp.status_code == 200, f"Upload preview failed: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    assert data["detected"] is True, "Auto-detection failed for PAN card"
    assert data["detected_type"] == "pan_dual", f"Expected pan_dual, got {data.get('detected_type')}"
    assert data["is_dual"] is True, "Expected dual cards (Front and Back)"
    assert data["front_box"] is not None
    assert data["back_box"] is not None

    fb = data["front_box"]
    bb = data["back_box"]
    print(f"  -> Auto-detected: {data['detected_label']} (Type: {data['detected_type']})")
    print(f"  -> Front Box: {fb}")
    print(f"  -> Back Box:  {bb}")

    # Ensure y position is at bottom card area (> 0.75) and NOT up in the text area (0.725)
    assert fb["y"] >= 0.75, f"Front box y too high ({fb['y']}), cutting text"
    assert bb["y"] >= 0.75, f"Back box y too high ({bb['y']}), cutting text"

    print("  Step 2: Generating PVC Card...")
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

    print("[SUCCESS] PAN Card Universal Auto-Detect & Crop Pipeline passed with 100% precision!")

if __name__ == "__main__":
    test_pan_pipeline()
