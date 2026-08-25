import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import database
import models

# Security Configuration
# In production, securely load these from environment variables
SECRET_KEY = os.environ.get("SECRET_KEY", "pvc-card-pro-super-secret-development-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30 # 30 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(request: Request, db: Session = Depends(database.get_db)):
    token = request.cookies.get("access_token")
    if not token:
        # Check Authorization header as fallback for API usage
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
        
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
        
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
        
    return user

DEFAULT_ADMIN_EMAILS = "rapidpvccard@gmail.com"

def get_admin_emails() -> list:
    raw = os.environ.get("ADMIN_EMAILS", DEFAULT_ADMIN_EMAILS)
    return [e.strip().lower() for e in raw.split(",") if e.strip()]

def is_admin_email(email: Optional[str]) -> bool:
    if not email:
        return False
    return email.strip().lower() in get_admin_emails()

def get_current_admin(current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    if is_admin_email(current_user.email) and not current_user.is_admin:
        current_user.is_admin = True
        try:
            db.commit()
        except Exception:
            db.rollback()
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 15

def create_password_reset_token(user: models.User) -> str:
    pwd_fingerprint = (user.hashed_password or "")[-10:]
    expire = datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": str(user.id),
        "email": user.email,
        "type": "pwd_reset",
        "fp": pwd_fingerprint,
        "exp": expire
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password_reset_token(token: str, db: Session) -> Optional[models.User]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "pwd_reset":
            return None
        user_id = payload.get("sub")
        fp = payload.get("fp")
        if not user_id or fp is None:
            return None
        user = db.query(models.User).filter(models.User.id == int(user_id)).first()
        if not user:
            return None
        current_fp = (user.hashed_password or "")[-10:]
        if current_fp != fp:
            return None
        return user
    except JWTError:
        return None

