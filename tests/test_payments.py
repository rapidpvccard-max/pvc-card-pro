import requests
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

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

def test_payment_flow(plan_id):
    print("Initiating plan recharge...")
    r = session.post(f"{BASE_URL}/api/payment/recharge-plan", json={"plan_id": plan_id})
    assert r.status_code == 200
    res_data = r.json()
    assert res_data.get("success") == True
    print(f"Recharge success! Message: {res_data.get('message')}")
    
    # Verify Balance
    r_dash = session.get(f"{BASE_URL}/api/user/dashboard")
    assert r_dash.status_code == 200
    dash = r_dash.json()
    print(f"Wallet balance: ₹{dash['credits']['wallet_balance']}")
    print(f"Total TX: {len(dash['transactions'])}")
    assert dash['credits']['wallet_balance'] >= 20.0
    print("[PASS] Payment & wallet recharge verification passed!")

if __name__ == "__main__":
    setup_auth()
    plan = test_plans()
    test_payment_flow(plan["id"])
