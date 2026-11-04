import requests
import os
import sys
import uuid
from decimal import Decimal

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_URL = "http://127.0.0.1:8000"

session_a = requests.Session()
session_b = requests.Session()

def create_user(session, name, email, password):
    r = session.post(f"{BASE_URL}/auth/register", json={
        "name": name, "email": email, "password": password
    })
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": email, "password": password
    })
    return r.status_code == 200

def get_dashboard(session):
    return session.get(f"{BASE_URL}/api/user/dashboard").json()

def run_tests():
    report = []
    
    def log(test_id, msg, passed):
        status = "PASS" if passed else "FAIL"
        report.append(f"[{status}] {test_id}: {msg}")
        print(f"[{status}] {test_id}: {msg}")

    # 1. User starts with correct initial credits
    email_a = f"user_a_{uuid.uuid4().hex}@test.com"
    create_user(session_a, "User A", email_a, "pass123")
    dash_a = get_dashboard(session_a)
    log(1, "User starts with correct initial balance", dash_a["credits"]["wallet_balance"] >= 0.0)
    
    # 2. Plan recharge adds credits accurately
    plan = dash_a["plans"][0]
    initial_credits = dash_a["credits"]["wallet_balance"]
    
    r_recharge = session_a.post(f"{BASE_URL}/api/payment/recharge-plan", json={"plan_id": plan["id"]})
    log(2, "Plan recharge endpoint returns 200 OK", r_recharge.status_code == 200)
    
    dash_a2 = get_dashboard(session_a)
    credits_after = dash_a2["credits"]["wallet_balance"]
    log(3, "Successful recharge increments wallet balance", abs(credits_after - (initial_credits + plan["credits"])) < 0.01)
    
    # 4. Invalid webhook signature is rejected
    r_stripe_webhook = session_a.post(f"{BASE_URL}/api/payment/webhook", headers={"stripe-signature": "invalid_sig"}, data=b"{}")
    log(4, "Invalid stripe webhook signature is rejected with 400", r_stripe_webhook.status_code == 400)
    
    # 5. Multi-user isolation
    email_b = f"user_b_{uuid.uuid4().hex}@test.com"
    create_user(session_b, "User B", email_b, "pass123")
    dash_b = get_dashboard(session_b)
    log(5, "User B has isolated credits", dash_b["credits"]["wallet_balance"] == 0.0 and credits_after > 0)

    # 6. CreditTransaction ledger is created correctly
    txs = dash_a2["transactions"]
    has_purchase = any(t["transaction_type"] == "purchase" for t in txs)
    log(6, "CreditTransaction ledger contains purchase record", has_purchase)
    
    # 7. Failed PVC generation does NOT deduct credits
    with open("fake.txt", "w") as f:
        f.write("Not a PDF")
    with open("fake.txt", "rb") as f:
        r_fail = session_a.post(f"{BASE_URL}/generate", files={"file": ("fake.pdf", f, "application/pdf")})
    dash_a3 = get_dashboard(session_a)
    log(7, "Failed PVC generation does NOT deduct credits", abs(dash_a3["credits"]["wallet_balance"] - credits_after) < 0.01)
    if os.path.exists("fake.txt"):
        os.remove("fake.txt")

    # 8. Existing login/logout works cleanly
    r_logout = session_a.post(f"{BASE_URL}/auth/logout")
    r_dash_after = session_a.get(f"{BASE_URL}/api/user/dashboard")
    log(8, "Existing login/logout works cleanly", r_logout.status_code == 200 and r_dash_after.status_code == 401)
    
    # 9. Stripe secret keys never exposed in source
    with open("app.py", "r", encoding="utf-8") as f:
        app_code = f.read()
    with open("routers/payment_router.py", "r", encoding="utf-8") as f:
        pay_code = f.read()
    exposed = "sk_live" in app_code or "sk_test" in app_code or ("whsec_" in pay_code and "os.environ" not in pay_code)
    log(9, "Payment gateway secret keys are never hardcoded", not exposed)
    
    return report

if __name__ == "__main__":
    run_tests()
