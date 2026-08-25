import json
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import database
import models
import schemas
import auth

router = APIRouter(prefix="/api/admin", tags=["admin"])

def log_admin_action(db: Session, admin_id: int, action: str, target_user_id: int = None, details: str = None):
    try:
        log = models.AdminAuditLog(
            admin_id=admin_id,
            action=action,
            target_user_id=target_user_id,
            details=details
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"[Admin Audit Log Warning] {e}")
        try: db.rollback()
        except: pass

@router.get("/dashboard", response_model=schemas.AdminDashboardResponse)
def get_admin_dashboard(
    current_admin: models.User = Depends(auth.get_current_admin), 
    db: Session = Depends(database.get_db)
):
    try:
        total_users = db.query(models.User).count()
    except Exception:
        total_users = 0

    try:
        active_users = db.query(models.User).filter(models.User.status == "active").count()
    except Exception:
        active_users = total_users

    try:
        total_cards = int(db.query(func.sum(models.GenerationHistory.card_count)).filter(models.GenerationHistory.status == "success").scalar() or 0)
    except Exception:
        try:
            total_cards = db.query(models.GenerationHistory).filter(models.GenerationHistory.status == "success").count()
        except Exception:
            total_cards = 0
    
    try:
        total_revenue = round(float(db.query(func.sum(models.Order.amount)).filter(models.Order.status == "paid").scalar() or 0.0), 2)
    except Exception:
        total_revenue = 0.0
    
    try:
        successful_payments = db.query(models.Order).filter(models.Order.status == "paid").count()
        pending_payments = db.query(models.Order).filter(models.Order.status == "pending").count()
        failed_payments = db.query(models.Order).filter(models.Order.status.in_(["failed", "cancelled"])).count()
    except Exception:
        successful_payments, pending_payments, failed_payments = 0, 0, 0
    
    try:
        outstanding_credits = round(float(db.query(func.sum(models.UserCredits.wallet_balance)).scalar() or 0.0), 2)
    except Exception:
        outstanding_credits = 0.0
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_cards_generated": total_cards,
        "total_revenue": total_revenue,
        "successful_payments": successful_payments,
        "pending_payments": pending_payments,
        "failed_payments": failed_payments,
        "outstanding_credits": outstanding_credits
    }

def build_admin_user_dict(user: models.User, db: Session) -> dict:
    wallet_bal = 0.0
    if user.credits and user.credits.wallet_balance is not None:
        try:
            wallet_bal = float(user.credits.wallet_balance)
        except Exception:
            wallet_bal = 0.0
    
    # 1. Total Cards Generated
    try:
        total_cards = db.query(func.sum(models.GenerationHistory.card_count))\
            .filter(models.GenerationHistory.user_id == user.id, models.GenerationHistory.status == "success")\
            .scalar()
        if total_cards is None:
            total_cards = user.credits.total_generated if user.credits and user.credits.total_generated else 0
    except Exception:
        total_cards = 0
        
    # 2. Total Spent & Paid Orders
    try:
        total_spent = db.query(func.sum(models.Order.amount))\
            .filter(models.Order.user_id == user.id, models.Order.status == "paid")\
            .scalar() or 0.0
        paid_orders_count = db.query(models.Order)\
            .filter(models.Order.user_id == user.id, models.Order.status == "paid")\
            .count()
    except Exception:
        total_spent = 0.0
        paid_orders_count = 0
        
    # 3. Auth provider
    auth_provider = "google" if getattr(user, 'google_id', None) else "email"
    
    # 4. Last Active
    try:
        last_gen = db.query(func.max(models.GenerationHistory.created_at))\
            .filter(models.GenerationHistory.user_id == user.id)\
            .scalar()
    except Exception:
        last_gen = None

    try:
        last_tx = db.query(func.max(models.CreditTransaction.created_at))\
            .filter(models.CreditTransaction.user_id == user.id)\
            .scalar()
    except Exception:
        last_tx = None

    candidates = [getattr(user, 'updated_at', None), getattr(user, 'created_at', None), last_gen, last_tx]
    valid_candidates = [c for c in candidates if c is not None]
    last_active = max(valid_candidates) if valid_candidates else (getattr(user, 'created_at', None) or datetime.datetime.utcnow())

    return {
        "id": user.id,
        "name": user.name or "Anonymous Operator",
        "email": user.email,
        "status": user.status or "active",
        "is_admin": bool(user.is_admin),
        "created_at": user.created_at or datetime.datetime.utcnow(),
        "auth_provider": auth_provider,
        "avatar_url": user.avatar_url,
        "wallet_balance": float(wallet_bal),
        "total_cards_generated": int(total_cards or 0),
        "total_spent": float(total_spent or 0.0),
        "paid_orders_count": int(paid_orders_count or 0),
        "last_active": last_active,
        "credits": user.credits
    }

