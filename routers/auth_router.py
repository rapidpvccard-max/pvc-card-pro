import os
import secrets
import urllib.parse
import requests
from datetime import timedelta
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import database
import models
import schemas
import auth

router = APIRouter(prefix="/auth", tags=["auth"])

def get_google_config() -> tuple[str, str, str]:
    # Reload .env in real time so changes are picked up immediately
    try:
        load_dotenv(override=True)
    except Exception:
        pass
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
    return client_id, client_secret, redirect_uri

def get_google_redirect_uri(request: Request) -> str:
    # Dynamically match the exact host the user is browsing on (e.g. 127.0.0.1:8000 or localhost:8000)
    base = str(request.base_url).rstrip("/")
    env_uri = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
    # If production custom domain is explicitly configured, use it
    if env_uri and "127.0.0.1" not in env_uri and "localhost" not in env_uri:
        return env_uri
    return f"{base}/auth/google/callback"

@router.get("/google/login")
def google_login(request: Request):
    client_id, _, _ = get_google_config()
    if not client_id:
        return RedirectResponse(
            url="/login?error=Google+Sign-In+is+not+configured+yet.+Please+add+GOOGLE_CLIENT_ID+and+GOOGLE_CLIENT_SECRET+in+.env"
        )
    
    redirect_uri = get_google_redirect_uri(request)
    state = secrets.token_urlsafe(16)
    
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": state
    }
    
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    response = RedirectResponse(url=google_auth_url)
    response.set_cookie(key="oauth_state", value=state, httponly=True, max_age=600, samesite="lax")
    return response

@router.get("/google/callback")
def google_callback(
    request: Request,
    response: Response,
    code: str = None,
    error: str = None,
    state: str = None,
    db: Session = Depends(database.get_db)
):
    if error:
        return RedirectResponse(url=f"/login?error=Google+login+cancelled:+{urllib.parse.quote(error)}")
        
    if not code:
        return RedirectResponse(url="/login?error=Invalid+Google+authorization+response")
        
    client_id, client_secret, _ = get_google_config()
    redirect_uri = get_google_redirect_uri(request)
    
    if not client_id or not client_secret:
        return RedirectResponse(url="/login?error=Google+OAuth+credentials+missing+on+server")
        
    # 1. Exchange code for token
    token_url = "https://oauth2.googleapis.com/token"
    token_payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    
    try:
        token_resp = requests.post(token_url, data=token_payload, timeout=10)
        token_data = token_resp.json()
    except Exception as e:
        return RedirectResponse(url=f"/login?error=Failed+to+connect+to+Google:+{urllib.parse.quote(str(e))}")
        
    if "error" in token_data:
        err_desc = token_data.get("error_description", token_data.get("error"))
        return RedirectResponse(url=f"/login?error=Google+authentication+failed:+{urllib.parse.quote(str(err_desc))}")
        
    google_access_token = token_data.get("access_token")
    if not google_access_token:
        return RedirectResponse(url="/login?error=No+access+token+received+from+Google")
        
    # 2. Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    try:
        userinfo_resp = requests.get(userinfo_url, headers={"Authorization": f"Bearer {google_access_token}"}, timeout=10)
        userinfo = userinfo_resp.json()
    except Exception as e:
        return RedirectResponse(url=f"/login?error=Failed+to+fetch+user+profile+from+Google:+{urllib.parse.quote(str(e))}")
        
    email = userinfo.get("email")
    if not email:
        return RedirectResponse(url="/login?error=No+email+associated+with+Google+account")
        
    name = userinfo.get("name") or email.split("@")[0]
    google_id = userinfo.get("id")
    picture = userinfo.get("picture")
    
    # 3. Find or Create User in DB
    admin_emails = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "rapidpvccard@gmail.com").split(",") if e.strip()]
    is_admin_user = email.lower() in admin_emails

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        dummy_pwd = auth.get_password_hash(secrets.token_urlsafe(32))
        user = models.User(
            name=name,
            email=email,
            hashed_password=dummy_pwd,
            google_id=google_id,
            avatar_url=picture,
            status="active",
            is_admin=is_admin_user
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Give starting credits (1000 for admin, 5 for normal user)
        start_bal = 1000.0 if is_admin_user else 5.0
        new_credits = models.UserCredits(user_id=user.id, wallet_balance=start_bal, total_generated=0)
        db.add(new_credits)
        db.commit()
    else:
        if not user.google_id and google_id:
            user.google_id = google_id
        if not user.avatar_url and picture:
            user.avatar_url = picture
        user.is_admin = is_admin_user
        if user.status != "active":
            return RedirectResponse(url="/login?error=Account+is+inactive.+Please+contact+support.")
        db.commit()
        
    # 4. Generate App JWT Token & set Cookie
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    use_secure = is_secure_request(request)
    redirect_target = "/admin" if is_admin_user else "/dashboard"
    redirect_res = RedirectResponse(url=redirect_target, status_code=status.HTTP_303_SEE_OTHER)
    redirect_res.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=use_secure,
        max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    return redirect_res

@router.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email.strip().lower()).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    admin_emails = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "rapidpvccard@gmail.com").split(",") if e.strip()]
    is_admin = user.email.strip().lower() in admin_emails

    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(
        name=user.name, 
        email=user.email.strip().lower(), 
        hashed_password=hashed_password,
        is_admin=is_admin
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Initialize default credits for new user
    start_bal = 1000.0 if is_admin else 5.0
    new_credits = models.UserCredits(user_id=new_user.id, wallet_balance=start_bal, total_generated=0)
    db.add(new_credits)
    db.commit()
    
    return new_user

def is_secure_request(request: Request) -> bool:
    if not request:
        return False
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme).lower()
    return scheme == "https"

