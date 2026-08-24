import requests
import uuid
import time
import os
import sqlite3
import json
import hmac
import hashlib

BASE_URL = "http://127.0.0.1:8000"
STRIPE_WEBHOOK_SECRET = "whsec_dummy" # Assuming this is loaded in .env for local tests
os.environ["STRIPE_WEBHOOK_SECRET"] = STRIPE_WEBHOOK_SECRET

def generate_stripe_signature(payload, secret):
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload}"
    sig = hmac.new(secret.encode('utf-8'), signed_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"

def run_tests():
    report = []
    
    def log(test_id, msg, passed):
        status = "PASS" if passed else "FAIL"
        report.append(f"[{status}] {test_id}: {msg}")
        print(f"[{status}] {test_id}: {msg}")

    s_user = requests.Session()
    email_u = f"user_{uuid.uuid4().hex}@test.com"
    s_user.post(f"{BASE_URL}/auth/register", json={"name": "Test User", "email": email_u, "password": "123"})
    s_user.post(f"{BASE_URL}/auth/login", json={"email": email_u, "password": "123"})
    
    dash_u = s_user.get(f"{BASE_URL}/api/user/dashboard").json()
    user_id = dash_u["user"]["id"]
    initial_credits = dash_u["credits"]["remaining_cards"]
    
    # 1. Create Order manually in DB for webhook test (bypassing stripe.checkout.Session.create since we don't have real keys here)
    conn = sqlite3.connect("app.db")
    c = conn.cursor()
    order_id = str(uuid.uuid4())
    c.execute("INSERT INTO orders (id, user_id, provider_order_id, plan_id, amount, currency, status) VALUES (?, ?, ?, ?, ?, ?, ?)", 
              (order_id, user_id, f"cs_test_{uuid.uuid4().hex}", 1, 5.0, "USD", "pending"))
    conn.commit()
    conn.close()
    
    log(1, "Test Order Created in DB", True)

    payment_intent = f"pi_test_{uuid.uuid4().hex}"

    # 2. Simulate valid checkout.session.completed webhook
    payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": f"cs_test_{uuid.uuid4().hex}",
                "payment_status": "paid",
                "payment_intent": payment_intent,
                "metadata": {
                    "order_id": str(order_id)
                }
            }
        }
    })
    
    headers = {"stripe-signature": generate_stripe_signature(payload, STRIPE_WEBHOOK_SECRET)}
    r_wh1 = requests.post(f"{BASE_URL}/api/payment/webhook", data=payload, headers=headers)
    log(2, "Valid webhook accepted", r_wh1.status_code == 200)

    dash_u2 = s_user.get(f"{BASE_URL}/api/user/dashboard").json()
    credits_after_pay = dash_u2["credits"]["remaining_cards"]
    log(3, "Credits incremented correctly (purchase)", credits_after_pay == initial_credits + 10)
    
    # 4. Idempotency test (resend same webhook)
    r_wh2 = requests.post(f"{BASE_URL}/api/payment/webhook", data=payload, headers=headers)
    dash_u3 = s_user.get(f"{BASE_URL}/api/user/dashboard").json()
    log(4, "Duplicate webhook idempotency (credits not duplicated)", dash_u3["credits"]["remaining_cards"] == credits_after_pay)

    # 5. Invalid signature test
    bad_headers = {"stripe-signature": "t=123,v1=bad_sig"}
    r_wh_bad = requests.post(f"{BASE_URL}/api/payment/webhook", data=payload, headers=bad_headers)
    log(5, "Invalid signature rejected", r_wh_bad.status_code == 400)

    # 6. Refund test
    refund_payload = json.dumps({
        "type": "charge.refunded",
        "data": {
            "object": {
                "payment_intent": payment_intent
            }
        }
    })
    
    refund_headers = {"stripe-signature": generate_stripe_signature(refund_payload, STRIPE_WEBHOOK_SECRET)}
    r_wh_refund = requests.post(f"{BASE_URL}/api/payment/webhook", data=refund_payload, headers=refund_headers)
    log(6, "Valid refund webhook accepted", r_wh_refund.status_code == 200)

    dash_u4 = s_user.get(f"{BASE_URL}/api/user/dashboard").json()
    credits_after_refund = dash_u4["credits"]["remaining_cards"]
    log(7, "Credits decremented correctly (refund)", credits_after_refund == initial_credits)
    
    # 8. Refund idempotency
    requests.post(f"{BASE_URL}/api/payment/webhook", data=refund_payload, headers=refund_headers)
    dash_u5 = s_user.get(f"{BASE_URL}/api/user/dashboard").json()
    log(8, "Duplicate refund idempotency", dash_u5["credits"]["remaining_cards"] == initial_credits)

    print("\n--- RESULTS ---")
    print("\n".join(report))

if __name__ == "__main__":
    run_tests()
