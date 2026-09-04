import os
import uuid
import datetime
from dotenv import load_dotenv
import asyncio
import time

load_dotenv()
from fastapi import FastAPI, Request, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel

import database
import models
import auth
from routers import auth_router, user_router, payment_router, admin_router

database.ensure_database_schema(database.engine)

# Background cleanup task (Zero-Retention Privacy Sweeper)
async def cleanup_temporary_files():
    retention_minutes = int(os.environ.get("FILE_RETENTION_MINUTES", "10"))
    while True:
        try:
            now = time.time()
            # 1. Clean uploads and output directories
            for directory in ['uploads', 'output']:
                if os.path.exists(directory):
                    for filename in os.listdir(directory):
                        if filename == '.gitkeep':
                            continue
                        filepath = os.path.join(directory, filename)
                        if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - (retention_minutes * 60):
                            try: os.remove(filepath)
                            except: pass
                            print(f"[Cleanup] Removed stale file: {filepath}")

            # 2. Clean static/renders temporary preview directories
            renders_dir = os.path.join("static", "renders")
            if os.path.exists(renders_dir):
                for dirname in os.listdir(renders_dir):
                    dirpath = os.path.join(renders_dir, dirname)
                    if os.path.isdir(dirpath) and os.stat(dirpath).st_mtime < now - (retention_minutes * 60):
                        shutil.rmtree(dirpath, ignore_errors=True)
                        print(f"[Cleanup] Purged stale render directory: {dirpath}")
        except Exception as e:
            print(f"[Cleanup Error] {e}")
        await asyncio.sleep(60 * 3) # Check every 3 minutes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(cleanup_temporary_files())
    yield
    # Shutdown
    task.cancel()

try:
    from engine.aadhaar_extractor import extract_aadhaar_data
    from engine.ayushman_extractor import extract_ayushman_data
    from engine.data_mapper import map_aadhaar_data, map_ayushman_data
    from engine.card_renderer import render_card
    from engine.qr_recovery import recover_qr_from_pdf
    from engine.a4_print import create_a4_print_pdf
except (ImportError, FileNotFoundError) as e:
    err_msg = str(e)
    def extract_aadhaar_data(pdf_path, password=None):
        class DummyAadhaarData:
            def __init__(self):
                self.source = "failed"
                self.errors = [f"Import failed: {err_msg}"]
            def to_json_safe_dict(self):
                return {"source": "failed", "errors": self.errors}
        return DummyAadhaarData()
    def map_aadhaar_data(data):
        return {}
    def recover_qr_from_pdf(pdf_path, password=None, trace=None):
        return None
    def create_a4_print_pdf(front_path, back_path, output_path):
        pass

# Ensure directories exist
for directory in ['uploads', 'output']:
    os.makedirs(directory, exist_ok=True)

app = FastAPI(title="PVC Card Pro", version="1.0.0", lifespan=lifespan)

# Mount routers
app.include_router(auth_router.router)
app.include_router(user_router.router)
app.include_router(payment_router.router)
app.include_router(admin_router.router)

from services.banner_service import get_banner_config

@app.get("/api/banner")
async def get_public_banner():
    return get_banner_config()

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def read_root(request: Request):
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(request=request, name="landing.html")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(database.get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login?error=Admin+login+required.+Please+login+first.")
    try:
        from jose import jwt
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return RedirectResponse(url="/login?error=Please+login+as+Admin")
        user = db.query(models.User).filter(models.User.id == int(user_id)).first()
        if not user:
            return RedirectResponse(url="/login?error=Session+expired.+Please+login+again.")
        if auth.is_admin_email(user.email) and not user.is_admin:
            user.is_admin = True
            db.commit()
        if not user.is_admin:
            return RedirectResponse(url="/login?error=Access+denied.+Administrator+privileges+required.")
    except Exception:
        return RedirectResponse(url="/login?error=Session+expired.+Please+login+again.")
    return templates.TemplateResponse(request=request, name="admin_dashboard.html")

@app.get("/subscription")
async def subscription_page(request: Request):
    return templates.TemplateResponse(request=request, name="subscription.html")

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

@app.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(request=request, name="forgot_password.html")

@app.get("/reset-password")
async def reset_password_page(request: Request):
    token = request.query_params.get("token", "")
    return templates.TemplateResponse(request=request, name="reset_password.html", context={"token": token})

@app.get("/dashboard")
async def dashboard_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/generator")
async def generator_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/history")
async def history_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request=request, name="history.html")