@router.post("/login")
def login(request: Request, response: Response, user_data: schemas.UserLogin, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == user_data.email.strip().lower()).first()
    if not user or not auth.verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
        
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support."
        )
        
    admin_emails = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "rapidpvccard@gmail.com").split(",") if e.strip()]
    is_admin_user = user.email.strip().lower() in admin_emails
    if user.is_admin != is_admin_user:
        user.is_admin = is_admin_user
        db.commit()
        
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    use_secure = is_secure_request(request)
    
    # Set HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=use_secure,
        max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    
    return {
        "message": "Successfully logged in",
        "user": {
            "name": user.name,
            "email": user.email,
            "is_admin": bool(user.is_admin)
        }
    }

@router.get("/logout")
def logout_get(request: Request, response: Response):
    use_secure = is_secure_request(request)
    redirect_res = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect_res.delete_cookie(
        "access_token", 
        path="/", 
        httponly=True, 
        samesite="lax", 
        secure=use_secure
    )
    return redirect_res

@router.post("/logout")
def logout_post(request: Request, response: Response):
    use_secure = is_secure_request(request)
    response.delete_cookie(
        "access_token", 
        path="/", 
        httponly=True, 
        samesite="lax", 
        secure=use_secure
    )
    return {"message": "Successfully logged out"}

from services.email_service import send_password_reset_email

@router.post("/forgot-password")
def forgot_password(
    request: Request,
    payload: schemas.ForgotPasswordRequest,
    db: Session = Depends(database.get_db)
):
    email = payload.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    
    # Generic security message (prevents account enumeration attacks)
    if not user:
        return {
            "success": True,
            "message": "If an account exists with this email, password reset instructions have been sent."
        }
        
    if user.status != "active":
        raise HTTPException(status_code=403, detail="This account is currently disabled. Please contact support.")
        
    token = auth.create_password_reset_token(user)
    base_url = str(request.base_url).rstrip("/")
    reset_url = f"{base_url}/reset-password?token={token}"
    
    sent, msg = send_password_reset_email(user.email, user.name, reset_url)
    
    return {
        "success": True,
        "message": "If an account exists with this email, password reset instructions have been sent.",
        "dev_test_url": reset_url if not sent else None
    }

@router.post("/reset-password")
def reset_password(
    payload: schemas.ResetPasswordRequest,
    db: Session = Depends(database.get_db)
):
    token = payload.token.strip()
    new_password = payload.new_password.strip()
    
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
    user = auth.verify_password_reset_token(token, db)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link. Please request a new one.")
        
    user.hashed_password = auth.get_password_hash(new_password)
    db.commit()
    
    return {
        "success": True,
        "message": "Password updated successfully. You can now sign in with your new password."
    }
