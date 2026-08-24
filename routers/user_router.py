from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
import database
import models
import schemas
import auth

router = APIRouter(prefix="/api/user", tags=["user"])

class UpdateProfileRequest(BaseModel):
    name: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.get("/me", response_model=schemas.UserResponse)
def get_user_profile(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@router.get("/dashboard", response_model=schemas.DashboardResponse)
def get_user_dashboard(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    credits = db.query(models.UserCredits).filter(models.UserCredits.user_id == current_user.id).first()
    
    # Get last 10 generations
    history = db.query(models.GenerationHistory)\
        .filter(models.GenerationHistory.user_id == current_user.id)\
        .order_by(models.GenerationHistory.created_at.desc())\
        .limit(10)\
        .all()
        
    transactions = db.query(models.CreditTransaction)\
        .filter(models.CreditTransaction.user_id == current_user.id)\
        .order_by(models.CreditTransaction.created_at.desc())\
        .limit(10)\
        .all()
        
    plans = db.query(models.Plan).filter(models.Plan.active == True).all()
        
    return {
        "user": current_user,
        "credits": credits,
        "history": history,
        "transactions": transactions,
        "plans": plans
    }

@router.get("/history")
def get_full_user_history(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    credits = db.query(models.UserCredits).filter(models.UserCredits.user_id == current_user.id).first()
    
    generations = db.query(models.GenerationHistory)\
        .filter(models.GenerationHistory.user_id == current_user.id)\
        .order_by(models.GenerationHistory.created_at.desc())\
        .all()
        
    transactions = db.query(models.CreditTransaction)\
        .filter(models.CreditTransaction.user_id == current_user.id)\
        .order_by(models.CreditTransaction.created_at.desc())\
        .all()
        
    return {
        "credits": {
            "wallet_balance": credits.wallet_balance if credits else 0.0,
            "total_generated": credits.total_generated if credits else 0
        },
        "generations": [
            {
                "id": g.id,
                "run_id": g.run_id,
                "document_type": g.document_type,
                "status": g.status,
                "created_at": g.created_at.isoformat() if g.created_at else None,
                "completed_at": g.completed_at.isoformat() if g.completed_at else None
            } for g in generations
        ],
        "transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "transaction_type": t.transaction_type,
                "reference_id": t.reference_id,
                "balance_after": t.balance_after,
                "created_at": t.created_at.isoformat() if t.created_at else None
            } for t in transactions
        ]
    }

@router.get("/credits")
def get_user_credits(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    credits = db.query(models.UserCredits).filter(models.UserCredits.user_id == current_user.id).first()
    if not credits:
        return {"wallet_balance": 0.0, "total_generated": 0}
    return {"wallet_balance": credits.wallet_balance, "total_generated": credits.total_generated}

@router.post("/update-profile")
def update_profile(req: UpdateProfileRequest, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    current_user.name = req.name.strip()
    db.commit()
    return {"success": True, "message": "Profile updated successfully", "name": current_user.name}

@router.post("/change-password")
def change_password(req: ChangePasswordRequest, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    if not auth.verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long")
    current_user.hashed_password = auth.get_password_hash(req.new_password)
    db.commit()
    return {"success": True, "message": "Password changed successfully"}
