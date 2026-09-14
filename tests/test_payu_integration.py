import sys
import os
import uuid
import hashlib

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from fastapi.testclient import TestClient
from app import app
import database
import models
import auth
from routers.payment_router import generate_payu_hash, verify_payu_hash

client = TestClient(app)

TEST_KEY = "HbMDKB"
TEST_SALT = "5zmZRvGOsrXkLcajkaIRWzdDGfZ0WYEB"


def make_official_payu_req_hash(key, txnid, amount, productinfo, firstname, email, udfs, salt):
    """PayU standard request hash."""
    seq = [key, txnid, amount, productinfo, firstname, email] + udfs + [salt]
    return hashlib.sha512("|".join(seq).encode("utf-8")).hexdigest().lower()


def make_official_payu_resp_hash(salt, status, udfs, email, firstname, productinfo, amount, txnid, key, additional_charges=None):
    """PayU standard response reverse hash."""
    rev_udfs = list(reversed(udfs))
    seq = [salt, status] + rev_udfs + [email, firstname, productinfo, amount, txnid, key]
    if additional_charges:
        seq = [additional_charges] + seq
    return hashlib.sha512("|".join(seq).encode("utf-8")).hexdigest().lower()


def run_payu_audit():
    print("\n" + "="*70)
    print(" 💳 RAPID PVC PRO -- PAYU LIVE INTEGRATION TEST SUITE")
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

    # Test 1: Request Hash Calculation
    txnid = f"pvc_{uuid.uuid4().hex[:14]}"
    amount = "100.00"
    productinfo = "Recharge Starter Pack"
    firstname = "Avinash"
    email = "test@rapidpvc.online"
    udf1 = "1"
    udf2 = "2"
    udfs = [udf1, udf2, "", "", "", "", "", "", "", ""]

    expected_hash = make_official_payu_req_hash(
        key=TEST_KEY,
        txnid=txnid,
        amount=amount,
        productinfo=productinfo,
        firstname=firstname,
        email=email,
        udfs=udfs,
        salt=TEST_SALT
    )

    computed_hash = generate_payu_hash(
        key=TEST_KEY,
        txnid=txnid,
        amount=amount,
        productinfo=productinfo,
        firstname=firstname,
        email=email,
        udf1=udf1,
        udf2=udf2,
        salt=TEST_SALT
    )
    check("PayU SHA-512 Request Hash Generation", computed_hash == expected_hash, f"(Hash: {computed_hash[:16]}...)")

    # Test 2: Reverse Hash Verification
    status = "success"
    valid_hash = make_official_payu_resp_hash(
        salt=TEST_SALT,
        status=status,
        udfs=udfs,
        email=email,
        firstname=firstname,
        productinfo=productinfo,
        amount=amount,
        txnid=txnid,
        key=TEST_KEY
    )

    payload = {
        "key": TEST_KEY,
        "txnid": txnid,
        "amount": amount,
        "productinfo": productinfo,
        "firstname": firstname,
        "email": email,
        "status": status,
        "udf1": udf1,
        "udf2": udf2,
        "hash": valid_hash
    }
    check("PayU Reverse Hash Verification (Valid)", verify_payu_hash(payload, TEST_SALT) is True)

    # Test 3: Anti-Tampering Check
    tampered_payload = dict(payload, amount="10.00")
    check("PayU Tampering Detection (Altered Amount Rejected)", verify_payu_hash(tampered_payload, TEST_SALT) is False)

    # Test 4: Additional Charges Hash Verification
    add_charges = "2.50"
    valid_add_hash = make_official_payu_resp_hash(
        salt=TEST_SALT,
        status=status,
        udfs=udfs,
        email=email,
        firstname=firstname,
        productinfo=productinfo,
        amount=amount,
        txnid=txnid,
        key=TEST_KEY,
        additional_charges=add_charges
    )
    payload_add = dict(payload, additionalCharges=add_charges, hash=valid_add_hash)
    check("PayU Additional Charges Hash Verification", verify_payu_hash(payload_add, TEST_SALT) is True)

    # Test 5: End-to-End API Initiate Flow
    db = next(database.get_db())
    test_user = db.query(models.User).filter(models.User.email == "payu_test_user@rapidpvc.online").first()
    if not test_user:
        test_user = models.User(
            name="Avinash Patil",
            email="payu_test_user@rapidpvc.online",
            status="active"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)

    user_cred = db.query(models.UserCredits).filter(models.UserCredits.user_id == test_user.id).first()
    if not user_cred:
        user_cred = models.UserCredits(user_id=test_user.id, wallet_balance=25.0, cost_per_card=0.95)
        db.add(user_cred)
        db.commit()
    initial_balance = float(user_cred.wallet_balance or 0.0)

    token = auth.create_access_token(data={"sub": str(test_user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    res_init = client.post("/api/payment/payu/initiate", json={"plan_id": 2}, headers=headers)
    check("API /api/payment/payu/initiate Status 200", res_init.status_code == 200)

    init_json = res_init.json()
    check("PayU Target URL is secure.payu.in/_payment", init_json.get("action") == "https://secure.payu.in/_payment")
    params = init_json.get("params", {})
    init_txnid = params.get("txnid", "")
    check("Transaction ID generated", bool(init_txnid and init_txnid.startswith("pvc_")))
    check("Initiate Payload contains valid Hash", bool(params.get("hash") and len(params.get("hash")) == 128))

    # Check pending order created in database
    db.expire_all()
    pending_order = db.query(models.Order).filter(models.Order.provider_order_id == init_txnid).first()
    check("Pending Order Recorded in Database", pending_order is not None and pending_order.status == "pending")

    # Test 6: Callback to /api/payment/payu/success
    cb_status = "success"
    mihpayid = f"payu_mih_{uuid.uuid4().hex[:10]}"
    cb_udfs = [params.get("udf1", ""), params.get("udf2", ""), "", "", "", "", "", "", "", ""]
    cb_hash = make_official_payu_resp_hash(
        salt=TEST_SALT,
        status=cb_status,
        udfs=cb_udfs,
        email=params["email"],
        firstname=params["firstname"],
        productinfo=params["productinfo"],
        amount=params["amount"],
        txnid=init_txnid,
        key=TEST_KEY
    )

    cb_form = {
        "key": TEST_KEY,
        "txnid": init_txnid,
        "amount": params["amount"],
        "productinfo": params["productinfo"],
        "firstname": params["firstname"],
        "email": params["email"],
        "status": cb_status,
        "mihpayid": mihpayid,
        "udf1": params["udf1"],
        "udf2": params["udf2"],
        "hash": cb_hash
    }

    res_cb = client.post("/api/payment/payu/success", data=cb_form, follow_redirects=False)
    check("Success Callback HTTP 303 Redirect", res_cb.status_code == 303)
    check("Redirect to /subscription?payment=success", "payment=success" in res_cb.headers.get("location", ""))

    # Verify wallet topped up
    db.expire_all()
    paid_order = db.query(models.Order).filter(models.Order.provider_order_id == init_txnid).first()
    check("Order Marked Paid in Database", paid_order is not None and paid_order.status == "paid")

    updated_cred = db.query(models.UserCredits).filter(models.UserCredits.user_id == test_user.id).first()
    expected_balance = initial_balance + float(params["amount"])
    check("Wallet Balance Credited Exactly", abs(float(updated_cred.wallet_balance) - expected_balance) < 0.01, f"(Old: ₹{initial_balance:.2f} -> New: ₹{updated_cred.wallet_balance:.2f})")

    # Test 7: Idempotency (Duplicate Callback Protection)
    res_cb_dup = client.post("/api/payment/payu/success", data=cb_form, follow_redirects=False)
    db.expire_all()
    dup_cred = db.query(models.UserCredits).filter(models.UserCredits.user_id == test_user.id).first()
    check("Idempotency: No Double Crediting on Duplicate Callback", abs(float(dup_cred.wallet_balance) - expected_balance) < 0.01)

    # Test 8: Failure Callback Flow
    fail_txnid = f"pvc_fail_{uuid.uuid4().hex[:10]}"
    fail_order = models.Order(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        provider_order_id=fail_txnid,
        plan_id=1,
        amount=20.0,
        currency="INR",
        status="pending"
    )
    db.add(fail_order)
    db.commit()

    res_fail = client.post("/api/payment/payu/failure", data={"txnid": fail_txnid, "error_Message": "User cancelled"}, follow_redirects=False)
    check("Failure Callback HTTP 303 Redirect", res_fail.status_code == 303)
    check("Redirect to /subscription?payment=failed", "payment=failed" in res_fail.headers.get("location", ""))

    db.expire_all()
    marked_failed_order = db.query(models.Order).filter(models.Order.provider_order_id == fail_txnid).first()
    check("Failed Order Status Updated to 'failed'", marked_failed_order is not None and marked_failed_order.status == "failed")

    print("="*70)
    print(f" TOTAL CHECKS: {total_checks} | PASSED: {passed_checks} | FAILED: {total_checks - passed_checks}")
    print("="*70)

    if passed_checks == total_checks:
        print(" 🎉 ALL PAYU INTEGRATION CHECKS PASSED PERFECTLY!\n")
        return 0
    else:
        print(" ❌ SOME CHECKS FAILED!\n")
        return 1

if __name__ == "__main__":
    sys.exit(run_payu_audit())
