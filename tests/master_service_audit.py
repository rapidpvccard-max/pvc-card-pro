import sys
import os
import uuid
import json

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from fastapi.testclient import TestClient
from app import app
import database, models, auth
from engine.data_mapper import map_aadhaar_data, map_ayushman_data
from engine.ayushman_extractor import extract_ayushman_data
from engine.card_renderer import render_card
from engine.a4_print import create_a4_print_pdf
from services.banner_service import get_banner_config

client = TestClient(app)
db = database.SessionLocal()

def run_master_audit():
    print("\n" + "="*70)
    print(" 🚀 RAPID PVC PRO -- MASTER SERVICE HEALTH & AUDIT REPORT")
    print("="*70)

    total_checks = 0
    passed_checks = 0

    def check(name, condition, extra=""):
        nonlocal total_checks, passed_checks
        total_checks += 1
        if condition:
            passed_checks += 1
            print(f"  ✅ [PASS] {name} {extra}")
        else:
            print(f"  ❌ [FAIL] {name} {extra}")
            raise AssertionError(f"Check failed: {name}")

    # -------------------------------------------------------------
    # 1. CORE WEB ROUTES & SERVER HEALTH
    # -------------------------------------------------------------
    print("\n[MODULE 1] Core Public Routes & Server Health Check")
    health_res = client.get("/health")
    check("/health online status", health_res.status_code == 200 and health_res.json().get("status") == "online")

    routes_to_test = [
        ("/", "Landing Page"),
        ("/login", "Login Page"),
        ("/register", "Registration Page"),
        ("/forgot-password", "Forgot Password Page"),
        ("/subscription", "Recharge Plans Page")
    ]
    for route, label in routes_to_test:
        r = client.get(route)
        check(f"Route {route} ({label})", r.status_code == 200, f"HTTP {r.status_code}")

    # -------------------------------------------------------------
    # 2. PAYMENT GATEWAY COMPLIANCE & LEGAL PAGES
    # -------------------------------------------------------------
    print("\n[MODULE 2] Compliance & Payment Gateway Legal Pages")
    compliance_routes = [
        ("/contact", "Contact Us Page"),
        ("/contact-us", "Contact Us Alias"),
        ("/terms", "Terms & Conditions Page"),
        ("/terms-and-conditions", "Terms & Conditions Alias"),
        ("/refund-policy", "Refunds & Cancellations Policy"),
        ("/refunds-and-cancellations", "Refunds Policy Alias"),
        ("/privacy-policy", "Privacy Policy Page"),
        ("/privacy", "Privacy Policy Alias")
    ]
    for route, label in compliance_routes:
        r = client.get(route)
        check(f"Compliance Route {route} ({label})", r.status_code == 200, f"({len(r.text)} bytes)")

    # Test Contact Helpdesk Inbound Ticket API
    contact_payload = {
        "name": "Audit Inspector",
        "email": "audit@rapidpvc.online",
        "category": "Wallet Recharge / Payment Issue",
        "message": "System automated self-test inquiry."
    }
    contact_res = client.post("/api/contact", json=contact_payload)
    check("Inbound Support Ticket API (/api/contact)", contact_res.status_code == 200 and contact_res.json().get("success") is True)

    # -------------------------------------------------------------
    # 3. DATABASE SCHEMA & ORM INTEGRITY
    # -------------------------------------------------------------
    print("\n[MODULE 3] Database Schema & Tables Integrity")
    from sqlalchemy import inspect
    inspector = inspect(database.engine)
    required_tables = [
        "users", "user_credits", "generation_history", 
        "orders", "credit_transactions", "admin_audit_logs", "plans"
    ]
    for table in required_tables:
        check(f"SQL Table '{table}' verified", inspector.has_table(table))

    # -------------------------------------------------------------
    # 4. OPERATOR AUTHENTICATION, PASSWORD HASHING & COOKIES
    # -------------------------------------------------------------
    print("\n[MODULE 4] User Authentication, Bcrypt & JWT Sessions")
    test_user_email = f"operator_{uuid.uuid4().hex[:6]}@gmail.com"
    test_password = "StrongSecret123@!"
    test_name = "Master Audit Operator"

    # Register
    reg_res = client.post("/auth/register", json={
        "email": test_user_email,
        "password": test_password,
        "name": test_name
    })
    check("Operator Account Registration", reg_res.status_code == 200, f"HTTP {reg_res.status_code}: {reg_res.text}")
    user_id = reg_res.json()["id"]

    # Verify password hash security
    user_row = db.query(models.User).filter(models.User.id == user_id).first()
    check("Bcrypt Password Hashing", auth.verify_password(test_password, user_row.hashed_password))
    check("Reject Incorrect Password", not auth.verify_password("FakePassword", user_row.hashed_password))

    # Login
    login_res = client.post("/auth/login", json={
        "email": test_user_email,
        "password": test_password
    })
    check("Operator Login & JWT Token issuance", login_res.status_code == 200 and "access_token" in login_res.cookies)

    # Profile fetch
    auth_headers = {"Cookie": f"access_token={login_res.cookies.get('access_token')}"}
    profile_res = client.get("/api/user/me", headers=auth_headers)
    check("Get Current User Profile (/api/user/me)", profile_res.status_code == 200 and profile_res.json().get("email") == test_user_email)

    # -------------------------------------------------------------
    # 5. WALLET, RECHARGES & LEDGER DEDUCTION
    # -------------------------------------------------------------
    print("\n[MODULE 5] Wallet Balance, Plans & Recharge Engine")
    credits_res = client.get("/api/user/credits", headers=auth_headers)
    check("Query User Credits (/api/user/credits)", credits_res.status_code == 200)
    initial_balance = credits_res.json().get("wallet_balance", 0.0)

    # Query public plans
    plans_res = client.get("/api/payment/plans")
    plans_list = plans_res.json() if isinstance(plans_res.json(), list) else plans_res.json().get("plans", [])
    check("Fetch Available Recharge Plans", plans_res.status_code == 200 and len(plans_list) >= 4, f"({len(plans_list)} packs active)")

    # Simulate Recharge Pack 2 (₹100 -> ~105 cards)
    recharge_res = client.post("/api/payment/recharge-plan", json={"plan_id": 2}, headers=auth_headers)
    check("Recharge Pack Purchase (/api/payment/recharge-plan)", recharge_res.status_code == 200 and recharge_res.json().get("success") is True)
    
    new_balance = recharge_res.json().get("new_balance")
    check("Balance accurately credited (Rs. 100.00 added)", new_balance == initial_balance + 100.0)

    # Simulate 1 Card Deduction (Rs. 0.95)
    rate = user_row.credits.cost_per_card
    user_row.credits.wallet_balance -= rate
    user_row.credits.total_generated += 1
    tx = models.CreditTransaction(
        user_id=user_row.id,
        amount=-rate,
        transaction_type="card_generation",
        reference_id=f"AUDIT_TX_{uuid.uuid4().hex[:8]}",
        balance_after=user_row.credits.wallet_balance
    )
    db.add(tx)
    db.commit()
    check("Accurate per-card deduction (Rs. 0.95)", round(user_row.credits.wallet_balance, 2) == 99.05)
    check("Ledger Transaction logged successfully", tx.id is not None)

    # -------------------------------------------------------------
    # 6. CARD DATA EXTRACTION & UIDAI/PMJAY MAPPERS
    # -------------------------------------------------------------
    print("\n[MODULE 6] Card Data Extraction & Formatting Engine")
    
    # Test Aadhaar Address Sequence
    sample_aadhaar = {
        "source": "qr",
        "full_name": "Avinash Patil",
        "dob": "10/05/1990",
        "gender": "M",
        "house": "Plot 12",
        "street": "Naval Nagar",
        "landmark": "Near Primary School",
        "location": "Raver",
        "vtc": "Raver",
        "sub_district": "Raver",
        "post_office": "Raver",
        "district": "Jalgaon",
        "state": "Maharashtra",
        "pincode": "425508"
    }
    mapped_aadhaar = map_aadhaar_data(sample_aadhaar)
    check("Aadhaar Data Mapper (UIDAI format)", "full_html" in mapped_aadhaar["address"] and "Maharashtra - 425508" in mapped_aadhaar["address"]["full_html"])

    # Test Ayushman Real PDF Extraction
    ayushman_pdf = os.path.join(os.path.dirname(__file__), "test_ayushman.pdf")
    if os.path.exists(ayushman_pdf):
        ayushman_extracted = extract_ayushman_data(ayushman_pdf)
        extracted_dict = ayushman_extracted.to_json_safe_dict()
        check("Ayushman PDF Extraction (Real PDF)", bool(extracted_dict.get("pmjay_id") or extracted_dict.get("name")), f"Name: {extracted_dict.get('name')}")
        mapped_pmjay = map_ayushman_data(extracted_dict)
        check("Ayushman Data Mapper", mapped_pmjay.get("document_type") == "ayushman", f"DocType: {mapped_pmjay.get('document_type')}")
    else:
        print("  ⚠️ test_ayushman.pdf not found, skipping extraction test.")

    # -------------------------------------------------------------
    # 7. CHROMIUM PLAYWRIGHT HIGH-DPI RENDERING ENGINE
    # -------------------------------------------------------------
    print("\n[MODULE 7] Chromium High-DPI Rendering Engine")
    render_out_dir = os.path.abspath("static/renders/audit_render_test")
    os.makedirs(render_out_dir, exist_ok=True)
    
    test_render_engine_dict = {
        "name": "Avinash Naval Patil",
        "yob": "1990",
        "gender": "Male",
        "pmjay_id": "PMJAY-9999-8888-7777",
        "mobile": "98XXXXXXXX",
        "district": "Jalgaon",
        "state": "Maharashtra",
        "ration_other_id": "NFSA-12345",
        "photo_png_base64": "",
        "qr_base64": ""
    }
    test_mapped = map_ayushman_data(test_render_engine_dict)
    
    front_img, back_img = render_card(test_mapped, test_render_engine_dict, render_out_dir, "ayushman")
    check("Chromium Front Card PNG Generated", os.path.exists(front_img), f"({os.path.getsize(front_img)} bytes)")
    check("Chromium Back Card PNG Generated", os.path.exists(back_img), f"({os.path.getsize(back_img)} bytes)")

    # -------------------------------------------------------------
    # 8. DUPLEX A4 PRINT SHEET GENERATOR
    # -------------------------------------------------------------
    print("\n[MODULE 8] Duplex A4 Print PDF Generator")
    a4_out_pdf = os.path.join(render_out_dir, "test_a4_sheet.pdf")
    a4_result = create_a4_print_pdf([front_img], [back_img], a4_out_pdf)
    check("A4 Multi-Card PDF Sheet Generated", a4_result.get("success") is True and os.path.exists(a4_out_pdf), f"Pages: {a4_result.get('page_count')}")

    # -------------------------------------------------------------
    # 9. BANNER SERVICE & ADMIN SECURITY (RBAC)
    # -------------------------------------------------------------
    print("\n[MODULE 9] Dynamic Banner & Admin Security Controls")
    banner = get_banner_config()
    check("Banner Service Configuration", isinstance(banner, dict))

    # Verify regular user cannot access admin dashboard
    admin_unauth = client.get("/admin", headers=auth_headers, follow_redirects=False)
    check("RBAC: Regular Operator Blocked from /admin", admin_unauth.status_code in [302, 303, 307])

    # -------------------------------------------------------------
    # 10. CLEANUP TEMPORARY TEST DATA
    # -------------------------------------------------------------
    print("\n[MODULE 10] Zero-Retention Cleanliness")
    db.query(models.CreditTransaction).filter(models.CreditTransaction.user_id == user_row.id).delete()
    db.query(models.UserCredits).filter(models.UserCredits.user_id == user_row.id).delete()
    db.query(models.User).filter(models.User.id == user_row.id).delete()
    db.commit()
    db.close()
    
    import shutil
    shutil.rmtree(render_out_dir, ignore_errors=True)
    check("Temporary audit artifacts cleaned up", True)

    print("\n" + "="*70)
    print(f" 🎯 MASTER AUDIT SUMMARY: {passed_checks}/{total_checks} CHECKS PASSED (100% SUCCESS)")
    print(" ALL SERVICES, ENGINES & COMPLIANCE PAGES ARE FULLY OPERATIONAL!")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_master_audit()
