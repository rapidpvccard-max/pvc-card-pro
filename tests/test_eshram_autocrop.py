import os
import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
import models
import database
import auth
from PIL import Image

def test_eshram_pipeline():
    print("Testing e-Shram Card Smart Auto-Detection & Direct Crop Pipeline...")
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

    sample_pdf = os.path.join(os.environ.get("USERPROFILE", "C:/Users/NANO"), "Downloads", "uan-card.pdf")
    if not os.path.exists(sample_pdf):
        print(f"Skipping test, sample PDF not found at {sample_pdf}")
        return

    print("  Step 1: Uploading e-Shram PDF to /api/crop/upload-preview...")
    with open(sample_pdf, "rb") as f:
        resp = client.post(
            "/api/crop/upload-preview",
            files={"file": ("uan-card.pdf", f, "application/pdf")},
            data={"preset": "custom"},
            headers=headers
        )

    assert resp.status_code == 200, f"Upload preview failed: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    assert data["detected"] is True, "Auto-detection failed for e-Shram card"
    assert data["detected_type"] == "eshram", f"Expected eshram, got {data.get('detected_type')}"
    assert data["is_dual"] is True, "Expected dual cards (Front and Back)"
    assert data["front_box"] is not None
    assert data["back_box"] is not None

    print(f"  -> Auto-detected: {data['detected_label']} (Type: {data['detected_type']})")
    print(f"  -> Front Box: {data['front_box']}")
    print(f"  -> Back Box:  {data['back_box']}")

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

    print("[SUCCESS] e-Shram Auto-Detect & Crop Pipeline passed with 100% accuracy!")

if __name__ == "__main__":
    test_eshram_pipeline()
