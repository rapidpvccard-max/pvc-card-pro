import requests
import os
import json
from PIL import Image

BASE_URL = "http://127.0.0.1:8000"

def test_live_http_flow():
    print("==================================================")
    print("LIVE END-TO-END HTTP WORKFLOW TEST — AYUSHMAN PVC")
    print("==================================================")

    session = requests.Session()

    # 1. Login
    print("\n[STEP 1] Logging in as live_tester@example.com...")
    r_login = session.post(f"{BASE_URL}/auth/login", json={
        "email": "live_tester@example.com",
        "password": "Password123!"
    })
    print(f" -> Login Status: {r_login.status_code}")
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"

    # 2. Get Generator Page
    print("\n[STEP 2] Accessing /generator page...")
    r_gen_page = session.get(f"{BASE_URL}/generator")
    assert r_gen_page.status_code == 200
    assert "Ayushman (PM-JAY) Card" in r_gen_page.text, "Ayushman tab not present in generator HTML!"
    print(" -> Generator page loaded with Ayushman tab present.")

    # 3. Test /extract endpoint for Ayushman
    print("\n[STEP 3] Testing /extract endpoint for Ayushman...")
    with open("test_ayushman.pdf", "rb") as f:
        r_extract = session.post(f"{BASE_URL}/extract", files={"file": ("test_ayushman.pdf", f, "application/pdf")}, data={"document_type": "ayushman"})
    
    print(f" -> Extract Status: {r_extract.status_code}")
    assert r_extract.status_code == 200, f"Extract failed: {r_extract.text}"
    extract_data = r_extract.json()
    assert extract_data["success"] is True
    assert extract_data["document_type"] == "ayushman"
    assert extract_data["mapped_data"]["person"]["name"].upper() == "NISHAD GANESHBHAI DINDYALBHAI"
    assert extract_data["mapped_data"]["identity"]["pmjay_id"] == "P9QBPEP3Y"
    print(" -> Extract Data Verified (Name & PM-JAY ID confirmed)")

    # 4. Test /generate endpoint for Ayushman
    print("\n[STEP 4] Testing /generate endpoint for Ayushman...")
    with open("test_ayushman.pdf", "rb") as f:
        r_generate = session.post(f"{BASE_URL}/generate", files={"file": ("test_ayushman.pdf", f, "application/pdf")}, data={"document_type": "ayushman"})
    
    print(f" -> Generate Status: {r_generate.status_code}")
    assert r_generate.status_code == 200, f"Generate failed: {r_generate.text}"
    gen_result = r_generate.json()
    assert gen_result["success"] is True
    run_id = gen_result["run_id"]
    front_url = gen_result["front_url"]
    back_url = gen_result["back_url"]
    print(f" -> Run ID: {run_id}")
    print(f" -> Front Card URL: {front_url}")
    print(f" -> Back Card URL: {back_url}")

    # Verify generated files on disk
    front_disk_path = f"static/renders/{run_id}/front.png"
    back_disk_path = f"static/renders/{run_id}/back.png"
    assert os.path.exists(front_disk_path), "front.png not found on disk"
    assert os.path.exists(back_disk_path), "back.png not found on disk"

    with Image.open(front_disk_path) as img:
        print(f" -> Front image dimensions: {img.size}")
        assert img.size == (1016, 638)

    with Image.open(back_disk_path) as img:
        print(f" -> Back image dimensions: {img.size}")
        assert img.size == (1016, 638)

    # 5. Test /generate-a4 for this Ayushman run
    print("\n[STEP 5] Testing /generate-a4 for this Ayushman run...")
    r_a4 = session.post(f"{BASE_URL}/generate-a4", json={"run_id": run_id, "cards_count": 2, "mirror_duplex": True})
    print(f" -> A4 Status: {r_a4.status_code}")
    assert r_a4.status_code == 200, f"A4 generation failed: {r_a4.text}"
    a4_result = r_a4.json()
    assert a4_result["success"] is True
    a4_pdf_disk = f"static/renders/{run_id}/a4_print.pdf"
    assert os.path.exists(a4_pdf_disk), "a4_print.pdf not found on disk"
    print(f" -> A4 Print PDF generated at {a4_pdf_disk}")

    print("\n==================================================")
    print("LIVE AYUSHMAN END-TO-END WORKFLOW TEST PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_live_http_flow()
