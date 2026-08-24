import requests
import os

BASE_URL = "http://127.0.0.1:8000"
session = requests.Session()

def setup_auth():
    print("Setting up test user...")
    # Try register
    r = session.post(f"{BASE_URL}/auth/register", json={
        "name": "QA Tester",
        "email": "qa@test.com",
        "password": "password123"
    })
    # If already registered, that's fine
    
    # Login
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "qa@test.com",
        "password": "password123"
    })
    assert r.status_code == 200
    print("Test user logged in.")

def test_health():
    r = session.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "online"
    print("Health check passed.")

def test_no_file():
    r = session.post(f"{BASE_URL}/generate")
    assert r.status_code == 422 # FastAPI validation error for missing form data
    print("No file test passed.")

def test_non_pdf():
    with open("fake.txt", "w") as f:
        f.write("Hello")
    
    with open("fake.txt", "rb") as f:
        r = session.post(f"{BASE_URL}/generate", files={"file": ("fake.txt", f, "text/plain")})
        assert r.status_code == 400
        assert "Only PDF files" in r.json()["error"]
        
    os.remove("fake.txt")
    print("Non-PDF test passed.")

def test_invalid_pdf():
    with open("fake.pdf", "w") as f:
        f.write("Not a PDF file")
        
    with open("fake.pdf", "rb") as f:
        r = session.post(f"{BASE_URL}/generate", files={"file": ("fake.pdf", f, "application/pdf")})
        assert r.status_code == 400
        assert "valid PDF" in r.json()["error"]
        
    os.remove("fake.pdf")
    print("Invalid PDF test passed.")

def test_oversized_pdf():
    size = 11 * 1024 * 1024
    with open("big.pdf", "wb") as f:
        f.write(b"%PDF-1.4\n")
        f.write(b"0" * size)
        
    with open("big.pdf", "rb") as f:
        r = session.post(f"{BASE_URL}/generate", files={"file": ("big.pdf", f, "application/pdf")})
        assert r.status_code == 413
        assert "10 MB limit" in r.json()["error"]
        
    os.remove("big.pdf")
    print("Oversized PDF test passed.")

def test_template_assets():
    """Guarantee that all required card template background graphics exist and are valid."""
    required_templates = [
        ("aadhaar", "AADHAAR_FRONT.png"),
        ("aadhaar", "AADHAAR_BACK.png"),
        ("ayushman", "AYUSHMAN_FRONT.png"),
    ]
    for doc_type, img_name in required_templates:
        path = os.path.join("templates", "cards", doc_type, "default", "images", img_name)
        assert os.path.exists(path), f"CRITICAL: Template image missing: {path}"
        assert os.path.getsize(path) > 10000, f"CRITICAL: Template image file is empty/corrupt: {path}"
    print("Card template assets integrity check passed.")

if __name__ == "__main__":
    print("Running QA Failure Matrix...")
    test_template_assets()
    setup_auth()
    test_health()
    test_no_file()
    test_non_pdf()
    test_invalid_pdf()
    test_oversized_pdf()
    print("All QA tests passed!")