@app.get("/profile")
async def profile_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request=request, name="profile.html")

# =========================================================
# MANDATORY COMPLIANCE & LEGAL ROUTES (Payment Gateway Approved)
# =========================================================
@app.get("/contact", response_class=HTMLResponse)
@app.get("/contact-us", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse(request=request, name="contact.html")

@app.get("/terms", response_class=HTMLResponse)
@app.get("/terms-and-conditions", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="terms.html")

@app.get("/refund-policy", response_class=HTMLResponse)
@app.get("/refunds-and-cancellations", response_class=HTMLResponse)
@app.get("/refund", response_class=HTMLResponse)
@app.get("/refunds", response_class=HTMLResponse)
async def refund_page(request: Request):
    return templates.TemplateResponse(request=request, name="refund_policy.html")

@app.get("/privacy-policy", response_class=HTMLResponse)
@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="privacy_policy.html")

class ContactMessageSchema(BaseModel):
    name: str
    email: str
    category: str = "General Business Inquiry"
    message: str

@app.post("/api/contact")
async def handle_contact_inquiry(payload: ContactMessageSchema):
    if not payload.name.strip() or not payload.email.strip() or not payload.message.strip():
        return JSONResponse(status_code=400, content={"success": False, "error": "Name, email, and message are required."})
    try:
        from services.email_service import send_contact_inquiry
        await run_in_threadpool(
            send_contact_inquiry,
            payload.name.strip(),
            payload.email.strip(),
            payload.category.strip(),
            payload.message.strip()
        )
    except Exception as e:
        print(f"[Contact API] Error logging inquiry: {e}")
    return {
        "success": True,
        "message": "Thank you! Your support request has been logged. Our helpdesk will respond to your registered email within 24-48 business hours."
    }

@app.get("/health")
async def health_check():
    return {
        "success": True,
        "status": "online",
        "project": "PVC Card Pro",
        "version": "1.0.0"
    }

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
UPLOAD_DIR = "uploads"

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...), current_user: models.User = Depends(auth.get_current_user)):
    # Validate content type
    if file.content_type != "application/pdf":
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Only PDF files are allowed"}
        )
    
    # Read file content safely up to max size + 1 byte
    content = await file.read(MAX_FILE_SIZE + 1)
    
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=413,
            content={"success": False, "error": "File size exceeds the 10 MB limit"}
        )
        
    # Extra validation: check magic bytes for PDF
    if not content.startswith(b"%PDF-"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "File does not appear to be a valid PDF"}
        )

    filename = f"{uuid.uuid4()}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)
        
    try:
        with open(filepath, "wb") as f:
            f.write(content)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Could not save file"}
        )

    return {
        "success": True,
        "message": "PDF uploaded successfully",
        "filename": filename
    }

def format_extraction_error(engine_data: dict) -> tuple[str, str]:
    errors = engine_data.get("errors", [])
    err_str = " ".join(str(e) for e in errors)
    err_lower = err_str.lower()
    if "incorrect pdf password" in err_lower or "password invalid" in err_lower or "authenticate" in err_lower:
        return "Incorrect PDF password. Please enter the correct password.", "INCORRECT_PASSWORD"
    if "password protected" in err_lower or "supply the password" in err_lower or "requires password" in err_lower:
        return "This PDF is password protected. Please enter the password.", "PASSWORD_REQUIRED"
    if errors:
        return f"Extraction failed: {errors[0]}", "EXTRACTION_FAILED"
    return "Extraction failed. Unable to extract document details.", "EXTRACTION_FAILED"

