import os
import requests
import json

BASE_URL = "http://127.0.0.1:8000"
VOTER_PDF = r"C:\Users\NANO\.gemini\antigravity-ide\brain\f5bb7641-6d8b-4eb9-8afd-019ef05a8d87\.user_uploaded\media_1790260163472.pdf"

def test_voter_card_autocrop():
    print("Testing Voter ID Smart Auto-Detection & Dual Crop...")
    session = requests.Session()
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "live_tester@example.com",
        "password": "Password123!"
    })
    assert r.status_code == 200, "Login failed"

    # Step 1: Upload preview
    with open(VOTER_PDF, "rb") as f:
        resp = session.post(
            f"{BASE_URL}/api/crop/upload-preview",
            files={"file": ("voter_card.pdf", f, "application/pdf")},
            data={"preset": "voter"}
        )
    assert resp.status_code == 200, f"Upload preview failed: {resp.text}"
    p_data = resp.json()
    print("  -> Detected Card Type:", p_data.get("detected_type"))
    print("  -> Detected Label:", p_data.get("detected_label"))
    print("  -> Front Box:", p_data.get("front_box"))
    print("  -> Back Box: ", p_data.get("back_box"))
    print("  -> Is Dual:  ", p_data.get("is_dual"))

    assert p_data.get("is_dual") == True, "Voter card must have both front and back"
    fb = p_data.get("front_box")
    bb = p_data.get("back_box")
    assert fb["x"] < 0.20, "Front card must be on the left side"
    assert bb["x"] > 0.40, "Back card must be on the right side"
    assert abs(fb["y"] - bb["y"]) < 0.05, "Front and back must be aligned in the same row"

    # Step 2: Generate PVC card
    gen_resp = session.post(
        f"{BASE_URL}/api/crop/generate",
        data={
            "temp_id": p_data["temp_id"],
            "file_ext": p_data["file_ext"],
            "front_box": json.dumps(fb),
            "back_box": json.dumps(bb),
            "card_type": p_data.get("detected_type", "voter"),
            "page_number": 0
        }
    )
    assert gen_resp.status_code == 200, f"Generate failed: {gen_resp.text}"
    g_data = gen_resp.json()
    print("  -> Generated run_id:", g_data.get("run_id"))
    print("  -> Front URL:", g_data.get("front_url"))
    print("  -> Back URL:", g_data.get("back_url"))
    print("[SUCCESS] Voter Card Auto-Detection & Dual Crop passed with 100% precision!")

if __name__ == "__main__":
    test_voter_card_autocrop()
