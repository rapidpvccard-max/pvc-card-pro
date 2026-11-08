import sys
import os
import io
import time
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from fastapi.testclient import TestClient
from app import app
import database, models, auth
from engine.bg_remover import process_background_removal

client = TestClient(app)

def create_test_image():
    # Create simple 600x600 image with a foreground colored circle and background
    img = Image.new("RGBA", (600, 600), (240, 240, 240, 255))
    draw = ImageDraw.Draw(img)
    # Circle in center (foreground subject)
    draw.ellipse([150, 100, 450, 500], fill=(220, 38, 38, 255))
    # Inner shape
    draw.ellipse([220, 180, 380, 400], fill=(255, 255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()

def test_bg_remover_engine_and_api():
    print("\n" + "=" * 70)
    print(" 🪄 AI BACKGROUND REMOVER & HD CUTOUT ENGINE & API AUDIT")
    print("=" * 70)

    # 1. Direct Engine Test
    print("\n[Step 1] Testing engine.bg_remover.process_background_removal...")
    out_dir = "tests_output/test_bg_remover"
    os.makedirs(out_dir, exist_ok=True)
    temp_img_path = os.path.join(out_dir, "input_test.png")
    img_data = create_test_image()
    with open(temp_img_path, "wb") as f:
        f.write(img_data)

    # Test Transparent Mode (Ultra-HD Studio)
    res_trans = process_background_removal(
        input_file_path=temp_img_path,
        output_dir=os.path.join(out_dir, "trans"),
        bg_color_name="transparent",
        precision_mode="studio"
    )
    assert res_trans["success"] is True, "Engine transparent mode failed"
    assert os.path.exists(res_trans["transparent_path"]), "transparent.png does not exist"
    assert res_trans["has_color"] is False
    assert res_trans["precision_mode"] == "studio"
    with Image.open(res_trans["transparent_path"]) as cutout:
        assert cutout.mode == "RGBA", f"Expected RGBA, got {cutout.mode}"
        assert cutout.size[0] == 600 and cutout.size[1] == 600
    print("  ✅ Engine Ultra-HD Studio Transparent Cutout Generated Successfully (600x600 RGBA)")

    # Test Turbo Mode
    res_turbo = process_background_removal(
        input_file_path=temp_img_path,
        output_dir=os.path.join(out_dir, "turbo"),
        bg_color_name="transparent",
        precision_mode="turbo"
    )
    assert res_turbo["success"] is True
    assert res_turbo["precision_mode"] == "turbo"
    print("  ✅ Engine Turbo Mode Generated Successfully")

    # Test Studio Color Mode (light_blue)
    res_blue = process_background_removal(
        input_file_path=temp_img_path,
        output_dir=os.path.join(out_dir, "blue"),
        bg_color_name="light_blue"
    )
    assert res_blue["success"] is True
    assert res_blue["has_color"] is True
    assert os.path.exists(res_blue["colored_path"])
    with Image.open(res_blue["colored_path"]) as comp:
        assert comp.mode == "RGB"
        assert comp.size == (600, 600)
    print("  ✅ Engine Studio Color Composite Generated Successfully (light_blue JPG)")

    # Test Custom Hex Color Mode (#06B6D4)
    res_hex = process_background_removal(
        input_file_path=temp_img_path,
        output_dir=os.path.join(out_dir, "hex"),
        bg_color_name="custom",
        custom_hex="#06b6d4"
    )
    assert res_hex["success"] is True
    assert res_hex["has_color"] is True
    assert os.path.exists(res_hex["colored_path"])
    print("  ✅ Engine Custom Hex Composite Generated Successfully (#06B6D4)")

    # 2. Database & User Setup for API
    print("\n[Step 2] Setting up authenticated test user & credits...")
    db = next(database.get_db())
    test_email = "bg_remover_test@rapidpvc.online"
    user = db.query(models.User).filter(models.User.email == test_email).first()
    if not user:
        user = models.User(
            name="BG Remover Tester",
            email=test_email,
            hashed_password=auth.get_password_hash("TestPass123!"),
            status="active"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    uc = db.query(models.UserCredits).filter(models.UserCredits.user_id == user.id).first()
    if not uc:
        uc = models.UserCredits(
            user_id=user.id,
            wallet_balance=50.0,
            cost_per_card=0.95,
            total_generated=0,
            sample_bg_remover=True
        )
        db.add(uc)
        db.commit()
        db.refresh(uc)
    else:
        uc.wallet_balance = 50.0
        uc.sample_bg_remover = True
        db.commit()

    token = auth.create_access_token({"sub": user.email})
    client.cookies.set("access_token", token)
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  ✅ Test User Ready: Balance=₹{uc.wallet_balance:.2f}, sample_bg_remover={uc.sample_bg_remover}")

    # 3. Test API POST /api/bg-remover/generate (Transparent)
    print("\n[Step 3] Testing API: POST /api/bg-remover/generate (Transparent Mode)...")
    init_balance = uc.wallet_balance
    response = client.post(
        "/api/bg-remover/generate",
        files={"file": ("test_portrait.png", img_data, "image/png")},
        data={"bg_color": "transparent"},
        headers=headers
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["success"] is True
    assert "transparent_url" in data
    assert data["has_color"] is False
    assert data["width"] == 600
    assert data["height"] == 600
    run_id = data["run_id"]
    print(f"  ✅ API Returned Success: run_id={run_id}, proc_time={data.get('processing_time_sec'):.2f}s")

    # Verify wallet deduction
    db.refresh(uc)
    assert abs(uc.wallet_balance - (init_balance - 0.95)) < 0.01, f"Expected wallet {init_balance - 0.95}, got {uc.wallet_balance}"
    print(f"  ✅ Wallet Balance Deducted Correctly: ₹{init_balance:.2f} -> ₹{uc.wallet_balance:.2f}")

    # 4. Test API Download Endpoint for Transparent Cutout
    print("\n[Step 4] Testing API: GET /download-bg-remover/{run_id}/transparent...")
    dl_res = client.get(f"/download-bg-remover/{run_id}/transparent", headers=headers)
    assert dl_res.status_code == 200
    assert dl_res.headers.get("content-type") == "image/png"
    assert len(dl_res.content) > 1000
    print(f"  ✅ Download Endpoint Verified: {len(dl_res.content)} bytes returned with image/png header")

    # 5. Test API POST /api/bg-remover/generate (Solid Studio Color)
    print("\n[Step 5] Testing API: POST /api/bg-remover/generate (Solid Color Mode)...")
    response_col = client.post(
        "/api/bg-remover/generate",
        files={"file": ("test_subject.png", img_data, "image/png")},
        data={"bg_color": "navy_blue"},
        headers=headers
    )
    assert response_col.status_code == 200
    data_col = response_col.json()
    assert data_col["success"] is True
    assert data_col["has_color"] is True
    assert data_col["colored_url"] is not None
    run_id_col = data_col["run_id"]
    print(f"  ✅ API Solid Color Success: colored_url={data_col['colored_url']}")

    dl_col = client.get(f"/download-bg-remover/{run_id_col}/colored", headers=headers)
    assert dl_col.status_code == 200
    assert dl_col.headers.get("content-type") == "image/jpeg"
    print(f"  ✅ Download Endpoint (Colored) Verified: {len(dl_col.content)} bytes returned with image/jpeg header")

    # 6. Test Free Demo Trial Mode (When balance is 0 and sample_bg_remover is True)
    print("\n[Step 6] Testing Free Demo Trial Support...")
    uc.wallet_balance = 0.0
    uc.sample_bg_remover = True
    db.commit()

    demo_res = client.post(
        "/api/bg-remover/generate",
        files={"file": ("test_demo.png", img_data, "image/png")},
        data={"bg_color": "transparent"},
        headers=headers
    )
    assert demo_res.status_code == 200
    demo_data = demo_res.json()
    assert demo_data["success"] is True
    assert demo_data["is_sample"] is True
    print("  ✅ Free Demo Trial Generation Succeeded with 0 Balance!")

    db.refresh(uc)
    assert uc.sample_bg_remover is False, "sample_bg_remover should be consumed"
    print("  ✅ sample_bg_remover Marked Consumed in Database")

    # Subsequent request with 0 balance and demo consumed should return 402
    insuf_res = client.post(
        "/api/bg-remover/generate",
        files={"file": ("test_fail.png", img_data, "image/png")},
        data={"bg_color": "transparent"},
        headers=headers
    )
    assert insuf_res.status_code == 402, f"Expected 402 Insufficient Balance, got {insuf_res.status_code}"
    print("  ✅ 402 Insufficient Balance Correctly Enforced When Demo Exhausted")

    # 7. Test User Router Credits Endpoint
    print("\n[Step 7] Testing User Credits Router (/api/user/credits)...")
    cred_res = client.get("/api/user/credits", headers=headers)
    assert cred_res.status_code == 200
    cred_data = cred_res.json()
    assert "sample_bg_remover" in cred_data
    assert cred_data["sample_bg_remover"] is False
    print("  ✅ /api/user/credits Returns sample_bg_remover Field Accurately")

    print("\n" + "=" * 70)
    print(" 🌟 ALL AI BACKGROUND REMOVER & HD CUTOUT AUDITS PASSED 100%!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    test_bg_remover_engine_and_api()