@router.get("/users", response_model=list[schemas.AdminUserResponse])
def list_users(
    current_admin: models.User = Depends(auth.get_current_admin), 
    db: Session = Depends(database.get_db)
):
    try:
        users = db.query(models.User).order_by(models.User.created_at.desc()).all()
        return [build_admin_user_dict(u, db) for u in users]
    except Exception as e:
        print(f"[Admin List Users Error] {e}")
        return []

@router.get("/users/{user_id}/details", response_model=schemas.AdminUserDetailResponse)
def get_user_details(
    user_id: int,
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_data = build_admin_user_dict(user, db)
    
    try:
        recent_gens = db.query(models.GenerationHistory)\
            .filter(models.GenerationHistory.user_id == user_id)\
            .order_by(models.GenerationHistory.created_at.desc())\
            .limit(10).all()
    except Exception:
        recent_gens = []
        
    try:
        recent_orders = db.query(models.Order)\
            .filter(models.Order.user_id == user_id)\
            .order_by(models.Order.created_at.desc())\
            .limit(10).all()
    except Exception:
        recent_orders = []
        
    try:
        recent_txs = db.query(models.CreditTransaction)\
            .filter(models.CreditTransaction.user_id == user_id)\
            .order_by(models.CreditTransaction.created_at.desc())\
            .limit(10).all()
    except Exception:
        recent_txs = []
        
    return {
        "user": user_data,
        "recent_generations": recent_gens,
        "recent_orders": recent_orders,
        "recent_transactions": recent_txs
    }

@router.post("/users/{user_id}/status")
def toggle_user_status(
    user_id: int,
    current_admin: models.User = Depends(auth.get_current_admin), 
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    old_status = user.status or "active"
    user.status = "inactive" if old_status == "active" else "active"
    
    log_admin_action(db, current_admin.id, "toggle_user_status", user.id, f"{old_status} -> {user.status}")
    db.commit()
    
    return {"status": "success", "new_status": user.status}

@router.post("/users/{user_id}/credits")
def adjust_credits(
    user_id: int,
    request: schemas.CreditAdjustmentRequest,
    current_admin: models.User = Depends(auth.get_current_admin), 
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_credits = db.query(models.UserCredits).filter(models.UserCredits.user_id == user_id).first()
    if not user_credits:
        user_credits = models.UserCredits(user_id=user_id, wallet_balance=0.0, total_generated=0)
        db.add(user_credits)
        
    user_credits.wallet_balance = float(user_credits.wallet_balance or 0.0) + float(request.amount)
    
    try:
        tx = models.CreditTransaction(
            user_id=user_id,
            amount=request.amount,
            transaction_type="admin_adjustment",
            reference_id=f"admin_{current_admin.id}",
            balance_after=user_credits.wallet_balance
        )
        db.add(tx)
    except Exception:
        pass
    
    log_admin_action(
        db, 
        current_admin.id, 
        "credit_adjustment", 
        user_id, 
        json.dumps({"amount": request.amount, "reason": request.reason, "balance_after": user_credits.wallet_balance})
    )
    db.commit()
    
    return {"status": "success", "balance_after": user_credits.wallet_balance}

@router.get("/audit", response_model=list[schemas.AdminAuditLogResponse])
def get_audit_logs(
    current_admin: models.User = Depends(auth.get_current_admin), 
    db: Session = Depends(database.get_db)
):
    try:
        logs = db.query(models.AdminAuditLog).order_by(models.AdminAuditLog.created_at.desc()).limit(100).all()
        return logs
    except Exception as e:
        print(f"[Admin Audit Error] {e}")
        return []

@router.get("/activity", response_model=list[schemas.SystemActivityItem])
def get_system_activity(
    limit: int = 50,
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(database.get_db)
):
    activities = []
    try:
        user_cache = {u.id: u for u in db.query(models.User).all()}
    except Exception:
        user_cache = {}

    # 1. Card Generations
    try:
        generations = db.query(models.GenerationHistory).order_by(models.GenerationHistory.created_at.desc()).limit(limit).all()
        for g in generations:
            u = user_cache.get(g.user_id)
            u_name = u.name if u and u.name else "Operator"
            u_email = u.email if u and u.email else "N/A"
            doc = (getattr(g, 'document_type', None) or "Aadhaar").upper()
            is_success = g.status == "success"
            
            activities.append({
                "id": f"gen_{g.id}",
                "activity_type": "generation",
                "title": f"{doc} PVC Card Generated",
                "description": f"{u_name} generated {getattr(g, 'card_count', 1) or 1} card ({g.status or 'completed'})",
                "user_id": g.user_id,
                "user_name": u_name,
                "user_email": u_email,
                "status": g.status or "success",
                "badge_label": f"🖨️ {doc}",
                "badge_type": "info" if is_success else "danger",
                "created_at": g.created_at or datetime.datetime.utcnow()
            })
    except Exception as e:
        print(f"[Activity Generations Error] {e}")

    # 2. User Registrations
    try:
        users = db.query(models.User).order_by(models.User.created_at.desc()).limit(limit).all()
        for u in users:
            auth_type = "Google 1-Click" if getattr(u, 'google_id', None) else "Email Signup"
            activities.append({
                "id": f"reg_{u.id}",
                "activity_type": "registration",
                "title": "New User Registered",
                "description": f"{u.name or 'Operator'} joined the platform via {auth_type}",
                "user_id": u.id,
                "user_name": u.name or "Operator",
                "user_email": u.email or "N/A",
                "status": "success",
                "badge_label": "👤 USER",
                "badge_type": "cyan" if getattr(u, 'google_id', None) else "success",
                "created_at": u.created_at or datetime.datetime.utcnow()
            })
    except Exception as e:
        print(f"[Activity Users Error] {e}")

    # 3. Credit Transactions / Wallet Deductions / Topups
    try:
        txs = db.query(models.CreditTransaction).order_by(models.CreditTransaction.created_at.desc()).limit(limit).all()
        for t in txs:
            u = user_cache.get(t.user_id)
            u_name = u.name if u and u.name else "Operator"
            u_email = u.email if u and u.email else "N/A"
            amt = float(t.amount or 0.0)
            is_pos = amt > 0
            sign = f"+₹{amt:.2f}" if is_pos else f"-₹{abs(amt):.2f}"
            bal_after = float(t.balance_after or 0.0)
            tx_type = (t.transaction_type or "transaction").replace('_', ' ').title()
            
            activities.append({
                "id": f"tx_{t.id}",
                "activity_type": "credit_tx",
                "title": f"Wallet: {tx_type}",
                "description": f"{u_name} balance updated by {sign} (New: ₹{bal_after:.2f})",
                "user_id": t.user_id,
                "user_name": u_name,
                "user_email": u_email,
                "status": "success",
                "badge_label": f"💳 {sign}",
                "badge_type": "success" if is_pos else "purple",
                "created_at": t.created_at or datetime.datetime.utcnow()
            })
    except Exception as e:
        print(f"[Activity Transactions Error] {e}")

    # 4. Admin Audit Logs
    try:
        audit_logs = db.query(models.AdminAuditLog).order_by(models.AdminAuditLog.created_at.desc()).limit(limit).all()
        for a in audit_logs:
            admin_u = user_cache.get(a.admin_id)
            admin_name = admin_u.name if admin_u and admin_u.name else f"Admin #{a.admin_id}"
            action_title = (a.action or "action").replace('_', ' ').title()
            activities.append({
                "id": f"audit_{a.id}",
                "activity_type": "admin_audit",
                "title": f"Admin Action: {action_title}",
                "description": f"{admin_name} modified User #{a.target_user_id or 'N/A'}",
                "user_id": a.target_user_id,
                "user_name": admin_name,
                "user_email": admin_u.email if admin_u and admin_u.email else "admin@rapidpvc.com",
                "status": "success",
                "badge_label": "⚡ ADMIN",
                "badge_type": "purple",
                "created_at": a.created_at or datetime.datetime.utcnow()
            })
    except Exception as e:
        print(f"[Activity Audit Error] {e}")

    # Sort all events chronologically descending safely
    def get_sort_key(item):
        val = item.get("created_at")
        if val is None:
            return datetime.datetime.min
        if isinstance(val, str):
            try:
                return datetime.datetime.fromisoformat(val)
            except Exception:
                return datetime.datetime.min
        return val

    activities.sort(key=get_sort_key, reverse=True)
    return activities[:limit]

from services.banner_service import get_banner_config, update_banner_config, save_banner_image
from fastapi import UploadFile, File

@router.get("/banner")
def admin_get_banner(current_admin: models.User = Depends(auth.get_current_admin)):
    return get_banner_config()

@router.post("/banner")
def admin_update_banner(
    payload: dict,
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(database.get_db)
):
    updated = update_banner_config(payload)
    log_admin_action(
        db,
        current_admin.id,
        "update_promo_banner",
        None,
        json.dumps({"type": updated.get("banner_type"), "enabled": updated.get("enabled")})
    )
    return {"status": "success", "config": updated}

@router.post("/banner/upload")
async def admin_upload_banner_image(
    file: UploadFile = File(...),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    
    image_url = await save_banner_image(file)
    update_banner_config({"image_url": image_url, "banner_type": "image"})
    return {"status": "success", "image_url": image_url}

