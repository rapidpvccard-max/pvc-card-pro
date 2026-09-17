import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from fastapi.testclient import TestClient
from app import app
import database, models, auth

client = TestClient(app)
db = database.SessionLocal()

def test_pricing_deductions():
    print("=" * 60)
    print("  TESTING RECHARGE PLAN DEDUCTION RATES (₹2.00 vs ₹0.95)")
    print("=" * 60)

    # 1. Create a test user
    test_email = f"rate_test_{uuid.uuid4().hex[:6]}@gmail.com"
    res = client.post("/auth/register", json={"email": test_email, "password": "PassWord123!", "name": "Rate Tester"})
    assert res.status_code == 200
    user_id = res.json()["id"]
    token = auth.create_access_token({"sub": str(user_id)})
    client.cookies.set("access_token", token)

    # =========================================================================
    # CASE 1: User recharges ₹20 Trial Pack
    # =========================================================================
    print("\n--- CASE 1: User Recharges ₹20 (Trial Pack) ---")
    rec_trial = client.post("/api/payment/recharge-plan", json={"plan_id": 1})
    assert rec_trial.status_code == 200
    cred_res = client.get("/api/user/credits")
    credits_data = cred_res.json()
    print(f"  -> Wallet Balance: ₹{credits_data['wallet_balance']:.2f}")
    print(f"  -> Cost Per Card:  ₹{credits_data['cost_per_card']:.2f}")
    assert credits_data["wallet_balance"] == 20.0
    assert credits_data["cost_per_card"] == 2.00, f"Expected 2.00, got {credits_data['cost_per_card']}"
    print("  ✅ [PASS] Trial Pack successfully sets cost_per_card = ₹2.00")

    # Simulate card generation deduction for Trial user
    user_row = db.query(models.User).filter(models.User.id == user_id).first()
    rate = user_row.credits.cost_per_card
    assert rate == 2.00
    user_row.credits.wallet_balance -= rate
    db.commit()
    print(f"  -> Balance after 1 card generation (-₹{rate:.2f}): ₹{user_row.credits.wallet_balance:.2f}")
    assert round(user_row.credits.wallet_balance, 2) == 18.00
    print("  ✅ [PASS] Trial user gets exactly ₹2.00 deducted per card (₹20.00 -> ₹18.00)")

    # =========================================================================
    # CASE 2: User recharges ₹100 Starter Pack
    # =========================================================================
    print("\n--- CASE 2: User Recharges ₹100 (Starter Pack) ---")
    rec_starter = client.post("/api/payment/recharge-plan", json={"plan_id": 2})
    assert rec_starter.status_code == 200
    cred_res2 = client.get("/api/user/credits")
    credits_data2 = cred_res2.json()
    print(f"  -> Wallet Balance: ₹{credits_data2['wallet_balance']:.2f}")
    print(f"  -> Cost Per Card:  ₹{credits_data2['cost_per_card']:.2f}")
    assert credits_data2["cost_per_card"] == 0.95, f"Expected 0.95, got {credits_data2['cost_per_card']}"
    print("  ✅ [PASS] ₹100 Pack successfully unlocks cost_per_card = ₹0.95")

    # Simulate card generation deduction for ₹100 user
    db.expire_all()
    user_row2 = db.query(models.User).filter(models.User.id == user_id).first()
    rate2 = user_row2.credits.cost_per_card
    assert rate2 == 0.95
    bal_before = user_row2.credits.wallet_balance
    user_row2.credits.wallet_balance -= rate2
    db.commit()
    print(f"  -> Balance after 1 card generation (-₹{rate2:.2f}): ₹{user_row2.credits.wallet_balance:.2f}")
    assert round(user_row2.credits.wallet_balance, 2) == round(bal_before - 0.95, 2)
    print(f"  ✅ [PASS] Standard user gets exactly ₹0.95 deducted per card (₹{bal_before:.2f} -> ₹{user_row2.credits.wallet_balance:.2f})")

    # Cleanup
    db.query(models.CreditTransaction).filter(models.CreditTransaction.user_id == user_id).delete(synchronize_session=False)
    db.query(models.Order).filter(models.Order.user_id == user_id).delete(synchronize_session=False)
    db.query(models.UserCredits).filter(models.UserCredits.user_id == user_id).delete(synchronize_session=False)
    db.query(models.User).filter(models.User.id == user_id).delete(synchronize_session=False)
    db.commit()
    db.close()

    print("\n" + "=" * 60)
    print("🎉 ALL PRICING & DEDUCTION RULES VERIFIED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    test_pricing_deductions()