@app.post("/extract")
async def extract_pdf(
    file: UploadFile = File(...), 
    password: str = Form(None), 
    document_type: str = Form("aadhaar"),
    current_user: models.User = Depends(auth.get_current_user)
):
    if file.content_type != "application/pdf":
        return JSONResponse(status_code=400, content={"success": False, "error": "Only PDF files are allowed"})
    
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(status_code=413, content={"success": False, "error": "File size exceeds 10 MB"})
        
    if not content.startswith(b"%PDF-"):
        return JSONResponse(status_code=400, content={"success": False, "error": "Not a valid PDF"})

    filename = f"{uuid.uuid4()}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)
        
    try:
        with open(filepath, "wb") as f:
            f.write(content)
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": "Could not save file"})
        
    try:
        doc_type = (document_type or "aadhaar").lower().strip()
        if doc_type == "ayushman":
            result = extract_ayushman_data(filepath, password=password)
            data = result.to_json_safe_dict()
            if data.get("source") == "failed":
                err_msg, err_code = format_extraction_error(data)
                return JSONResponse(status_code=400, content={"success": False, "error": err_msg, "code": err_code, "details": data})
            mapped_data = map_ayushman_data(data)
        else:
            result = extract_aadhaar_data(filepath, password=password)
            data = result.to_json_safe_dict()
            if data.get("source") == "failed":
                err_msg, err_code = format_extraction_error(data)
                return JSONResponse(status_code=400, content={"success": False, "error": err_msg, "code": err_code, "details": data})
            mapped_data = map_aadhaar_data(data)
            qr_b64 = recover_qr_from_pdf(filepath, password, data.get("trace", []))
            if qr_b64:
                mapped_data["qr"]["available"] = True
                mapped_data["qr"]["base64"] = qr_b64
            
        try: os.remove(filepath)
        except: pass
            
        return {"success": True, "engine_data": data, "mapped_data": mapped_data, "document_type": doc_type}
    except Exception as e:
        try: os.remove(filepath)
        except: pass
        return JSONResponse(status_code=500, content={"success": False, "error": f"Internal error: {str(e)}"})

