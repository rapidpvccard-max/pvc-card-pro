import requests
import json
import os

BASE_URL = "http://127.0.0.1:8000"
session = requests.Session()

def setup_auth():
    print("Setting up test user for payments...")
    session.post(f"{BASE_URL}/auth/register", json={
        "name": "Payment Tester",
        "email": "payment@test.com",
        "password": "password123"
    })
    
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "payment@test.com",
        "password": "password123"
    })
    assert r.status_code == 200

def test_plans():
    r = session.get(f"{BASE_URL}/api/payment/plans")
    assert r.status_code == 200
    plans = r.json()
    assert len(plans) > 0
    print(f"Found {len(plans)} active plans.")
    return plans[0]

def test_mock_payment_flow(plan_id):
    print("Initiating checkout...")
    r = session.post(f"{BASE_URL}/api/payment/create-order", json={"plan_id": plan_id})
    assert r.status_code == 200
    order_data = r.json()
    checkout_url = order_data["checkout_url"]
    order_id = order_data["order_id"]
    
    print(f"Order created! URL: {checkout_url}")
    
    # Extract session_id from URL
    session_id = checkout_url.split("session_id=")[1]
    
    print("Simulating webhook payment success...")
    r_webhook = session.post(f"{BASE_URL}/api/payment/mock-webhook", data={"session_id": session_id})
    assert r_webhook.status_code in [200, 303]
    print("Webhook success!")
    
    # Test Idempotency
    print("Simulating DUPLICATE webhook payment success...")
    r_webhook2 = session.post(f"{BASE_URL}/api/payment/mock-webhook", data={"session_id": session_id})
    assert r_webhook2.status_code == 200
    assert r_webhook2.json().get("status") == "already paid"
    print("Duplicate webhook handled correctly.")
    
    # Verify Balance
    r_dash = session.get(f"{BASE_URL}/api/user/dashboard")
    dash = r_dash.json()
    print(f"Wallet balance: ₹{dash['credits']['wallet_balance']}")
    print(f"Total TX: {len(dash['transactions'])}")

if __name__ == "__main__":
    setup_auth()
    plan = test_plans()
    test_mock_payment_flow(plan["id"])
