import sys
import os
os.environ["TESTING"] = "1"
import uuid
import hmac
import hashlib
import base64
import json
from unittest.mock import patch, MagicMock

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    reconfig = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig):
        reconfig(encoding='utf-8')
except Exception:
    pass

from fastapi.testclient import TestClient
from app import app
import database
import models
import auth
from routers.payment_router import (
    verify_cashfree_signature,
    _process_cashfree_payment_success,
    get_cashfree_base_url,
    get_cashfree_headers
)

client = TestClient(app)

TEST_CF_APP_ID = "CF_TEST_APP_123456"
TEST_CF_SECRET_KEY = "cf_test_secret_key_abcdef123456"


def generate_test_cf_signature(raw_body: str, timestamp: str, secret_key: str) -> str:
    message = f"{timestamp}{raw_body}"
    hash_obj = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    return base64.b64encode(hash_obj.digest()).decode("utf-8")


def run_cashfree_audit():
    print("\n" + "=" * 70)
    print(" 🚀 RAPID PVC PRO -- CASHFREE INTEGRATION COMPREHENSIVE TEST SUITE")
    print("=" * 70)

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

    # ----------------------------------------------------
    # TEST 1: Cryptographic Webhook HMAC-SHA256 Signature Verification
    # ----------------------------------------------------
    sample_body = json.dumps({
        "data": {
            "order": {"order_id": "cf_test_order_001", "order_amount": 100.0, "order_currency": "INR"},
            "payment": {"cf_payment_id": "12345678", "payment_status": "SUCCESS", "payment_amount": 100.0}
        },
        "type": "PAYMENT_SUCCESS_WEBHOOK"
    })
    timestamp = "1727600000"

    valid_signature = generate_test_cf_signature(sample_body, timestamp, TEST_CF_SECRET_KEY)
    check("Cashfree HMAC-SHA256 Valid Signature Verification",
          verify_cashfree_signature(sample_body, timestamp, valid_signature, TEST_CF_SECRET_KEY) is True)

    # Tampered Payload Defense
    tampered_body = sample_body.replace("100.0", "1000.0")
    check("Tampered Payload Rejection Defense",
          verify_cashfree_signature(tampered_body, timestamp, valid_signature, TEST_CF_SECRET_KEY) is False)

    # Tampered Timestamp Defense
    tampered_timestamp = "1727600099"
    check("Tampered Timestamp Rejection Defense",
          verify_cashfree_signature(sample_body, tampered_timestamp, valid_signature, TEST_CF_SECRET_KEY) is False)

    # Wrong Secret Key Defense
    check("Wrong Secret Key Rejection Defense",
          verify_cashfree_signature(sample_body, timestamp, valid_signature, "wrong_secret_key") is False)

    # ----------------------------------------------------
    # TEST 2: Payment Gateways Config API
    # ----------------------------------------------------
    res_gw = client.get("/api/payment/gateways")
    check("Gateways Config API Status 200", res_gw.status_code == 200)
    gw_json = res_gw.json()
    check("Gateways API returns Cashfree & PayU status",
          "cashfree" in gw_json and "payu" in gw_json and "default_gateway" in gw_json)

    # ----------------------------------------------------
    # TEST 3: Order Initiation Authentication & Unconfigured Check
    # ----------------------------------------------------
    res_unauth = client.post("/api/payment/cashfree/initiate", json={"plan_id": 1})
    check("Unauthenticated Initiate Request Rejected (401)", res_unauth.status_code == 401)

    # Prepare Test User
    db = database.SessionLocal()
    test_email = f"cf_tester_{uuid.uuid4().hex[:6]}@rapidpvc.online"
    test_user = models.User(
        email=test_email,
        name="Cashfree Tester",
        hashed_password=auth.get_password_hash("testpass123")
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)

    auth_token = auth.create_access_token(data={"sub": str(test_user.id)})
    headers = {"Authorization": f"Bearer {auth_token}"}

    # ----------------------------------------------------
    # TEST 4: Initiate Cashfree Payment with Mocked Cashfree PG API
    # ----------------------------------------------------
    with patch.dict(os.environ, {
        "CASHFREE_APP_ID": TEST_CF_APP_ID,
        "CASHFREE_SECRET_KEY": TEST_CF_SECRET_KEY,
        "CASHFREE_ENV": "sandbox"
    }):
        fake_session_id = f"session_{uuid.uuid4().hex[:16]}"
        fake_cf_resp = MagicMock()
        fake_cf_resp.status_code = 200
        fake_cf_resp.json.return_value = {
            "cf_order_id": "1234567",
            "order_id": "cf_test_order_123",
            "payment_session_id": fake_session_id,
            "order_status": "ACTIVE"
        }

        with patch("requests.post", return_value=fake_cf_resp):
            res_init = client.post("/api/payment/cashfree/initiate", json={"plan_id": 2}, headers=headers)
            check("Cashfree Initiate Endpoint Status 200", res_init.status_code == 200)
            init_data = res_init.json()
            check("Initiate Returns payment_session_id", init_data.get("payment_session_id") == fake_session_id)
            check("Initiate Returns order_id starting with 'cf_'", str(init_data.get("order_id", "")).startswith("cf_"))

            created_order_id = init_data.get("order_id")
            order_in_db = db.query(models.Order).filter(models.Order.provider_order_id == created_order_id).first()
            check("Order stored in DB with pending status & gateway='cashfree'",
                  order_in_db is not None and order_in_db.status == "pending" and order_in_db.gateway == "cashfree")

    # ----------------------------------------------------
    # TEST 5: Cashfree Return Verification Handler (PAID Flow)
    # ----------------------------------------------------
    fake_status_resp = MagicMock()
    fake_status_resp.status_code = 200
    fake_status_resp.json.return_value = {
        "cf_order_id": "1234567",
        "order_id": created_order_id,
        "order_status": "PAID",
        "order_amount": 100.0,
        "order_currency": "INR"
    }

    fake_pay_resp = MagicMock()
    fake_pay_resp.status_code = 200
    fake_pay_resp.json.return_value = [{
        "cf_payment_id": "99887766",
        "payment_status": "SUCCESS",
        "payment_amount": 100.0
    }]

    def mock_requests_get(url, *args, **kwargs):
        if "payments" in url:
            return fake_pay_resp
        return fake_status_resp

    with patch.dict(os.environ, {
        "CASHFREE_APP_ID": TEST_CF_APP_ID,
        "CASHFREE_SECRET_KEY": TEST_CF_SECRET_KEY
    }):
        with patch("requests.get", side_effect=mock_requests_get):
            res_return = client.get(f"/api/payment/cashfree/return?order_id={created_order_id}", follow_redirects=False)
            check("Return URL Redirects 303 Upon Payment Success", res_return.status_code == 303)
            check("Redirect Location points to /subscription?payment=success",
                  "/subscription?payment=success" in res_return.headers.get("location", ""))

            # Verify DB Order and User Credits
            db.refresh(order_in_db)
            check("Order status updated to 'paid'", order_in_db.status == "paid")
            check("Order provider_payment_id recorded", order_in_db.provider_payment_id == "99887766")

            user_credits = db.query(models.UserCredits).filter(models.UserCredits.user_id == test_user.id).first()
            check("Wallet Balance incremented by plan amount (₹100)",
                  user_credits is not None and float(user_credits.wallet_balance) == 100.0)
            check("Per-card printing rate unlocked at ₹0.95",
                  user_credits is not None and float(user_credits.cost_per_card) == 0.95)

            # Idempotency Test: Repeat Return call
            res_return_dup = client.get(f"/api/payment/cashfree/return?order_id={created_order_id}", follow_redirects=False)
            check("Duplicate Return Call Handled Gracefully", res_return_dup.status_code == 303)
            db.refresh(user_credits)
            check("Idempotency: Wallet Balance NOT doubled on duplicate return",
                  float(user_credits.wallet_balance) == 100.0)

    # ----------------------------------------------------
    # TEST 6: Cashfree Server Webhook Handler & Idempotency
    # ----------------------------------------------------
    # Create another order for webhook test
    webhook_order_id = f"cf_{uuid.uuid4().hex[:16]}"
    wh_order = models.Order(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        provider_order_id=webhook_order_id,
        plan_id=1,  # Trial Pack (₹20)
        amount=20.0,
        currency="INR",
        status="pending",
        gateway="cashfree"
    )
    db.add(wh_order)
    db.commit()

    webhook_payload_dict = {
        "data": {
            "order": {"order_id": webhook_order_id, "order_amount": 20.0, "order_currency": "INR"},
            "payment": {"cf_payment_id": "wh_pay_112233", "payment_status": "SUCCESS", "payment_amount": 20.0}
        },
        "event_time": "2026-09-29T10:00:00Z",
        "type": "PAYMENT_SUCCESS_WEBHOOK"
    }
    wh_raw_body = json.dumps(webhook_payload_dict)
    wh_timestamp = "1727601000"
    wh_sig = generate_test_cf_signature(wh_raw_body, wh_timestamp, TEST_CF_SECRET_KEY)

    with patch.dict(os.environ, {"CASHFREE_SECRET_KEY": TEST_CF_SECRET_KEY}):
        # Bad signature test
        res_bad_sig = client.post(
            "/api/payment/cashfree/webhook",
            content=wh_raw_body,
            headers={
                "Content-Type": "application/json",
                "x-webhook-signature": "tampered_sig",
                "x-webhook-timestamp": wh_timestamp
            }
        )
        check("Webhook with Invalid Signature Rejected (400)", res_bad_sig.status_code == 400)

        # Valid signature test
        res_wh = client.post(
            "/api/payment/cashfree/webhook",
            content=wh_raw_body,
            headers={
                "Content-Type": "application/json",
                "x-webhook-signature": wh_sig,
                "x-webhook-timestamp": wh_timestamp
            }
        )
        check("Webhook with Valid Signature Returns 200 OK", res_wh.status_code == 200)

        db.refresh(wh_order)
        check("Webhook Marks Order as 'paid'", wh_order.status == "paid")
        db.refresh(user_credits)
        check("Wallet Balance updated to ₹120 (100 + 20)", float(user_credits.wallet_balance) == 120.0)
        check("Trial Pack sets cost_per_card to ₹2.00", float(user_credits.cost_per_card) == 2.00)

        # Duplicate Webhook Idempotency Check
        res_wh_dup = client.post(
            "/api/payment/cashfree/webhook",
            content=wh_raw_body,
            headers={
                "Content-Type": "application/json",
                "x-webhook-signature": wh_sig,
                "x-webhook-timestamp": wh_timestamp
            }
        )
        check("Duplicate Webhook Processed Without Error", res_wh_dup.status_code == 200, f"(Status: {res_wh_dup.status_code}, Body: {res_wh_dup.text})")
        db.refresh(user_credits)
        check("Idempotency: Wallet Balance remains ₹120 (No Double Credit)", float(user_credits.wallet_balance) == 120.0)

    # ----------------------------------------------------
    # TEST 7: User History Shows Cashfree Gateway Mode
    # ----------------------------------------------------
    res_history = client.get("/api/user/history", headers=headers)
    check("User History Endpoint Status 200", res_history.status_code == 200)
    hist_json = res_history.json()
    recharges = hist_json.get("recharges", [])
    cf_recharges = [r for r in recharges if "Cashfree" in r.get("payment_mode", "")]
    check("User History contains recharges with 'Cashfree / UPI' payment mode", len(cf_recharges) > 0)

    db.close()

    print("\n" + "=" * 70)
    print(f" 📊 AUDIT RESULT: {passed_checks}/{total_checks} CHECKS PASSED")
    if passed_checks == total_checks:
        print(" 🎉 ALL CASHFREE INTEGRATION CHECKS PASSED PERFECTLY!\n")
        return 0
    else:
        print(" ❌ SOME CHECKS FAILED!\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_cashfree_audit())
