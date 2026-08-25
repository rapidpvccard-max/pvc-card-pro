import os
import uuid
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Form
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
    plan = db.query(models.Plan).filter(models.Plan.id == order_data.plan_id).first()
    if not plan:
        # Fallback plan lookup by ID
        default_plans = {
            1: {"name": "Trial Pack", "price": 20.0, "credits": 20.0, "cost_per_card": 2.00},
            2: {"name": "Starter Pack", "price": 100.0, "credits": 100.0, "cost_per_card": 0.95},
            3: {"name": "Pro Pack", "price": 200.0, "credits": 200.0, "cost_per_card": 0.95},
            4: {"name": "Business Pack", "price": 300.0, "credits": 300.0, "cost_per_card": 0.95}
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

    user_credits = db.query(models.UserCredits).filter(models.UserCredits.user_id == current_user.id).first()
    if not user_credits:
        user_credits = models.UserCredits(user_id=current_user.id, wallet_balance=0.0, total_generated=0, cost_per_card=0.95)
        db.add(user_credits)
        
    # Top up wallet with exact recharge amount
    recharge_amount = float(plan.price)
    user_credits.wallet_balance = float(user_credits.wallet_balance or 0.0) + recharge_amount
    
    # Set per-card rate: ₹2.00 for Trial Pack, ₹0.95 for all standard packs
    if plan.id == 1 or "trial" in plan.name.lower():
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
        session = stripe.checkout.Session.create(
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
