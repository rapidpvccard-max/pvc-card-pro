import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import database
import models
import schemas
import auth

router = APIRouter(prefix="/api/admin", tags=["admin"])

def log_admin_action(db: Session, admin_id: int, action: str, target_user_id: int = None, details: str = None):
    log = models.AdminAuditLog(
        admin_id=admin_id,
        action=action,
        target_user_id=target_user_id,
        details=details
    )
    db.add(log)

@router.get("/dashboard", response_model=schemas.AdminDashboardResponse)
def get_admin_dashboard(
    current_admin: models.User = Depends(auth.get_current_admin), 
    db: Session = Depends(database.get_db)
):
    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(models.User.status == "active").count()
    total_cards = db.query(func.sum(models.GenerationHistory.card_count)).filter(models.GenerationHistory.status == "success").scalar() or 0
    
    total_revenue = db.query(func.sum(models.Order.amount)).filter(models.Order.status == "paid").scalar() or 0.0
    
    successful_payments = db.query(models.Order).filter(models.Order.status == "paid").count()
    pending_payments = db.query(models.Order).filter(models.Order.status == "pending").count()
    failed_payments = db.query(models.Order).filter(models.Order.status.in_(["failed", "cancelled"])).count()
    
    outstanding_credits = db.query(func.sum(models.UserCredits.wallet_balance)).scalar() or 0
    
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
    wallet_bal = float(user.credits.wallet_balance) if user.credits else 0.0
    
    # 1. Total Cards Generated
    total_cards = db.query(func.sum(models.GenerationHistory.card_count))\
        .filter(models.GenerationHistory.user_id == user.id, models.GenerationHistory.status == "success")\
        .scalar()
    if total_cards is None:
        total_cards = user.credits.total_generated if user.credits else 0
        
    # 2. Total Spent & Paid Orders
    total_spent = db.query(func.sum(models.Order.amount))\
        .filter(models.Order.user_id == user.id, models.Order.status == "paid")\
        .scalar() or 0.0
        
    paid_orders_count = db.query(models.Order)\
        .filter(models.Order.user_id == user.id, models.Order.status == "paid")\
        .count()
        
    # 3. Auth provider
    auth_provider = "google" if user.google_id else "email"
    
    # 4. Last Active
    last_gen = db.query(func.max(models.GenerationHistory.created_at))\
        .filter(models.GenerationHistory.user_id == user.id)\
        .scalar()
    last_tx = db.query(func.max(models.CreditTransaction.created_at))\
        .filter(models.CreditTransaction.user_id == user.id)\
        .scalar()
    candidates = [user.updated_at, user.created_at, last_gen, last_tx]
    valid_candidates = [c for c in candidates if c is not None]
    last_active = max(valid_candidates) if valid_candidates else user.created_at

    return {
        "id": user.id,
        "name": user.name or "Anonymous Operator",
        "email": user.email,
        "status": user.status,
        "is_admin": user.is_admin,
        "created_at": user.created_at,
        "auth_provider": auth_provider,
        "avatar_url": user.avatar_url,
        "wallet_balance": wallet_bal,
        "total_cards_generated": int(total_cards),
        "total_spent": float(total_spent),
        "paid_orders_count": paid_orders_count,
        "last_active": last_active,
        "credits": user.credits
    }

@router.get("/users", response_model=list[schemas.AdminUserResponse])
def list_users(
    current_admin: models.User = Depends(auth.get_current_admin), 
    db: Session = Depends(database.get_db)
):
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return [build_admin_user_dict(u, db) for u in users]

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
    
    recent_gens = db.query(models.GenerationHistory)\
        .filter(models.GenerationHistory.user_id == user_id)\
        .order_by(models.GenerationHistory.created_at.desc())\
        .limit(10).all()
        
    recent_orders = db.query(models.Order)\
        .filter(models.Order.user_id == user_id)\
        .order_by(models.Order.created_at.desc())\
        .limit(10).all()
        
    recent_txs = db.query(models.CreditTransaction)\
        .filter(models.CreditTransaction.user_id == user_id)\
        .order_by(models.CreditTransaction.created_at.desc())\
        .limit(10).all()
        
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
        
    old_status = user.status
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
        
    user_credits.wallet_balance += request.amount
    
    tx = models.CreditTransaction(
        user_id=user_id,
        amount=request.amount,
        transaction_type="admin_adjustment",
        reference_id=f"admin_{current_admin.id}",
        balance_after=user_credits.wallet_balance
    )
    db.add(tx)
    
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
    logs = db.query(models.AdminAuditLog).order_by(models.AdminAuditLog.created_at.desc()).limit(100).all()
    return logs

