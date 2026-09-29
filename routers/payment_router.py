# pyre-ignore-all-errors
# type: ignore
import os
import uuid
import hashlib
import hmac
import base64
from typing import Any, cast
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import database
import models
import schemas
import auth

# Set up Stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

router = APIRouter(prefix="/api/payment", tags=["payment"])

@router.get("/plans", response_model=list[schemas.PlanResponse])
def get_plans(db: Session = Depends(database.get_db)):
    plans = db.query(models.Plan).filter(models.Plan.active == True).all()
    return plans

@router.post("/recharge-plan")
def recharge_plan(
    order_data: schemas.OrderCreate, 
    current_user: models.User = Depends(auth.get_current_user), 
    db: Session = Depends(database.get_db)
):
    is_admin = getattr(current_user, "is_admin", False) or auth.is_admin_email(current_user.email)
    is_prod = os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
    if is_prod and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Direct plan recharge is restricted to administrators in production. Please use Cashfree or PayU checkout."
        )
    plan = db.query(models.Plan).filter(models.Plan.id == order_data.plan_id).first()
    if not plan:
        # Fallback plan lookup by ID
        default_plans = {
            1: {"name": "Trial Pack", "price": 20.0, "credits": 20.0, "cost_per_card": 2.00},
            2: {"name": "Starter Pack", "price": 100.0, "credits": 100.0, "cost_per_card": 0.95},
            3: {"name": "Pro Pack", "price": 200.0, "credits": 200.0, "cost_per_card": 0.95},
            4: {"name": "Business Pack", "price": 300.0, "credits": 300.0, "cost_per_card": 0.95},
            5: {"name": "Enterprise Pack", "price": 1000.0, "credits": 1000.0, "cost_per_card": 0.95}
        }
        if order_data.plan_id in default_plans:
            pinfo = default_plans[order_data.plan_id]
            plan = models.Plan(
                id=order_data.plan_id,
                name=pinfo["name"],
                price=pinfo["price"],
                credits=int(pinfo["credits"]),
                active=True
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
        else:
            raise HTTPException(status_code=404, detail="Plan not found")

    user_credits: Any = db.query(models.UserCredits).filter(models.UserCredits.user_id == current_user.id).first()
    if not user_credits:
        user_credits = models.UserCredits(user_id=current_user.id, wallet_balance=0.0, total_generated=0, cost_per_card=0.95)
        db.add(user_credits)
        
    # Top up wallet with exact recharge amount
    recharge_amount = float(cast(Any, plan).price)
    user_credits.wallet_balance = float(user_credits.wallet_balance or 0.0) + recharge_amount
    
    # Set per-card rate: ₹2.00 for Trial Pack, ₹0.95 for all standard packs
    if plan.id == 1 or "trial" in str(plan.name).lower():
        user_credits.cost_per_card = 2.00
    else:
        user_credits.cost_per_card = 0.95
    
    order_id = str(uuid.uuid4())
    order = models.Order(
        id=order_id,
        user_id=current_user.id,
        provider_order_id=f"rec_{uuid.uuid4().hex[:12]}",
        plan_id=plan.id,
        amount=recharge_amount,
        currency="INR",
        status="paid"
    )
    db.add(order)
    
    tx = models.CreditTransaction(
        user_id=current_user.id,
        amount=recharge_amount,
        transaction_type="purchase",
        reference_id=order_id,
        balance_after=user_credits.wallet_balance
    )
    db.add(tx)
    db.commit()
    
    return {
        "success": True,
        "message": f"Successfully recharged {plan.name} (₹{recharge_amount:.2f})!",
        "plan_name": plan.name,
        "amount_added": recharge_amount,
        "cost_per_card": user_credits.cost_per_card,
        "new_balance": user_credits.wallet_balance
    }

@router.post("/create-order")
def create_order(
    order_data: schemas.OrderCreate, 
    current_user: models.User = Depends(auth.get_current_user), 
    db: Session = Depends(database.get_db)
):
    plan = db.query(models.Plan).filter(models.Plan.id == order_data.plan_id, models.Plan.active == True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    try:
        base_url = os.environ.get("BASE_URL", "http://localhost:8000")
        session = cast(Any, stripe.checkout.Session).create(
            payment_method_types=['card'],
            line_items=[{
                'price': plan.stripe_price_id,
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{base_url}/dashboard?payment=success",
            cancel_url=f"{base_url}/dashboard?payment=cancelled",
            client_reference_id=str(current_user.id),
            metadata={
                "order_id": "" # Will be updated after DB insert
            }
        )
        provider_order_id = session.id
        checkout_url = session.url
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    new_order = models.Order(
        user_id=current_user.id,
        provider_order_id=provider_order_id,
        plan_id=plan.id,
        amount=plan.price,
        currency="USD",
        status="pending"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    # Update Stripe Session metadata with the internal order ID
    stripe.checkout.Session.modify(
        session.id,
        metadata={"order_id": new_order.id}
    )

    return {"checkout_url": checkout_url, "order_id": new_order.id}

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(database.get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"].to_dict()
        if session.get("payment_status") != "paid":
            return {"status": "ignored - not paid"}
            
        order_id = session.get("metadata", {}).get("order_id")
        if not order_id:
            return {"status": "ignored - no order_id"}

        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            return {"status": "ignored - order not found"}

        # Idempotency Check
        if order.status == "paid":
            return {"status": "success"}

        plan = db.query(models.Plan).filter(models.Plan.id == order.plan_id).first()
        
        # Atomically update DB
        order.status = "paid"
        order.provider_payment_id = session.get("payment_intent")
        
        user_credits = db.query(models.UserCredits).filter(models.UserCredits.user_id == order.user_id).first()
        if not user_credits:
            user_credits = models.UserCredits(user_id=order.user_id, wallet_balance=0.0, total_generated=0)
            db.add(user_credits)
            
        user_credits.wallet_balance += plan.credits
        
        tx = models.CreditTransaction(
            user_id=order.user_id,
            amount=plan.credits,
            transaction_type="purchase",
            reference_id=order.id,
            balance_after=user_credits.wallet_balance
        )
        db.add(tx)
        db.commit()
        
    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"].to_dict()
        payment_intent = charge.get("payment_intent")
        
        if not payment_intent:
            return {"status": "ignored - no payment_intent"}
            
        order = db.query(models.Order).filter(models.Order.provider_payment_id == payment_intent).first()
        if not order:
            return {"status": "ignored - order not found"}
            
        # Idempotency
        if order.status == "refunded":
            return {"status": "success"}
            
        plan = db.query(models.Plan).filter(models.Plan.id == order.plan_id).first()
        
        order.status = "refunded"
        
        user_credits = db.query(models.UserCredits).filter(models.UserCredits.user_id == order.user_id).first()
        user_credits.wallet_balance -= plan.credits
        
        tx = models.CreditTransaction(
            user_id=order.user_id,
            amount=-plan.credits,
            transaction_type="refund",
            reference_id=order.id,
            balance_after=user_credits.wallet_balance
        )
        db.add(tx)
        db.commit()

    return {"status": "success"}


# ==========================================
# PayU Hosted Checkout Integration (Live)
# ==========================================

PAYU_MERCHANT_KEY = os.environ.get("PAYU_MERCHANT_KEY", "HbMDKB")
PAYU_MERCHANT_SALT = os.environ.get("PAYU_MERCHANT_SALT", "5zmZRvGOsrXkLcajkaIRWzdDGfZ0WYEB")
PAYU_PAYMENT_URL = os.environ.get("PAYU_PAYMENT_URL", "https://secure.payu.in/_payment")

def generate_payu_hash(
    key: str,
    txnid: str,
    amount: str,
    productinfo: str,
    firstname: str,
    email: str,
    udf1: str = "",
    udf2: str = "",
    udf3: str = "",
    udf4: str = "",
    udf5: str = "",
    salt: str = ""
) -> str:
    """
    Generate SHA-512 request hash according to PayU formula:
    sha512(key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5||||||SALT)
    """
    hash_sequence = f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}|{udf2}|{udf3}|{udf4}|{udf5}||||||{salt}"
    return hashlib.sha512(hash_sequence.encode("utf-8")).hexdigest().lower()


def verify_payu_hash(data: dict, salt: str) -> bool:
    """
    Verify reverse hash returned by PayU upon payment completion.
    Formula with additionalCharges:
      sha512(additionalCharges|SALT|status||||||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key)
    Formula without additionalCharges:
      sha512(SALT|status||||||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key)
    """
    received_hash = str(data.get("hash", "")).strip().lower()
    if not received_hash:
        return False

    status = str(data.get("status", ""))
    txnid = str(data.get("txnid", ""))
    amount = str(data.get("amount", ""))
    productinfo = str(data.get("productinfo", ""))
    firstname = str(data.get("firstname", ""))
    email = str(data.get("email", ""))
    udf1 = str(data.get("udf1", "") or "")
    udf2 = str(data.get("udf2", "") or "")
    udf3 = str(data.get("udf3", "") or "")
    udf4 = str(data.get("udf4", "") or "")
    udf5 = str(data.get("udf5", "") or "")
    key = str(data.get("key", ""))
    additional_charges = data.get("additionalCharges")

    if additional_charges:
        hash_sequence = f"{additional_charges}|{salt}|{status}||||||{udf5}|{udf4}|{udf3}|{udf2}|{udf1}|{email}|{firstname}|{productinfo}|{amount}|{txnid}|{key}"
    else:
        hash_sequence = f"{salt}|{status}||||||{udf5}|{udf4}|{udf3}|{udf2}|{udf1}|{email}|{firstname}|{productinfo}|{amount}|{txnid}|{key}"

    calculated_hash = hashlib.sha512(hash_sequence.encode("utf-8")).hexdigest().lower()
    return hmac.compare_digest(received_hash, calculated_hash)


@router.post("/payu/initiate")
def initiate_payu_payment(
    order_data: schemas.OrderCreate,
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    plan = db.query(models.Plan).filter(models.Plan.id == order_data.plan_id).first()
    if not plan:
        default_plans = {
            1: {"name": "Trial Pack", "price": 20.0, "credits": 20.0, "cost_per_card": 2.00},
            2: {"name": "Starter Pack", "price": 100.0, "credits": 100.0, "cost_per_card": 0.95},
            3: {"name": "Pro Pack", "price": 200.0, "credits": 200.0, "cost_per_card": 0.95},
            4: {"name": "Business Pack", "price": 300.0, "credits": 300.0, "cost_per_card": 0.95},
            5: {"name": "Enterprise Pack", "price": 1000.0, "credits": 1000.0, "cost_per_card": 0.95}
        }
        if order_data.plan_id in default_plans:
            pinfo = default_plans[order_data.plan_id]
            plan = models.Plan(
                id=order_data.plan_id,
                name=pinfo["name"],
                price=pinfo["price"],
                credits=int(pinfo["credits"]),
                active=True
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
        else:
            raise HTTPException(status_code=404, detail="Plan not found")

    key = os.environ.get("PAYU_MERCHANT_KEY", PAYU_MERCHANT_KEY)
    salt = os.environ.get("PAYU_MERCHANT_SALT", PAYU_MERCHANT_SALT)
    action_url = os.environ.get("PAYU_PAYMENT_URL", PAYU_PAYMENT_URL)

    env_base_url = os.environ.get("BASE_URL", "https://rapidpvc.online").rstrip("/")
    req_base_url = str(request.base_url).rstrip("/")
    if "localhost" in req_base_url or "127.0.0.1" in req_base_url:
        base_url = req_base_url
    elif env_base_url:
        base_url = env_base_url
    else:
        base_url = "https://rapidpvc.online"

    txnid = f"pvc_{uuid.uuid4().hex[:14]}"
    amount_str = f"{float(plan.price):.2f}"
    productinfo = f"Recharge {plan.name}".replace("-", " ")
    productinfo = "".join(c for c in productinfo if c.isalnum() or c.isspace())[:50]

    raw_name = current_user.name or "Customer"
    firstname = "".join(c for c in raw_name if c.isalnum() or c.isspace()).strip() or "Customer"
    email = current_user.email or "rapidpvccard@gmail.com"
    phone = "7698390510"

    udf1 = str(current_user.id)
    udf2 = str(plan.id)

    surl = f"{base_url}/api/payment/payu/success"
    furl = f"{base_url}/api/payment/payu/failure"

    hash_val = generate_payu_hash(
        key=key,
        txnid=txnid,
        amount=amount_str,
        productinfo=productinfo,
        firstname=firstname,
        email=email,
        udf1=udf1,
        udf2=udf2,
        salt=salt
    )

    # Record order in pending state
    order_id = str(uuid.uuid4())
    new_order = models.Order(
        id=order_id,
        user_id=current_user.id,
        provider_order_id=txnid,
        plan_id=plan.id,
        amount=float(plan.price),
        currency="INR",
        status="pending"
    )
    db.add(new_order)
    db.commit()

    return {
        "action": action_url,
        "params": {
            "key": key,
            "txnid": txnid,
            "amount": amount_str,
            "productinfo": productinfo,
            "firstname": firstname,
            "email": email,
            "phone": phone,
            "surl": surl,
            "furl": furl,
            "hash": hash_val,
            "udf1": udf1,
            "udf2": udf2
        }
    }


def _process_payu_payment_success(data: dict, db: Session) -> tuple[bool, str, float]:
    """
    Internal helper to atomically mark order as paid and credit user's wallet.
    Returns (success, txnid, recharge_amount).
    """
    txnid = data.get("txnid", "")
    status = data.get("status", "")
    mihpayid = data.get("mihpayid", "")
    amount = float(data.get("amount", 0.0) or 0.0)

    order = db.query(models.Order).filter(models.Order.provider_order_id == txnid).first()
    if not order:
        user_id = data.get("udf1")
        plan_id = data.get("udf2")
        if user_id and plan_id:
            order = models.Order(
                id=str(uuid.uuid4()),
                user_id=int(user_id),
                provider_order_id=txnid,
                plan_id=int(plan_id),
                amount=amount,
                currency="INR",
                status="pending"
            )
            db.add(order)
            db.commit()
            db.refresh(order)

    if not order:
        return False, txnid, 0.0

    # Idempotency check: Already credited
    if order.status == "paid":
        return True, txnid, float(order.amount)

    if str(status).lower() == "success":
        order.status = "paid"
        order.provider_payment_id = str(mihpayid)

        user_credits: Any = db.query(models.UserCredits).filter(models.UserCredits.user_id == order.user_id).first()
        if not user_credits:
            user_credits = models.UserCredits(user_id=order.user_id, wallet_balance=0.0, total_generated=0, cost_per_card=0.95)
            db.add(user_credits)

        recharge_amount = float(order.amount)
        user_credits.wallet_balance = float(user_credits.wallet_balance or 0.0) + recharge_amount

        # Update per-card rate
        plan: Any = db.query(models.Plan).filter(models.Plan.id == order.plan_id).first()
        if plan and (plan.id == 1 or "trial" in str(plan.name).lower()):
            user_credits.cost_per_card = 2.00
        else:
            user_credits.cost_per_card = 0.95

        tx = models.CreditTransaction(
            user_id=order.user_id,
            amount=recharge_amount,
            transaction_type="purchase",
            reference_id=txnid,
            balance_after=user_credits.wallet_balance
        )
        db.add(tx)
        db.commit()

        # Dispatch Payment Receipt & Tax Invoice Email
        try:
            from services.email_service import send_payment_invoice_email
            paid_user: Any = db.query(models.User).filter(models.User.id == order.user_id).first()
            if paid_user and paid_user.email:
                plan_name_val = plan.name if plan and getattr(plan, 'name', None) else f"Plan #{order.plan_id}"
                send_payment_invoice_email(
                    to_email=str(paid_user.email),
                    user_name=str(paid_user.name or "Operator"),
                    txnid=str(txnid),
                    amount=float(recharge_amount),
                    plan_name=str(plan_name_val),
                    new_wallet_balance=float(user_credits.wallet_balance or 0.0),
                    cost_per_card=float(user_credits.cost_per_card or 0.95),
                    mihpayid=str(mihpayid) if mihpayid else None
                )
        except Exception as email_err:
            print(f"[Payment Invoice Email Dispatch Error] {email_err}")

        return True, txnid, recharge_amount
    else:
        order.status = "failed"
        db.commit()
        return False, txnid, 0.0


@router.api_route("/payu/success", methods=["GET", "POST"])
async def payu_success(request: Request, db: Session = Depends(database.get_db)):
    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
    else:
        data = dict(request.query_params)

    salt = os.environ.get("PAYU_MERCHANT_SALT", PAYU_MERCHANT_SALT)
    
    # Verify hash integrity
    if not verify_payu_hash(data, salt):
        return RedirectResponse(
            url="/subscription?payment=error&message=Payment+signature+verification+failed",
            status_code=303
        )

    success, txnid, amount = _process_payu_payment_success(data, db)
    if success:
        return RedirectResponse(
            url=f"/subscription?payment=success&txnid={txnid}&amount={amount:.2f}",
            status_code=303
        )
    else:
        error_msg = data.get("error_Message") or data.get("unmappedstatus") or "Payment not successful"
        return RedirectResponse(
            url=f"/subscription?payment=failed&message={error_msg}",
            status_code=303
        )


@router.api_route("/payu/failure", methods=["GET", "POST"])
async def payu_failure(request: Request, db: Session = Depends(database.get_db)):
    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
    else:
        data = dict(request.query_params)

    txnid = data.get("txnid", "")
    error_msg = data.get("error_Message") or data.get("unmappedstatus") or "Payment cancelled or failed"

    if txnid:
        order = db.query(models.Order).filter(models.Order.provider_order_id == txnid).first()
        if order and order.status != "paid":
            order.status = "failed"
            db.commit()

    return RedirectResponse(
        url=f"/subscription?payment=failed&message={error_msg}",
        status_code=303
    )


@router.post("/payu/webhook")
async def payu_webhook(request: Request, db: Session = Depends(database.get_db)):
    form_data = await request.form()
    data = dict(form_data)
    salt = os.environ.get("PAYU_MERCHANT_SALT", PAYU_MERCHANT_SALT)

    if not verify_payu_hash(data, salt):
        raise HTTPException(status_code=400, detail="Invalid hash signature")

    success, txnid, amount = _process_payu_payment_success(data, db)
    return {"status": "success" if success else "failed", "txnid": txnid, "amount": amount}


# ==========================================
# Cashfree Payment Gateway Integration (PG)
# ==========================================

CASHFREE_APP_ID = os.environ.get("CASHFREE_APP_ID", "")
CASHFREE_SECRET_KEY = os.environ.get("CASHFREE_SECRET_KEY", "")
CASHFREE_ENV = os.environ.get("CASHFREE_ENV", "production").strip().lower()  # 'sandbox' or 'production'
CASHFREE_API_VERSION = os.environ.get("CASHFREE_API_VERSION", "2023-08-01").strip()
DEFAULT_PAYMENT_GATEWAY = os.environ.get("DEFAULT_PAYMENT_GATEWAY", "cashfree").strip().lower()


def get_cashfree_base_url() -> str:
    env = os.environ.get("CASHFREE_ENV", CASHFREE_ENV).strip().lower()
    if env == "sandbox":
        return "https://sandbox.cashfree.com/pg"
    return "https://api.cashfree.com/pg"


def get_cashfree_headers() -> dict:
    app_id = os.environ.get("CASHFREE_APP_ID", CASHFREE_APP_ID).strip()
    secret_key = os.environ.get("CASHFREE_SECRET_KEY", CASHFREE_SECRET_KEY).strip()
    api_version = os.environ.get("CASHFREE_API_VERSION", CASHFREE_API_VERSION).strip() or "2023-08-01"
    return {
        "x-client-id": app_id,
        "x-client-secret": secret_key,
        "x-api-version": api_version,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def verify_cashfree_signature(raw_body: str, timestamp: str, signature: str, secret_key: str = None) -> bool:
    """
    Verify cryptographic Cashfree Webhook HMAC-SHA256 signature according to Cashfree standard:
    base64(hmac_sha256(timestamp + raw_body, secret_key))
    """
    if not secret_key:
        secret_key = os.environ.get("CASHFREE_SECRET_KEY", CASHFREE_SECRET_KEY).strip()
    if not secret_key or not signature or not timestamp:
        return False
    try:
        message = str(timestamp) + str(raw_body)
        hash_object = hmac.new(
            secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        )
        expected_sig = base64.b64encode(hash_object.digest()).decode("utf-8")
        return hmac.compare_digest(expected_sig.strip(), signature.strip())
    except Exception as e:
        print(f"[Cashfree Signature Verify Error] {e}")
        return False


def _process_cashfree_payment_success(
    order: models.Order,
    cf_payment_id: str,
    payment_amount: float,
    db: Session
) -> tuple[bool, str, float]:
    """
    Atomically mark Cashfree order as paid and credit user's wallet.
    Guaranteed idempotent!
    """
    if order.status == "paid":
        return True, str(order.provider_order_id), float(order.amount)

    order.status = "paid"
    order.gateway = "cashfree"
    order.provider_payment_id = str(cf_payment_id) if cf_payment_id else f"cf_pay_{uuid.uuid4().hex[:12]}"

    user_credits: Any = db.query(models.UserCredits).filter(models.UserCredits.user_id == order.user_id).first()
    if not user_credits:
        user_credits = models.UserCredits(user_id=order.user_id, wallet_balance=0.0, total_generated=0, cost_per_card=0.95)
        db.add(user_credits)

    recharge_amount = float(order.amount)
    user_credits.wallet_balance = float(user_credits.wallet_balance or 0.0) + recharge_amount

    # Update per-card rate: ₹2.00 for Trial Pack, ₹0.95 for all standard packs
    plan: Any = db.query(models.Plan).filter(models.Plan.id == order.plan_id).first()
    if plan and (plan.id == 1 or "trial" in str(plan.name).lower()):
        user_credits.cost_per_card = 2.00
    else:
        user_credits.cost_per_card = 0.95

    tx = models.CreditTransaction(
        user_id=order.user_id,
        amount=recharge_amount,
        transaction_type="purchase",
        reference_id=str(order.provider_order_id),
        balance_after=user_credits.wallet_balance
    )
    db.add(tx)
    db.commit()

    # Dispatch Payment Receipt & Tax Invoice Email
    try:
        from services.email_service import send_payment_invoice_email
        paid_user: Any = db.query(models.User).filter(models.User.id == order.user_id).first()
        if paid_user and paid_user.email:
            plan_name_val = plan.name if plan and getattr(plan, 'name', None) else f"Plan #{order.plan_id}"
            send_payment_invoice_email(
                to_email=str(paid_user.email),
                user_name=str(paid_user.name or "Operator"),
                txnid=str(order.provider_order_id),
                amount=float(recharge_amount),
                plan_name=str(plan_name_val),
                new_wallet_balance=float(user_credits.wallet_balance or 0.0),
                cost_per_card=float(user_credits.cost_per_card or 0.95),
                gateway="Cashfree",
                gateway_ref=str(order.provider_payment_id)
            )
    except Exception as email_err:
        print(f"[Cashfree Invoice Email Dispatch Error] {email_err}")

    return True, str(order.provider_order_id), recharge_amount


@router.get("/gateways")
def get_payment_gateways():
    """
    Returns configured payment gateways and active default gateway.
    """
    cf_app_id = os.environ.get("CASHFREE_APP_ID", CASHFREE_APP_ID).strip()
    cf_secret = os.environ.get("CASHFREE_SECRET_KEY", CASHFREE_SECRET_KEY).strip()
    cf_configured = bool(cf_app_id and cf_secret and cf_app_id != "your_cashfree_app_id")

    payu_key = os.environ.get("PAYU_MERCHANT_KEY", PAYU_MERCHANT_KEY).strip()
    payu_salt = os.environ.get("PAYU_MERCHANT_SALT", PAYU_MERCHANT_SALT).strip()
    payu_configured = bool(payu_key and payu_salt)

    default_gw = os.environ.get("DEFAULT_PAYMENT_GATEWAY", DEFAULT_PAYMENT_GATEWAY).strip().lower()
    cf_env = os.environ.get("CASHFREE_ENV", CASHFREE_ENV).strip().lower()

    return {
        "default_gateway": default_gw if default_gw in ("cashfree", "payu") else "cashfree",
        "cashfree": {
            "enabled": True,
            "configured": cf_configured,
            "environment": cf_env if cf_env in ("sandbox", "production") else "production"
        },
        "payu": {
            "enabled": True,
            "configured": payu_configured
        }
    }


@router.post("/cashfree/initiate")
def initiate_cashfree_payment(
    order_data: schemas.OrderCreate,
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Creates an order on Cashfree and returns payment_session_id for Cashfree JS Checkout.
    """
    plan = db.query(models.Plan).filter(models.Plan.id == order_data.plan_id).first()
    if not plan:
        default_plans = {
            1: {"name": "Trial Pack", "price": 20.0, "credits": 20.0, "cost_per_card": 2.00},
            2: {"name": "Starter Pack", "price": 100.0, "credits": 100.0, "cost_per_card": 0.95},
            3: {"name": "Pro Pack", "price": 200.0, "credits": 200.0, "cost_per_card": 0.95},
            4: {"name": "Business Pack", "price": 300.0, "credits": 300.0, "cost_per_card": 0.95},
            5: {"name": "Enterprise Pack", "price": 1000.0, "credits": 1000.0, "cost_per_card": 0.95}
        }
        if order_data.plan_id in default_plans:
            pinfo = default_plans[order_data.plan_id]
            plan = models.Plan(
                id=order_data.plan_id,
                name=pinfo["name"],
                price=pinfo["price"],
                credits=int(pinfo["credits"]),
                active=True
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
        else:
            raise HTTPException(status_code=404, detail="Plan not found")

    app_id = os.environ.get("CASHFREE_APP_ID", CASHFREE_APP_ID).strip()
    secret_key = os.environ.get("CASHFREE_SECRET_KEY", CASHFREE_SECRET_KEY).strip()
    if not app_id or not secret_key or app_id == "your_cashfree_app_id":
        raise HTTPException(
            status_code=400,
            detail="Cashfree Payment Gateway is not configured. Please set CASHFREE_APP_ID and CASHFREE_SECRET_KEY in server environment."
        )

    # Determine Base URL
    env_base_url = os.environ.get("BASE_URL", "https://rapidpvc.online").rstrip("/")
    req_base_url = str(request.base_url).rstrip("/")
    if "localhost" in req_base_url or "127.0.0.1" in req_base_url:
        base_url = req_base_url
    elif env_base_url:
        base_url = env_base_url
    else:
        base_url = "https://rapidpvc.online"

    # Unique Cashfree Order ID (alphanumeric up to 45 chars)
    cf_order_id = f"cf_{uuid.uuid4().hex[:16]}"
    amount_val = round(float(plan.price), 2)

    raw_name = current_user.name or "Customer"
    customer_name = "".join(c for c in raw_name if c.isalnum() or c.isspace()).strip() or "Customer"
    customer_email = current_user.email or "rapidpvccard@gmail.com"
    customer_phone = "7698390510"

    cf_payload = {
        "order_id": cf_order_id,
        "order_amount": amount_val,
        "order_currency": "INR",
        "customer_details": {
            "customer_id": f"cust_{current_user.id}",
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": customer_phone
        },
        "order_meta": {
            "return_url": f"{base_url}/api/payment/cashfree/return?order_id={{order_id}}"
        },
        "order_note": f"Recharge {plan.name} - Rapid PVC"
    }

    base_cf_url = get_cashfree_base_url()
    headers = get_cashfree_headers()

    import requests
    try:
        resp = requests.post(f"{base_cf_url}/orders", json=cf_payload, headers=headers, timeout=12)
        resp_data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to communicate with Cashfree API: {str(e)}")

    if resp.status_code not in (200, 201):
        err_msg = resp_data.get("message") or resp_data.get("detail") or f"Cashfree HTTP {resp.status_code} Error"
        raise HTTPException(status_code=resp.status_code if resp.status_code < 500 else 502, detail=err_msg)

    payment_session_id = resp_data.get("payment_session_id")
    if not payment_session_id:
        raise HTTPException(status_code=502, detail="No payment_session_id returned by Cashfree")

    # Record internal order in pending state
    internal_order_id = str(uuid.uuid4())
    new_order = models.Order(
        id=internal_order_id,
        user_id=current_user.id,
        provider_order_id=cf_order_id,
        plan_id=plan.id,
        amount=amount_val,
        currency="INR",
        status="pending",
        gateway="cashfree"
    )
    db.add(new_order)
    db.commit()

    cf_env = os.environ.get("CASHFREE_ENV", CASHFREE_ENV).strip().lower()
    return {
        "success": True,
        "order_id": cf_order_id,
        "payment_session_id": payment_session_id,
        "cf_env": cf_env if cf_env in ("sandbox", "production") else "production"
    }


@router.get("/cashfree/return")
def cashfree_return(
    order_id: str = "",
    db: Session = Depends(database.get_db)
):
    """
    Return redirect URL configured in Cashfree Order Meta.
    Verifies order status with Cashfree PG and safely credits wallet upon success.
    """
    if not order_id:
        return RedirectResponse(
            url="/subscription?payment=failed&message=Missing+order_id",
            status_code=303
        )

    order = db.query(models.Order).filter(models.Order.provider_order_id == order_id).first()
    if not order:
        return RedirectResponse(
            url="/subscription?payment=failed&message=Order+not+found",
            status_code=303
        )

    # Idempotency: Already marked as paid via webhook
    if order.status == "paid":
        return RedirectResponse(
            url=f"/subscription?payment=success&txnid={order.provider_order_id}&amount={order.amount:.2f}",
            status_code=303
        )

    # Query Cashfree PG API directly for ground truth status
    base_cf_url = get_cashfree_base_url()
    headers = get_cashfree_headers()
    import requests
    try:
        resp = requests.get(f"{base_cf_url}/orders/{order_id}", headers=headers, timeout=12)
        cf_data = resp.json() if resp.status_code == 200 else {}
    except Exception as e:
        print(f"[Cashfree Status Check Exception] {e}")
        cf_data = {}

    order_status = str(cf_data.get("order_status", "")).upper()

    if order_status == "PAID":
        # Extract specific payment ID if present
        cf_payment_id = None
        try:
            pay_resp = requests.get(f"{base_cf_url}/orders/{order_id}/payments", headers=headers, timeout=10)
            if pay_resp.status_code == 200:
                p_list = pay_resp.json()
                if isinstance(p_list, list) and len(p_list) > 0:
                    cf_payment_id = str(p_list[0].get("cf_payment_id") or "")
        except Exception:
            pass

        success, txnid, amount = _process_cashfree_payment_success(order, cf_payment_id, float(order.amount), db)
        return RedirectResponse(
            url=f"/subscription?payment=success&txnid={txnid}&amount={amount:.2f}",
            status_code=303
        )
    elif order_status == "ACTIVE":
        return RedirectResponse(
            url=f"/subscription?payment=pending&txnid={order_id}&message=Payment+in+progress.+Wallet+will+update+upon+confirmation.",
            status_code=303
        )
    else:
        order.status = "failed"
        db.commit()
        err_msg = cf_data.get("order_status") or "Payment cancelled or incomplete"
        return RedirectResponse(
            url=f"/subscription?payment=failed&message={err_msg}",
            status_code=303
        )


@router.api_route("/cashfree/webhook", methods=["GET", "POST"])
async def cashfree_webhook(
    request: Request,
    db: Session = Depends(database.get_db)
):
    """
    Cashfree server-to-server webhook endpoint with HMAC-SHA256 signature verification.
    Supports GET ping / dashboard test verification.
    """
    if request.method == "GET":
        return {"status": "OK", "endpoint": "Cashfree Webhook Endpoint Active", "version": "2023-08-01"}

    raw_body_bytes = await request.body()
    raw_body_str = raw_body_bytes.decode("utf-8") if raw_body_bytes else ""

    signature = request.headers.get("x-webhook-signature") or request.headers.get("X-Webhook-Signature") or ""
    timestamp = request.headers.get("x-webhook-timestamp") or request.headers.get("X-Webhook-Timestamp") or ""

    # Handle Cashfree Dashboard 'Test' Ping (which may not send a valid HMAC signature)
    if not signature and (not raw_body_str or "test" in raw_body_str.lower() or "ping" in raw_body_str.lower()):
        return {"status": "OK", "message": "Cashfree test webhook received successfully"}

    secret_key = os.environ.get("CASHFREE_SECRET_KEY", CASHFREE_SECRET_KEY).strip()

    if not verify_cashfree_signature(raw_body_str, timestamp, signature, secret_key):
        raise HTTPException(status_code=400, detail="Invalid Cashfree webhook signature")

    import json
    try:
        event_data = json.loads(raw_body_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    data = event_data.get("data", {})
    order_obj = data.get("order", {})
    payment_obj = data.get("payment", {})

    order_id = order_obj.get("order_id") or event_data.get("order_id")
    event_type = str(event_data.get("type", "")).upper()
    payment_status = str(payment_obj.get("payment_status", "")).upper()

    if not order_id:
        return {"status": "ignored - no order_id"}

    order = db.query(models.Order).filter(models.Order.provider_order_id == order_id).first()
    if not order:
        return {"status": "ignored - order not found"}

    if event_type == "PAYMENT_SUCCESS_WEBHOOK" or payment_status == "SUCCESS":
        cf_payment_id = payment_obj.get("cf_payment_id")
        amount = float(payment_obj.get("payment_amount") or order.amount)
        _process_cashfree_payment_success(order, str(cf_payment_id) if cf_payment_id else None, amount, db)
        return {"status": "OK", "order_id": order_id}
    elif payment_status == "FAILED" or event_type == "PAYMENT_FAILED_WEBHOOK":
        if order.status != "paid":
            order.status = "failed"
            db.commit()
        return {"status": "OK", "order_id": order_id}

    return {"status": "ignored", "event_type": event_type}

