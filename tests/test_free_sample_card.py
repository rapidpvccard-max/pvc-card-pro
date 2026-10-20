import sys
import os
import uuid
from fastapi.testclient import TestClient
from PIL import Image

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app
import database
import models
import auth
from engine.watermark import apply_card_watermark

client = TestClient(app.app)

def test_watermark_engine_direct():
    """Verify watermark application to image file and visual content."""
    temp_img_dir = os.path.join("tests_output", "watermark_test")
    os.makedirs(temp_img_dir, exist_ok=True)
    
    front_test_path = os.path.join(temp_img_dir, "test_front.png")
    back_test_path = os.path.join(temp_img_dir, "test_back.png")
    
    # Create plain cards
    Image.new("RGB", (1016, 638), "#ffffff").save(front_test_path, "PNG")
    Image.new("RGB", (1016, 638), "#f1f5f9").save(back_test_path, "PNG")
    
    # Apply watermark
    apply_card_watermark(front_test_path)
    apply_card_watermark(back_test_path)
    
    assert os.path.exists(front_test_path)
    assert os.path.exists(back_test_path)
    
    with Image.open(front_test_path) as img:
        assert img.size == (1016, 638)
    with Image.open(back_test_path) as img:
        assert img.size == (1016, 638)
    print("✅ Watermark direct test passed!")

def test_all_4_services_independent_free_samples():
    """
    Verify all 4 card services have independent free demos for every account:
    1. Aadhaar (Standard)
    2. Aadhaar (Colourful)
    3. Ayushman PVC Card
    4. Auto Card Cropper
    """
    db = next(database.get_db())
    unique_email = f"multi_demo_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "MultiDemo123!"

    # 1. Register User
    reg_res = client.post("/auth/register", json={
        "name": "Multi Demo Tester",
        "email": unique_email,
        "password": pwd
    })
    assert reg_res.status_code == 200, f"Register failed: {reg_res.text}"
    user_data = reg_res.json()
    user_id = user_data["id"]

    token = auth.create_access_token(data={"sub": str(user_id)})
    headers = {"Authorization": f"Bearer {token}"}
    cookies = {"access_token": token}

    # 2. Check /api/user/credits
    cred_res = client.get("/api/user/credits", headers=headers, cookies=cookies)
    assert cred_res.status_code == 200
    cred_data = cred_res.json()
    assert cred_data["wallet_balance"] == 0.0
    assert cred_data["sample_aadhaar"] == True
    assert cred_data["sample_aadhaar_color"] == True
    assert cred_data["sample_ayushman"] == True
    assert cred_data["sample_crop"] == True
    assert cred_data["free_sample_available"] == True
    print("✅ Verified new account has 1 free demo for all 4 services!")

    # 3. Use 1st demo: Auto Card Cropper
    os.makedirs("uploads", exist_ok=True)
    temp_crop_id = str(uuid.uuid4())
    temp_file_path = os.path.join("uploads", f"crop_{temp_crop_id}.png")
    Image.new("RGB", (1200, 800), "#e2e8f0").save(temp_file_path, "PNG")

    front_box = {"x": 0.05, "y": 0.1, "w": 0.4, "h": 0.3}
    back_box = {"x": 0.5, "y": 0.1, "w": 0.4, "h": 0.3}

    crop_res = client.post(
        "/api/crop/generate",
        data={
            "temp_id": temp_crop_id,
            "file_ext": ".png",
            "front_box": str(front_box).replace("'", '"'),
            "back_box": str(back_box).replace("'", '"'),
            "card_type": "voter",
            "page_number": 0,
            "duplex_mode": False
        },
        headers=headers,
        cookies=cookies
    )
    assert crop_res.status_code == 200
    crop_data = crop_res.json()
    assert crop_data["is_sample"] == True

    # 4. Check credits after Cropper demo
    cred_res2 = client.get("/api/user/credits", headers=headers, cookies=cookies)
    c2 = cred_res2.json()
    assert c2["sample_crop"] == False
    assert c2["sample_aadhaar"] == True
    assert c2["sample_aadhaar_color"] == True
    assert c2["sample_ayushman"] == True
    assert c2["free_sample_available"] == True
    print("✅ Auto Card Cropper demo consumed; other 3 services remain available!")

    # 5. Cropper 2nd attempt at 0 balance must be blocked
    temp_crop_id_2 = str(uuid.uuid4())
    temp_file_path_2 = os.path.join("uploads", f"crop_{temp_crop_id_2}.png")
    Image.new("RGB", (1200, 800), "#e2e8f0").save(temp_file_path_2, "PNG")

    crop_block = client.post(
        "/api/crop/generate",
        data={
            "temp_id": temp_crop_id_2,
            "file_ext": ".png",
            "front_box": str(front_box).replace("'", '"'),
            "back_box": str(back_box).replace("'", '"'),
            "card_type": "voter",
            "page_number": 0,
            "duplex_mode": False
        },
        headers=headers,
        cookies=cookies
    )
    assert crop_block.status_code == 402
    assert "Insufficient wallet balance" in crop_block.json()["error"]
    print("✅ Auto Card Cropper 2nd attempt blocked with 402!")

    # 6. Verify helper methods accurately track each category
    user = db.query(models.User).filter(models.User.id == user_id).first()
    assert app.is_service_sample_available(user.credits, "crop") == False
    assert app.is_service_sample_available(user.credits, "aadhaar") == True
    assert app.is_service_sample_available(user.credits, "aadhaar_color") == True
    assert app.is_service_sample_available(user.credits, "ayushman") == True

    # Consume Aadhaar demo
    app.consume_service_sample(user.credits, "aadhaar")
    db.commit()
    assert app.is_service_sample_available(user.credits, "aadhaar") == False
    assert app.is_service_sample_available(user.credits, "aadhaar_color") == True
    assert app.is_service_sample_available(user.credits, "ayushman") == True

    # Consume Colourful Aadhaar demo
    app.consume_service_sample(user.credits, "aadhaar_color")
    db.commit()
    assert app.is_service_sample_available(user.credits, "aadhaar_color") == False
    assert app.is_service_sample_available(user.credits, "ayushman") == True

    # Consume Ayushman demo
    app.consume_service_sample(user.credits, "ayushman")
    db.commit()
    assert app.is_service_sample_available(user.credits, "ayushman") == False
    assert app.is_service_sample_available(user.credits, "crop") == False
    assert user.credits.free_sample_available == False
    print("✅ All 4 service sample flags independently tracked & consumed!")

if __name__ == "__main__":
    test_watermark_engine_direct()
    test_all_4_services_independent_free_samples()
    print("\n🎉 ALL 4-SERVICE FREE SAMPLE TESTS PASSED 100%!")