@router.get("/activity", response_model=list[schemas.SystemActivityItem])
def get_system_activity(
    limit: int = 50,
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(database.get_db)
):
    activities = []
    user_cache = {u.id: u for u in db.query(models.User).all()}

    # 1. Card Generations
    generations = db.query(models.GenerationHistory).order_by(models.GenerationHistory.created_at.desc()).limit(limit).all()
    for g in generations:
        u = user_cache.get(g.user_id)
        u_name = u.name if u else "Operator"
        u_email = u.email if u else "N/A"
        doc = (g.document_type or "Aadhaar").upper()
        is_success = g.status == "success"
        
        activities.append({
            "id": f"gen_{g.id}",
            "activity_type": "generation",
            "title": f"{doc} PVC Card Generated",
            "description": f"{u_name} generated {g.card_count or 1} card ({g.status})",
            "user_id": g.user_id,
            "user_name": u_name,
            "user_email": u_email,
            "status": g.status,
            "badge_label": f"🖨️ {doc}",
            "badge_type": "info" if is_success else "danger",
            "created_at": g.created_at
        })

    # 2. User Registrations
    users = db.query(models.User).order_by(models.User.created_at.desc()).limit(limit).all()
    for u in users:
        auth_type = "Google 1-Click" if u.google_id else "Email Signup"
        activities.append({
            "id": f"reg_{u.id}",
            "activity_type": "registration",
            "title": "New User Registered",
            "description": f"{u.name or 'Operator'} joined the platform via {auth_type}",
            "user_id": u.id,
            "user_name": u.name or "Operator",
            "user_email": u.email,
            "status": "success",
            "badge_label": "👤 USER",
            "badge_type": "cyan" if u.google_id else "success",
            "created_at": u.created_at
        })

    # 3. Credit Transactions / Wallet Deductions / Topups
    txs = db.query(models.CreditTransaction).order_by(models.CreditTransaction.created_at.desc()).limit(limit).all()
    for t in txs:
        u = user_cache.get(t.user_id)
        u_name = u.name if u else "Operator"
        u_email = u.email if u else "N/A"
        is_pos = t.amount > 0
        sign = f"+₹{t.amount:.2f}" if is_pos else f"-₹{abs(t.amount):.2f}"
        
        activities.append({
            "id": f"tx_{t.id}",
            "activity_type": "credit_tx",
            "title": f"Wallet: {t.transaction_type.replace('_', ' ').title()}",
            "description": f"{u_name} balance updated by {sign} (New: ₹{t.balance_after:.2f})",
            "user_id": t.user_id,
            "user_name": u_name,
            "user_email": u_email,
            "status": "success",
            "badge_label": f"💳 {sign}",
            "badge_type": "success" if is_pos else "purple",
            "created_at": t.created_at
        })

    # 4. Admin Audit Logs
    audit_logs = db.query(models.AdminAuditLog).order_by(models.AdminAuditLog.created_at.desc()).limit(limit).all()
    for a in audit_logs:
        admin_u = user_cache.get(a.admin_id)
        admin_name = admin_u.name if admin_u else f"Admin #{a.admin_id}"
        activities.append({
            "id": f"audit_{a.id}",
            "activity_type": "admin_audit",
            "title": f"Admin Action: {a.action.replace('_', ' ').title()}",
            "description": f"{admin_name} modified User #{a.target_user_id or 'N/A'}",
            "user_id": a.target_user_id,
            "user_name": admin_name,
            "user_email": admin_u.email if admin_u else "admin@rapidpvc.com",
            "status": "success",
            "badge_label": "⚡ ADMIN",
            "badge_type": "purple",
            "created_at": a.created_at
        })

    # Sort all events chronologically descending
    activities.sort(key=lambda x: x["created_at"], reverse=True)
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

