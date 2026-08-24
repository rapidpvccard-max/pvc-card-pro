import requests
import uuid
import sys
import os

BASE_URL = "http://127.0.0.1:8000"
test_username = f"test_{uuid.uuid4().hex[:8]}"
test_email = f"{test_username}@example.com"
test_password = "password123"

def print_result(name, passed, details=""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {name} {details}")
    if not passed:
        sys.exit(1)

def run_qa():
    print("--- 1. Authentication & Security Audit ---")
    s = requests.Session()
    
    # 1.1 Registration
    r = s.post(f"{BASE_URL}/auth/register", json={
        "name": test_username,
        "email": test_email,
        "password": test_password
    })
    print_result("Registration", r.status_code == 200)
    
    # 1.2 Duplicate Registration
    r2 = s.post(f"{BASE_URL}/auth/register", json={
        "name": test_username,
        "email": test_email,
        "password": test_password
    })
    print_result("Duplicate Registration Constraint", r2.status_code == 400)
    
    # 1.3 Login (Valid)
    r_login = s.post(f"{BASE_URL}/auth/login", json={
        "email": test_email,
        "password": test_password
    })
    print_result("Login Valid Credentials", r_login.status_code == 200)
    
    # Check if HttpOnly cookie is set
    token = s.cookies.get("access_token")
    print_result("JWT Cookie Persistence", token is not None)
    
    # 1.4 Invalid Credentials
    s_invalid = requests.Session()
    r_invalid = s_invalid.post(f"{BASE_URL}/auth/login", json={
        "email": test_email,
        "password": "wrongpassword"
    })
    print_result("Invalid Credentials Rejected", r_invalid.status_code in [400, 401])
    
    # 1.5 Protected Route Access
    r_dash = s.get(f"{BASE_URL}/api/user/dashboard")
    print_result("Protected API Access (Logged In)", r_dash.status_code == 200)
    
    r_dash_unauth = s_invalid.get(f"{BASE_URL}/api/user/dashboard")
    print_result("Protected API Access (Logged Out)", r_dash_unauth.status_code == 401)
    
    # 1.6 User/Admin Separation
    r_admin = s.get(f"{BASE_URL}/api/admin/users")
    print_result("Admin Route Rejects Normal User", r_admin.status_code == 403)
    
    # 1.7 Logout
    r_logout = s.post(f"{BASE_URL}/auth/logout")
    print_result("Logout", r_logout.status_code == 200)
    print_result("Cookie Cleared on Logout", s.cookies.get("access_token") is None or not s.cookies.get("access_token"))

    # Re-login for next tests
    s.post(f"{BASE_URL}/auth/login", json={"email": test_email, "password": test_password})

    print("\n--- 2. Dashboard & Ledger Integrity ---")
    dash = s.get(f"{BASE_URL}/api/user/dashboard").json()
    print_result("Dashboard Format", "credits" in dash and "wallet_balance" in dash["credits"])
    
    print("\n--- All tests passed! ---")

if __name__ == "__main__":
    try:
        run_qa()
    except Exception as e:
        print(f"Test script failed: {e}")
        sys.exit(1)