@app.post("/generate")
async def generate_pipeline(
    file: UploadFile = File(...), 
    password: str = Form(None), 
    document_type: str = Form("aadhaar"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    user_rate = float(getattr(current_user.credits, 'cost_per_card', 0.95) or 0.95)
    if current_user.credits.wallet_balance < user_rate:
        return JSONResponse(
            status_code=402,
            content={"success": False, "error": f"Insufficient wallet balance to generate a card. Required: ₹{user_rate:.2f}"}
        )

    if file.content_type != "application/pdf":
        return JSONResponse(status_code=400, content={"success": False, "error": "Only PDF files are allowed"})
    
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(status_code=413, content={"success": False, "error": "File size exceeds the 10 MB limit"})
        
    if not content.startswith(b"%PDF-"):
        return JSONResponse(status_code=400, content={"success": False, "error": "File does not appear to be a valid PDF"})

    doc_type = (document_type or "aadhaar").lower().strip()
    run_id = str(uuid.uuid4())
    filename = f"{run_id}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    # Initialize history record
    history = models.GenerationHistory(
        id=run_id,
        user_id=current_user.id,
        run_id=run_id,
        document_type=doc_type,
        status="processing"
    )
    db.add(history)
    db.commit()
    
    try:
        with open(filepath, "wb") as f:
            f.write(content)
    except Exception as e:
        history.status = "failed"
        db.commit()
        return JSONResponse(status_code=500, content={"success": False, "error": "Could not save file"})
        
    try:
        if doc_type == "ayushman":
            result = extract_ayushman_data(filepath, password=password)
            engine_data = result.to_json_safe_dict()
            if engine_data.get("source") == "failed":
                history.status = "failed"
                history.completed_at = datetime.datetime.utcnow()
                db.commit()
                try: os.remove(filepath)
                except: pass
                err_msg, err_code = format_extraction_error(engine_data)
                return JSONResponse(status_code=400, content={"success": False, "error": err_msg, "code": err_code, "details": engine_data})
            mapped_data = map_ayushman_data(engine_data)
        else:
            result = extract_aadhaar_data(filepath, password=password)
            engine_data = result.to_json_safe_dict()
            if engine_data.get("source") == "failed":
                history.status = "failed"
                history.completed_at = datetime.datetime.utcnow()
                db.commit()
                try: os.remove(filepath)
                except: pass
                err_msg, err_code = format_extraction_error(engine_data)
                return JSONResponse(status_code=400, content={"success": False, "error": err_msg, "code": err_code, "details": engine_data})
            # Pass PDF path/password into engine_data so data_mapper can do a text scan
            engine_data["__pdf_path__"] = filepath
            engine_data["__pdf_password__"] = password
            mapped_data = map_aadhaar_data(engine_data)
            qr_b64 = engine_data.get("qr_base64") or recover_qr_from_pdf(filepath, password, engine_data.get("trace", []))
            if qr_b64:
                mapped_data["qr"]["available"] = True
                mapped_data["qr"]["base64"] = qr_b64

        try: os.remove(filepath)
        except: pass
        
        output_dir = os.path.join("static", "renders", run_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # High-Speed Persistent Rendering Worker
        front_path, back_path = await run_in_threadpool(render_card, mapped_data, engine_data, output_dir, doc_type)
        
        # Pre-generate standard A4 print PDF in the same pass
        pdf_path = os.path.join(output_dir, "a4_print.pdf")
        try:
            await run_in_threadpool(create_a4_print_pdf, [front_path], [back_path], pdf_path, False)
        except Exception as e:
            print(f"[A4 Pre-generation Warning] {e}")

        # Deduct credit on successful generation
        current_user.credits.wallet_balance -= user_rate
        current_user.credits.total_generated += 1
        history.status = "success"
        history.completed_at = datetime.datetime.utcnow()
        
        tx = models.CreditTransaction(
            user_id=current_user.id,
            amount=-user_rate,
            transaction_type="generation_usage",
            reference_id=run_id,
            balance_after=current_user.credits.wallet_balance
        )
        db.add(tx)
        
        db.commit()
        
        return {
            "success": True,
            "run_id": run_id,
            "document_type": doc_type,
            "mapped_data": mapped_data,
            "front_url": f"/static/renders/{run_id}/front.png",
            "back_url": f"/static/renders/{run_id}/back.png",
            "pdf_url": f"/download-pdf/{run_id}",
            "extraction_status": engine_data.get("extraction_confidence", "unknown"),
            "photo_available": mapped_data.get("photo", {}).get("available", False),
            "qr_available": mapped_data.get("qr", {}).get("available", False)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        history.status = "failed"
        history.completed_at = datetime.datetime.utcnow()
        db.commit()
        try: os.remove(filepath)
        except: pass
        return JSONResponse(status_code=500, content={"success": False, "error": f"Pipeline failure: {type(e).__name__}: {str(e) or repr(e)}"})

class A4GenerateRequest(BaseModel):
    run_id: str
    cards_count: int = 1
    mirror_duplex: bool = True

@app.post("/generate-a4")
async def generate_a4(
    req: A4GenerateRequest, 
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify ownership
    history = db.query(models.GenerationHistory).filter(
        models.GenerationHistory.run_id == req.run_id,
        models.GenerationHistory.user_id == current_user.id
    ).first()
    
    if not history:
        return JSONResponse(status_code=403, content={"success": False, "error": "Access denied or run_id not found"})

    run_id = req.run_id
    output_dir = os.path.join("static", "renders", run_id)
    front_path = os.path.join(output_dir, "front.png")
    back_path = os.path.join(output_dir, "back.png")
    
    if not os.path.exists(front_path) or not os.path.exists(back_path):
        return JSONResponse(status_code=404, content={"success": False, "error": "Generated cards not found."})
        
    pdf_path = os.path.join(output_dir, "a4_print.pdf")
    fronts = [front_path] * req.cards_count
    backs = [back_path] * req.cards_count
    
    try:
        result = await run_in_threadpool(create_a4_print_pdf, fronts, backs, pdf_path, req.mirror_duplex)
        result["pdf_url"] = f"/download-pdf/{run_id}"
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"A4 Generation failure: {str(e)}"})

import shutil
from fastapi.responses import FileResponse
from fastapi import BackgroundTasks

@app.get("/download-pdf/{run_id}")
async def download_pdf(
    run_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify ownership
    history = db.query(models.GenerationHistory).filter(
        models.GenerationHistory.run_id == run_id,
        models.GenerationHistory.user_id == current_user.id
    ).first()
    
    if not history:
        return JSONResponse(status_code=403, content={"success": False, "error": "Access denied or run_id not found"})

    pdf_path = os.path.join("static", "renders", run_id, "a4_print.pdf")
    
    if not os.path.exists(pdf_path):
        return JSONResponse(status_code=404, content={"success": False, "error": "File not found or expired."})
    
    return FileResponse(
        path=pdf_path,
        filename=f"PVC_Card_{run_id[:8]}.pdf",
        media_type="application/pdf"
    )
