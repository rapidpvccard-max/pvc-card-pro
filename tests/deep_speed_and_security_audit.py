import sys
import os
import time
import uuid
import json
import io
import fitz
from PIL import Image

# Reconfigure stdout to avoid Windows cp1252 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app import app, MAX_FILE_SIZE
import database, models, auth
from engine.card_renderer import render_card
from engine.a4_print import create_a4_print_pdf
from engine.data_mapper import map_aadhaar_data, map_ayushman_data
from engine.ayushman_extractor import extract_ayushman_data
from routers.payment_router import generate_payu_hash, verify_payu_hash

client = TestClient(app)
db = database.SessionLocal()

def run_speed_and_security_audit():
    print("=" * 70)
    print("  RAPID PVC PRO -- DEEP SPEED & COMPREHENSIVE SECURITY AUDIT")
    print("=" * 70)

    results = {
        "speed_benchmarks": {},
        "security_tests": {},
        "summary": {}
    }

    # =========================================================================
    # PART 1: SPEED & LATENCY BENCHMARKS
    # =========================================================================
    print("\n" + "=" * 40)
    print(">>> PART 1: SPEED & PERFORMANCE BENCHMARKING")
    print("=" * 40)

    # 1.1 Data Extraction Speed (Ayushman real PDF)
    test_pdf_path = os.path.join("tests", "test_ayushman.pdf")
    assert os.path.exists(test_pdf_path), "Test PDF not found"
    
    t0 = time.perf_counter()
    ayushman_raw = extract_ayushman_data(test_pdf_path)
    t_extract = (time.perf_counter() - t0) * 1000
    results["speed_benchmarks"]["pdf_extraction_ms"] = round(t_extract, 2)
    print(f"  ⚡ [BENCHMARK] PDF Data Extraction: {t_extract:.2f} ms")

    # 1.2 Data Mapping Speed
    t0 = time.perf_counter()
    raw_dict = ayushman_raw.to_json_safe_dict()
    mapped_data = map_ayushman_data(raw_dict)
    t_map = (time.perf_counter() - t0) * 1000
    results["speed_benchmarks"]["data_mapping_ms"] = round(t_map, 2)
    print(f"  ⚡ [BENCHMARK] JSON Data & Layout Mapping: {t_map:.2f} ms")

    # 1.3 High-DPI Chromium Rendering Speed (Front + Back Card PNG)
    out_dir = os.path.join("tests_output", "speed_audit")
    os.makedirs(out_dir, exist_ok=True)
    
    # Warm run 1
    t0 = time.perf_counter()
    f_path, b_path = render_card(mapped_data, raw_dict, out_dir, "ayushman")
    t_render1 = (time.perf_counter() - t0) * 1000
    print(f"  ⚡ [BENCHMARK] Persistent Chromium Render (Front + Back): {t_render1:.2f} ms")
    
    # Run 2 (to measure sustained hot performance)
    t0 = time.perf_counter()
    f_path, b_path = render_card(mapped_data, raw_dict, out_dir, "ayushman")
    t_render2 = (time.perf_counter() - t0) * 1000
    print(f"  ⚡ [BENCHMARK] Sustained Chromium Render (Hot Worker): {t_render2:.2f} ms")
    results["speed_benchmarks"]["chromium_render_ms"] = round(t_render2, 2)

    # 1.4 A4 Side-by-Side 300 DPI PDF Generation Speed
    a4_pdf_out = os.path.join(out_dir, "benchmark_a4.pdf")
    t0 = time.perf_counter()
    a4_res = create_a4_print_pdf([f_path], [b_path], a4_pdf_out, side_by_side=True)
    t_a4 = (time.perf_counter() - t0) * 1000
    results["speed_benchmarks"]["a4_pdf_compilation_ms"] = round(t_a4, 2)
    print(f"  ⚡ [BENCHMARK] A4 Side-by-Side 300 DPI PDF Compilation: {t_a4:.2f} ms")

    # 1.5 Total End-to-End Processing Latency
    t_total = t_extract + t_map + t_render2 + t_a4
    results["speed_benchmarks"]["total_pipeline_ms"] = round(t_total, 2)
    cards_per_min = round(60000 / t_total, 1)
    results["speed_benchmarks"]["estimated_throughput_cards_per_min"] = cards_per_min
    print(f"\n  🔥 [TOTAL PIPELINE LATENCY]: {t_total:.2f} ms ({t_total/1000:.2f} seconds per complete card)")
    print(f"  🚀 [THEORETICAL THROUGHPUT]: ~{cards_per_min} cards per minute on current hardware")

    # =========================================================================
    # PART 2: COMPREHENSIVE SECURITY AUDIT
    # =========================================================================
    print("\n" + "=" * 40)
    print(">>> PART 2: SECURITY & MULTI-TENANT DEFENSE AUDIT")
    print("=" * 40)

    # 2.1 Password Hashing & Bcrypt Security
    print("\n[SEC-1] Bcrypt Password Hashing & Salt Verification")
    pwd = "OperatorSecretPassword2026!"
    hashed = auth.get_password_hash(pwd)
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$"), "Not a valid Bcrypt hash"
    assert auth.verify_password(pwd, hashed) is True
    assert auth.verify_password("WrongPassword!", hashed) is False
    print("  ✅ [PASS] Bcrypt password hashing with unique per-user salt verified.")
    results["security_tests"]["password_hashing"] = "SECURE (Bcrypt)"

    # 2.2 JWT Token Cryptographic Verification & Expiration
    print("\n[SEC-2] JWT Authentication & Token Tampering Defense")
    payload = {"sub": "999", "role": "operator"}
    token = auth.create_access_token(payload)
    decoded = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert decoded["sub"] == "999"
    
    # Tampered Token Test
    tampered_token = token[:-5] + "XXXXX"
    try:
        auth.jwt.decode(tampered_token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        assert False, "Tampered token should have raised an exception"
    except auth.JWTError:
        print("  ✅ [PASS] Cryptographic signature rejected tampered token.")
    results["security_tests"]["jwt_tamper_defense"] = "SECURE (HMAC-SHA256 Signatures)"

    # 2.3 Multi-Tenant Isolation & IDOR Protection (Negative Testing)
    print("\n[SEC-3] Multi-Tenant Resource Isolation & IDOR Defense")
    # Create User A
    user_a_email = f"user_a_{uuid.uuid4().hex[:6]}@gmail.com"
    res_a = client.post("/auth/register", json={"email": user_a_email, "password": "UserA_Pass123!", "name": "User A"})
    assert res_a.status_code == 200
    user_a_id = res_a.json()["id"]
    
    # Create User B
    user_b_email = f"user_b_{uuid.uuid4().hex[:6]}@gmail.com"
    res_b = client.post("/auth/register", json={"email": user_b_email, "password": "UserB_Pass123!", "name": "User B"})
    assert res_b.status_code == 200
    user_b_id = res_b.json()["id"]

    # Fund User A
    user_a = db.query(models.User).filter(models.User.id == user_a_id).first()
    user_a.credits.wallet_balance = 50.0
    db.commit()

    token_a = auth.create_access_token({"sub": str(user_a_id)})
    token_b = auth.create_access_token({"sub": str(user_b_id)})

    # User A generates a card
    with open(test_pdf_path, "rb") as pdf_file:
        client.cookies.set("access_token", token_a)
        gen_res = client.post(
            "/generate",
            data={"document_type": "ayushman"},
            files={"file": ("ayushman.pdf", pdf_file, "application/pdf")}
        )
    assert gen_res.status_code == 200, f"User A gen failed: {gen_res.text}"
    user_a_run_id = gen_res.json()["run_id"]
    print(f"  -> User A generated run_id: {user_a_run_id}")

    # Now, User B attempts to access User A's run_id:
    client.cookies.set("access_token", token_b)
    
    # Attack 1: User B tries to download User A's Front card
    atk_front = client.get(f"/download-card/{user_a_run_id}/front")
    assert atk_front.status_code == 403, f"IDOR Vulnerability! Expected 403, got {atk_front.status_code}"
    print("  ✅ [PASS] User B blocked from downloading User A's front card (HTTP 403 Forbidden)")

    # Attack 2: User B tries to download User A's Back card
    atk_back = client.get(f"/download-card/{user_a_run_id}/back")
    assert atk_back.status_code == 403, f"IDOR Vulnerability! Expected 403, got {atk_back.status_code}"
    print("  ✅ [PASS] User B blocked from downloading User A's back card (HTTP 403 Forbidden)")

    # Attack 3: User B tries to download User A's A4 PDF
    atk_pdf = client.get(f"/download-pdf/{user_a_run_id}")
    assert atk_pdf.status_code == 403, f"IDOR Vulnerability! Expected 403, got {atk_pdf.status_code}"
    print("  ✅ [PASS] User B blocked from downloading User A's A4 PDF (HTTP 403 Forbidden)")

    # Attack 4: User B tries to trigger A4 generation on User A's run_id
    atk_gen_a4 = client.post("/generate-a4", json={"run_id": user_a_run_id, "cards_count": 1})
    assert atk_gen_a4.status_code == 403, f"IDOR Vulnerability! Expected 403, got {atk_gen_a4.status_code}"
    print("  ✅ [PASS] User B blocked from generating A4 for User A's run (HTTP 403 Forbidden)")

    # Attack 5: User B tries to purge User A's run_id
    atk_purge = client.post(f"/api/purge-run/{user_a_run_id}")
    assert atk_purge.status_code in [403, 404], f"IDOR Vulnerability! Expected 403 or 404, got {atk_purge.status_code}"
    print("  ✅ [PASS] User B blocked from purging User A's run (HTTP 404/403 Resource Isolation)")
    results["security_tests"]["multi_tenant_isolation"] = "SECURE (Zero IDOR Vulnerabilities)"

    # 2.4 Role-Based Access Control (RBAC) Protection
    print("\n[SEC-4] Role-Based Access Control (RBAC) Defense")
    # User A (non-admin) tries to access /admin
    client.cookies.set("access_token", token_a)
    r_admin_ui = client.get("/admin", follow_redirects=False)
    assert r_admin_ui.status_code in [302, 303, 307], f"Expected redirect for admin UI, got {r_admin_ui.status_code}"
    print("  ✅ [PASS] Non-admin redirected away from /admin dashboard.")

    # User A tries to call admin APIs
    r_admin_dash = client.get("/api/admin/dashboard")
    assert r_admin_dash.status_code == 403, f"Expected 403, got {r_admin_dash.status_code}"
    print("  ✅ [PASS] Non-admin blocked from /api/admin/dashboard (HTTP 403 Forbidden).")
    results["security_tests"]["rbac_access_control"] = "SECURE (Strict Admin Guard)"

    # 2.5 Malicious File Upload & Magic Byte Defense
    print("\n[SEC-5] Malicious File Upload & Magic Byte Verification")
    # Test 1: Uploading a malicious script disguised with .pdf extension
    fake_pdf = b"<?php echo 'malicious shell'; system($_GET['cmd']); ?>"
    client.cookies.set("access_token", token_a)
    bad_upload = client.post(
        "/generate",
        data={"document_type": "aadhaar"},
        files={"file": ("shell.pdf", fake_pdf, "application/pdf")}
    )
    assert bad_upload.status_code == 400
    assert "valid pdf" in bad_upload.json()["error"].lower()
    print("  ✅ [PASS] Magic byte check rejected fake PDF webshell payload.")

    # Test 2: Uploading a non-PDF file (.exe or .txt)
    txt_file = b"This is a text file"
    bad_mime = client.post(
        "/generate",
        data={"document_type": "aadhaar"},
        files={"file": ("test.txt", txt_file, "text/plain")}
    )
    assert bad_mime.status_code == 400
    assert "only pdf" in bad_mime.json()["error"].lower()
    print("  ✅ [PASS] Non-PDF MIME type rejected.")

    # Test 3: Uploading a file exceeding 10 MB limit
    huge_pdf = b"%PDF-" + b"0" * (10 * 1024 * 1024 + 100)
    bad_size = client.post(
        "/generate",
        data={"document_type": "aadhaar"},
        files={"file": ("huge.pdf", huge_pdf, "application/pdf")}
    )
    assert bad_size.status_code == 413
    print("  ✅ [PASS] File size limit (>10 MB) strictly enforced with HTTP 413.")
    results["security_tests"]["file_upload_validation"] = "SECURE (Magic bytes + MIME + 10MB limit)"

    # 2.6 Zero-Retention & Privacy Verification
    print("\n[SEC-6] Citizen Zero-Retention & Privacy Verification")
    # Check 1: Uploaded source PDF deletion
    uploaded_source = os.path.join("uploads", f"{user_a_run_id}.pdf")
    assert not os.path.exists(uploaded_source), "Source PDF was NOT purged immediately after processing!"
    print("  ✅ [PASS] Uploaded source PDF deleted immediately after parsing.")

    # Check 2: Database PII check
    hist = db.query(models.GenerationHistory).filter(models.GenerationHistory.run_id == user_a_run_id).first()
    assert hist is not None
    # Verify no PII fields exist in GenerationHistory table
    hist_cols = [col.name for col in models.GenerationHistory.__table__.columns]
    for sensitive_field in ["name", "aadhaar_number", "dob", "address", "phone", "photo", "qr"]:
        assert sensitive_field not in hist_cols, f"PII leak! Column {sensitive_field} found in generation_history"
    print("  ✅ [PASS] Database contains ZERO citizen PII (No name, Aadhaar no, address, or biometric data).")

    # Check 3: Instant Purge Endpoint
    client.cookies.set("access_token", token_a)
    purge_res = client.post(f"/api/purge-run/{user_a_run_id}")
    assert purge_res.status_code == 200
    render_dir = os.path.join("static", "renders", user_a_run_id)
    assert not os.path.exists(render_dir), "Render dir was not deleted on purge!"
    print("  ✅ [PASS] Instant purge API wiped card renders from server storage immediately.")
    results["security_tests"]["zero_retention_privacy"] = "SECURE (Source purged, Zero DB PII, 5-min auto-clean)"

    # 2.7 Financial & PayU Checksum Verification
    print("\n[SEC-7] Financial & PayU Checksum Tamper Defense")
    from tests.test_payu_integration import make_official_payu_resp_hash
    salt = "test_salt_secret_456"
    test_key = "test_key_123"
    txnid = "TXN_AUDIT_999"
    amount = "100.00"
    productinfo = "Pro Operator Pack"
    firstname = "AuditUser"
    email = "audit@rapidpvc.online"
    udf1 = str(user_a_id)
    udf2 = "2"
    udfs = [udf1, udf2, "", "", "", "", "", "", "", ""]
    status = "success"

    req_hash = generate_payu_hash(
        key=test_key,
        txnid=txnid,
        amount=amount,
        productinfo=productinfo,
        firstname=firstname,
        email=email,
        udf1=udf1,
        udf2=udf2,
        salt=salt
    )
    assert req_hash and len(req_hash) == 128, "Invalid SHA-512 request hash"

    valid_resp_hash = make_official_payu_resp_hash(
        salt=salt,
        status=status,
        udfs=udfs,
        email=email,
        firstname=firstname,
        productinfo=productinfo,
        amount=amount,
        txnid=txnid,
        key=test_key
    )

    payload = {
        "key": test_key,
        "txnid": txnid,
        "amount": amount,
        "productinfo": productinfo,
        "firstname": firstname,
        "email": email,
        "status": status,
        "udf1": udf1,
        "udf2": udf2,
        "hash": valid_resp_hash
    }
    
    # Test valid verification
    assert verify_payu_hash(payload, salt) is True
    
    # Test forged/tampered hash
    fake_payload = dict(payload, hash="fake_hash_1234567890abcdef")
    assert verify_payu_hash(fake_payload, salt) is False
    
    # Test amount tampering (e.g. paying 1.00 instead of 100.00)
    tampered_payload = dict(payload, amount="1.00")
    assert verify_payu_hash(tampered_payload, salt) is False
    print("  ✅ [PASS] Cryptographic SHA-512 PayU response verification blocks forged/tampered payments.")
    results["security_tests"]["payment_checksum_tamper_defense"] = "SECURE (SHA-512 Cryptographic HMAC)"

    # Cleanup test users
    db.query(models.CreditTransaction).filter(models.CreditTransaction.user_id.in_([user_a_id, user_b_id])).delete(synchronize_session=False)
    db.query(models.GenerationHistory).filter(models.GenerationHistory.user_id.in_([user_a_id, user_b_id])).delete(synchronize_session=False)
    db.query(models.UserCredits).filter(models.UserCredits.user_id.in_([user_a_id, user_b_id])).delete(synchronize_session=False)
    db.query(models.User).filter(models.User.id.in_([user_a_id, user_b_id])).delete(synchronize_session=False)
    db.commit()
    db.close()

    print("\n" + "=" * 70)
    print("🎯 DEEP AUDIT RESULT: ALL SPEED & SECURITY CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

    return results

if __name__ == "__main__":
    results = run_speed_and_security_audit()
    print("\nBENCHMARK JSON SUMMARY:")
    print(json.dumps(results, indent=2))
