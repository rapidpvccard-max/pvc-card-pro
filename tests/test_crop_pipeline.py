import os
import sys
import json
import base64
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app import app
import models
import database
import auth

def run_tests():
    print("Testing Smart Auto-Crop Pipeline End-to-End...")
    client = TestClient(app)
    
    # 1. Setup Test User with credits
    db = next(database.get_db())
    test_user = db.query(models.User).filter(models.User.email == "test_cropper@example.com").first()
    if not test_user:
        test_user = models.User(
            name="Crop Tester",
            email="test_cropper@example.com",
            status="active"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        user_credits = models.UserCredits(
            user_id=test_user.id,
            wallet_balance=50.0,
            cost_per_card=0.95
        )
        db.add(user_credits)
        db.commit()
    else:
        test_user.credits.wallet_balance = 50.0
        db.commit()

    token = auth.create_access_token({"sub": str(test_user.id)})
    headers = {"Cookie": f"access_token={token}"}

    # 2. Test /api/crop/upload-preview
    test_pdf_path = os.path.join("tests", "test_ayushman.pdf")
    assert os.path.exists(test_pdf_path), "test_ayushman.pdf must exist"

    print("  Step 1: Uploading PDF to /api/crop/upload-preview...")
    with open(test_pdf_path, "rb") as f:
        response = client.post(
            "/api/crop/upload-preview",
            files={"file": ("test_doc.pdf", f, "application/pdf")},
            data={"preset": "voter"},
            headers=headers
        )

    assert response.status_code == 200, f"Upload preview failed: {response.text}"
    preview_data = response.json()
    assert preview_data["success"] is True
    assert "temp_id" in preview_data
    assert "preview_url" in preview_data
    assert preview_data["preview_url"].startswith("data:image/jpeg;base64,")
    assert "front_box" in preview_data
    print("  -> Preview successfully rendered and received!")

    temp_id = preview_data["temp_id"]
    front_box = preview_data["front_box"]
    back_box = preview_data.get("back_box")

    # 3. Test /api/crop/generate
    print("  Step 2: Sending crop coordinates to /api/crop/generate...")
    gen_response = client.post(
        "/api/crop/generate",
        data={
            "temp_id": temp_id,
            "file_ext": preview_data.get("file_ext", ".pdf"),
            "front_box": json.dumps(front_box),
            "back_box": json.dumps(back_box) if back_box else "",
            "card_type": "voter"
        },
        headers=headers
    )

    assert gen_response.status_code == 200, f"Generate failed: {gen_response.text}"
    gen_data = gen_response.json()
    assert gen_data["success"] is True
    assert "run_id" in gen_data
    assert "front_url" in gen_data
    assert "pdf_url" in gen_data
    run_id = gen_data["run_id"]
    print(f"  -> PVC Crop & Print PDF generated successfully! Run ID: {run_id}")

    # 4. Verify Downloads
    print("  Step 3: Verifying card image and A4 PDF downloads...")
    front_dl = client.get(f"/download-card/{run_id}/front", headers=headers)
    assert front_dl.status_code == 200
    assert len(front_dl.content) > 1000

    pdf_dl = client.get(f"/download-pdf/{run_id}", headers=headers)
    assert pdf_dl.status_code == 200
    assert pdf_dl.content.startswith(b"%PDF-")
    print("  -> All downloads verified!")

    # 5. Verify Wallet Balance Deduction
    db.refresh(test_user.credits)
    print(f"  -> Wallet Balance after generation: Rs. {test_user.credits.wallet_balance:.2f} (Expected: Rs. 49.05)")
    assert round(test_user.credits.wallet_balance, 2) == 49.05

    print("\n[SUCCESS] All Smart Auto-Crop Pipeline tests PASSED successfully!")

if __name__ == "__main__":
    run_tests()
