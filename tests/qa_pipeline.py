import requests
import uuid
import sys
import os
import time

BASE_URL = "http://127.0.0.1:8000"
test_username = f"test_pipe_{uuid.uuid4().hex[:8]}"
test_email = f"{test_username}@example.com"
test_password = "password123"

def print_result(name, passed, details=""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {name} {details}")
    if not passed:
        sys.exit(1)

def run_pipeline_qa():
    print("--- Core Pipeline & Failure Matrix QA ---")
    s = requests.Session()
    
    # Register and Login
    s.post(f"{BASE_URL}/auth/register", json={
        "name": test_username,
        "email": test_email,
        "password": test_password
    })
    s.post(f"{BASE_URL}/auth/login", json={
        "email": test_email,
        "password": test_password
    })
    
    dash = s.get(f"{BASE_URL}/api/user/dashboard").json()
    initial_credits = dash["credits"]["remaining_cards"]
    print_result("Initial Credits Set", initial_credits > 0)
    
    if not os.path.exists("test_aadhaar.pdf"):
        print("test_aadhaar.pdf not found, skipping core pipeline test.")
        return

    # Upload Test
    with open("test_aadhaar.pdf", "rb") as f:
        r_up = s.post(f"{BASE_URL}/generate", files={"file": ("test_aadhaar.pdf", f, "application/pdf")})
    
    if r_up.status_code == 200:
        data = r_up.json()
        print_result("Pipeline: Generate Success", data.get("success") == True)
        run_id = data.get("run_id")
        print_result("Pipeline: Valid Run ID", run_id is not None)
        
        # Check credits deduction
        dash2 = s.get(f"{BASE_URL}/api/user/dashboard").json()
        print_result("Pipeline: Credit Deducted on Success", dash2["credits"]["remaining_cards"] == initial_credits - 1)
        
        # A4 Print Test
        r_a4 = s.post(f"{BASE_URL}/generate-a4", json={
            "run_id": run_id,
            "cards_count": 1,
            "mirror_duplex": True
        })
        print_result("Pipeline: A4 Print Generation", r_a4.status_code == 200 and r_a4.json().get("success") == True)
        
        # Unauthorized access to another user's run_id
        s_other = requests.Session()
        s_other.post(f"{BASE_URL}/auth/register", json={
            "name": "other_" + test_username,
            "email": "other_" + test_email,
            "password": test_password
        })
        s_other.post(f"{BASE_URL}/auth/login", json={"email": "other_" + test_email, "password": test_password})
        
        r_other_a4 = s_other.post(f"{BASE_URL}/generate-a4", json={"run_id": run_id})
        print_result("Isolation: Cannot access other user's run_id", r_other_a4.status_code == 403)
        
    else:
        print_result("Pipeline: Generate endpoint failed", False, r_up.text)

    # Failure Matrix Tests
    with open("requirements.txt", "rb") as f:
        r_fail = s.post(f"{BASE_URL}/generate", files={"file": ("requirements.txt", f, "text/plain")})
    print_result("Failure Matrix: Reject Non-PDF Content Type", r_fail.status_code == 400)

    # Create spoofed PDF
    with open("spoofed.pdf", "wb") as f:
        f.write(b"This is just text masquerading as a PDF")
    
    with open("spoofed.pdf", "rb") as f:
        r_spoof = s.post(f"{BASE_URL}/generate", files={"file": ("spoofed.pdf", f, "application/pdf")})
    print_result("Failure Matrix: Reject Spoofed PDF Magic Bytes", r_spoof.status_code == 400)
    os.remove("spoofed.pdf")
    
    # Check that failed generations did not deduct credits
    dash3 = s.get(f"{BASE_URL}/api/user/dashboard").json()
    print_result("Ledger Integrity: Failed generation did not deduct credits", dash3["credits"]["remaining_cards"] == dash2["credits"]["remaining_cards"])
    
if __name__ == "__main__":
    try:
        run_pipeline_qa()
    except Exception as e:
        print(f"Test script failed: {e}")
        sys.exit(1)
