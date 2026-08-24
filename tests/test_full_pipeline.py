import requests
import json
import os

BASE_URL = "http://127.0.0.1:8000"
PDF_PATH = "test_aadhaar.pdf"

session = requests.Session()

def setup_auth():
    print("Setting up test user...")
    session.post(f"{BASE_URL}/auth/register", json={
        "name": "Pipeline Tester",
        "email": "pipeline@test.com",
        "password": "password123"
    })
    
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "pipeline@test.com",
        "password": "password123"
    })
    assert r.status_code == 200
    print("Test user logged in.")

def test_pipeline():
    if not os.path.exists(PDF_PATH):
        print(f"Skipping test: {PDF_PATH} not found.")
        return

    print("Testing Full Pipeline...")
    
    with open(PDF_PATH, "rb") as f:
        # Use a password if needed, this test assumes the local test_aadhaar is a sample
        data = {"password": ""}
        files = {"file": ("test_aadhaar.pdf", f, "application/pdf")}
        
        response = session.post(f"{BASE_URL}/generate", data=data, files=files)
        
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("Pipeline Success!")
        print(f"Mapped Name: {result.get('mapped_data', {}).get('person', {}).get('name', '')}")
        print(f"Front URL: {result.get('front_url')}")
        print(f"Back URL: {result.get('back_url')}")
        print(f"Extraction Status: {result.get('extraction_status')}")
        print(f"Photo Available: {result.get('photo_available')}")
        print(f"QR Available: {result.get('qr_available')}")
        
        # Verify file existence physically
        run_id = result.get('run_id')
        front_path = os.path.join("static", "renders", run_id, "front.png")
        back_path = os.path.join("static", "renders", run_id, "back.png")
        
        print(f"Front Image exists: {os.path.exists(front_path)}")
        print(f"Back Image exists: {os.path.exists(back_path)}")
        
        if os.path.exists(front_path):
            from PIL import Image
            with Image.open(front_path) as img:
                print(f"Front Dimensions: {img.width}x{img.height}")
                
        # Test A4 Generation
        print("\nTesting /generate-a4 endpoint...")
        a4_res = session.post(f"{BASE_URL}/generate-a4", json={
            "run_id": run_id,
            "cards_count": 10,
            "mirror_duplex": True
        })
        print(f"A4 Status Code: {a4_res.status_code}")
        if a4_res.status_code == 200:
            a4_data = a4_res.json()
            print("A4 Pipeline Success!")
            print(f"A4 PDF URL: {a4_data.get('pdf_url')}")
            print(f"Pages: {a4_data.get('pages')}")
            print(f"Cards Per Page: {a4_data.get('cards_per_page')}")
        else:
            print(f"A4 Pipeline Failed: {a4_res.text}")
            
    else:
        print(f"Pipeline Failed: {response.text}")

if __name__ == "__main__":
    setup_auth()
    test_pipeline()
