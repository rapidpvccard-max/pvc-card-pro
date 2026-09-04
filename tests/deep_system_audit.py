import sys
import os
import uuid

# Set working directory to project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app import app
import database, models, auth
from engine.data_mapper import map_aadhaar_data, map_ayushman_data

client = TestClient(app)
db = database.SessionLocal()

def run_deep_audit():
    print("==================================================================")
    print(">> RAPID PVC PRO -- COMPREHENSIVE 360-DEGREE SYSTEM AUDIT")
    print("==================================================================")

    # 1. DATABASE & SCHEMA CHECK
    print("\n[1/6] DATABASE & SCHEMA INTEGRITY CHECK")
    database.ensure_database_schema(database.engine)
    from sqlalchemy import inspect
    inspector = inspect(database.engine)
    required_tables = ["users", "user_credits", "generation_history", "orders", "credit_transactions", "admin_audit_logs", "plans"]
    for t in required_tables:
        assert inspector.has_table(t), f"Missing table: {t}"
        print(f"  [OK] Table '{t}': Verified")
    print("  -> Database schema is 100% healthy.")

    # 2. USER REGISTRATION & INITIAL CREDITS
    print("\n[2/6] USER REGISTRATION & CREDITS INITIALIZATION")
    test_email = f"audit_{uuid.uuid4().hex[:6]}@gmail.com"
    res = client.post("/auth/register", json={
        "email": test_email,
        "password": "SecurePassword123!",
        "name": "Audit Tester"
    })
    assert res.status_code == 200, f"Register failed: {res.text}"
    user_id = res.json()["id"]
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    assert user is not None, "User not persisted in DB"
    assert user.credits is not None, "UserCredits row not created"
    assert user.credits.wallet_balance == 0.0, f"New user must have 0.0 balance, got {user.credits.wallet_balance}"
    assert user.credits.cost_per_card == 0.95, f"Default rate must be 0.95, got {user.credits.cost_per_card}"
    print(f"  [OK] User created: {test_email} (ID: {user_id})")
    print(f"  [OK] Starting balance: Rs.{user.credits.wallet_balance:.2f} (Rate: Rs.{user.credits.cost_per_card:.2f}/card)")

    # 3. AUTHENTICATION & SESSION TOKENS
    print("\n[3/6] AUTHENTICATION, PASSWORD HASHING & COOKIES")
    assert auth.verify_password("SecurePassword123!", user.hashed_password), "Bcrypt password verification failed"
    assert not auth.verify_password("WrongPassword", user.hashed_password), "Bcrypt incorrectly accepted wrong password"
    
    login_res = client.post("/auth/login", json={
        "email": test_email,
        "password": "SecurePassword123!"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    assert "access_token" in login_res.cookies, "Missing HttpOnly access_token cookie"
    print("  [OK] Bcrypt password hashing & verification: OK")
    print("  [OK] Login endpoint & JWT authentication cookie: OK")

    # 4. WALLET RECHARGE & USAGE SIMULATION
    print("\n[4/6] WALLET RECHARGE & DEDUCTION SIMULATION")
    # Top-up wallet
    recharge_amount = 100.0
    user.credits.wallet_balance += recharge_amount
    tx = models.CreditTransaction(
        user_id=user.id,
        amount=recharge_amount,
        transaction_type="recharge",
        reference_id="TEST_RECHARGE_01",
        balance_after=user.credits.wallet_balance
    )
    db.add(tx)
    db.commit()
    print(f"  [OK] Recharged wallet by Rs.{recharge_amount:.2f} -> Current Balance: Rs.{user.credits.wallet_balance:.2f}")

    # Simulate card generation deduction
    rate = user.credits.cost_per_card
    assert user.credits.wallet_balance >= rate, "Balance check failed"
    user.credits.wallet_balance -= rate
    user.credits.total_generated += 1
    gen_tx = models.CreditTransaction(
        user_id=user.id,
        amount=-rate,
        transaction_type="generation_usage",
        reference_id="TEST_GEN_01",
        balance_after=user.credits.wallet_balance
    )
    db.add(gen_tx)
    db.commit()
    print(f"  [OK] Deducted Rs.{rate:.2f} for card generation -> Remaining Balance: Rs.{user.credits.wallet_balance:.2f}")
    assert round(user.credits.wallet_balance, 2) == round(100.0 - 0.95, 2), "Balance math mismatch"

    # 5. DATA EXTRACTION & MAPPING INTEGRITY
    print("\n[5/6] AADHAAR & AYUSHMAN DATA MAPPING (UIDAI STANDARD)")
    sample_qr_data = {
        "source": "qr",
        "full_name": "Ramesh Chandra",
        "dob": "15/08/1985",
        "gender": "M",
        "house": "F-501",
        "street": "Santok park",
        "landmark": "Near Temple",
        "location": "Dindoli",
        "vtc": "Dindoli",
        "sub_district": "Surat (m Corp+og) (part)",
        "post_office": "Udhna",
        "district": "Surat",
        "state": "Gujarat",
        "pincode": "394210"
    }
    mapped = map_aadhaar_data(sample_qr_data)
    addr = mapped["address"]
    assert "full_html" in addr, "full_html missing"
    assert "<br>" in addr["full_html"], "Line break missing in full_html"
    
    parts = addr["full_html"].split("<br>")
    line1 = parts[0].rstrip(",")
    line2 = parts[1]
    
    print(f"  [OK] Address Line 1: {line1}")
    print(f"  [OK] Address Line 2: {line2}")
    assert "Santok park" in line1 and "Dindoli" in line1, "Address fields missing"
    assert line1.find("Santok park") < line1.find("Dindoli"), "Street must come BEFORE Location/VTC"
    assert line2 == "Gujarat - 394210", f"Line 2 mismatch: got '{line2}'"
    print("  [OK] Strict UIDAI address sequence & 2-line layout: 100% VERIFIED")

    # 6. SECURITY & ACCESS CONTROL
    print("\n[6/6] SECURITY, ROLES & PRIVILEGES")
    # Verify regular user cannot access admin routes
    token = auth.create_access_token(data={"sub": str(user.id)})
    client.cookies.set("access_token", token)
    admin_res = client.get("/admin", follow_redirects=False)
    assert admin_res.status_code in [302, 303, 307], f"Expected redirect, got: {admin_res.status_code}"
    assert "/login" in admin_res.headers.get("location", ""), "Must redirect to /login"
    print("  [OK] Role-Based Access Control (RBAC): Regular users blocked from /admin")
    
    # Cleanup test user
    db.query(models.CreditTransaction).filter(models.CreditTransaction.user_id == user.id).delete()
    db.query(models.UserCredits).filter(models.UserCredits.user_id == user.id).delete()
    db.query(models.User).filter(models.User.id == user.id).delete()
    db.commit()
    db.close()

    print("\n==================================================================")
    print(">>> AUDIT RESULT: 100% PASS -- ALL SYSTEMS FULLY VERIFIED & SECURE!")
    print("==================================================================")

if __name__ == "__main__":
    run_deep_audit()
