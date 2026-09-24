import os
import shutil
import uuid
import datetime
from dotenv import load_dotenv
import asyncio
import time
import base64
import io
import json

load_dotenv()
from fastapi import FastAPI, Request, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse, PlainTextResponse
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

# Background cleanup task (Strict Zero-Retention Privacy Sweeper - 5 Minutes)
async def cleanup_temporary_files():
    retention_seconds = int(os.environ.get("FILE_RETENTION_SECONDS", "300")) # Strictly 5 minutes (300s)
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
                        try:
                            if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - retention_seconds:
                                os.remove(filepath)
                                print(f"[Zero-Retention] Purged stale file: {filepath}")
                        except Exception:
                            pass

            # 2. Clean static/renders temporary preview directories
            renders_dir = os.path.join("static", "renders")
            if os.path.exists(renders_dir):
                for dirname in os.listdir(renders_dir):
                    if dirname == '.gitkeep':
                        continue
                    dirpath = os.path.join(renders_dir, dirname)
                    try:
                        if os.path.isdir(dirpath) and os.stat(dirpath).st_mtime < now - retention_seconds:
                            shutil.rmtree(dirpath, ignore_errors=True)
                            print(f"[Zero-Retention] Purged expired render session: {dirname}")
                    except Exception as err:
                        print(f"[Cleanup Error on {dirname}] {err}")
        except Exception as e:
            print(f"[Cleanup Loop Error] {e}")
        await asyncio.sleep(20) # Check frequently every 20 seconds

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
    from engine.card_cropper import (
        PRESETS,
        generate_page_preview,
        detect_card_boxes_in_page,
        smart_detect_card_layout,
        process_crop_and_print,
        open_pdf_document
    )
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

@app.get("/shipping-policy", response_class=HTMLResponse)
@app.get("/shipping-and-delivery", response_class=HTMLResponse)
@app.get("/delivery-policy", response_class=HTMLResponse)
@app.get("/shipping", response_class=HTMLResponse)
async def shipping_page(request: Request):
    return templates.TemplateResponse(request=request, name="shipping_policy.html")

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    return templates.TemplateResponse(request=request, name="subscription.html")

@app.get("/ads.txt", response_class=PlainTextResponse)
async def get_ads_txt():
    ads_file = os.path.join("static", "ads.txt")
    if os.path.exists(ads_file):
        with open(ads_file, "r", encoding="utf-8") as f:
            return f.read()
    return "google.com, pub-7359691130707617, DIRECT, f08c47fec0942fa0\n"

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
    template_style: str = Form("default"),
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
        style = (template_style or "default").lower().strip()
        if doc_type in ["aadhaar_color", "aadhaar-color", "aadhaar_colour", "colour_aadhaar", "color_aadhaar"]:
            doc_type = "aadhaar"
            style = "color"

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
            
        return {"success": True, "engine_data": data, "mapped_data": mapped_data, "document_type": doc_type, "template_style": style}
    except Exception as e:
        try: os.remove(filepath)
        except: pass
        return JSONResponse(status_code=500, content={"success": False, "error": f"Internal error: {str(e)}"})

@app.post("/generate")
async def generate_pipeline(
    file: UploadFile = File(...), 
    password: str = Form(None), 
    document_type: str = Form("aadhaar"),
    template_style: str = Form("default"),
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
    style = (template_style or "default").lower().strip()
    if doc_type in ["aadhaar_color", "aadhaar-color", "aadhaar_colour", "colour_aadhaar", "color_aadhaar"]:
        doc_type = "aadhaar"
        style = "color"

    run_id = str(uuid.uuid4())
    filename = f"{run_id}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    # Initialize history record
    doc_label = f"aadhaar (colourful)" if (doc_type == "aadhaar" and style == "color") else doc_type
    history = models.GenerationHistory(
        id=run_id,
        user_id=current_user.id,
        run_id=run_id,
        document_type=doc_label,
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
        
        # High-Speed Persistent Rendering Worker (Passes doc_type and template_style)
        front_path, back_path = await run_in_threadpool(render_card, mapped_data, engine_data, output_dir, doc_type, style)
        
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
            "template_style": style,
            "mapped_data": mapped_data,
            "front_url": f"/download-card/{run_id}/front",
            "back_url": f"/download-card/{run_id}/back",
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

# =========================================================
# UNIVERSAL SMART AUTO-CROP PVC PIPELINE (VOTER, E-SHRAM, PAN, DL)
# =========================================================

@app.post("/api/crop/upload-preview")
async def crop_upload_preview(
    file: UploadFile = File(...),
    password: str = Form(None),
    preset: str = Form("voter"),
    current_user: models.User = Depends(auth.get_current_user)
):
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(status_code=413, content={"success": False, "error": "File size exceeds 10 MB limit"})
    
    is_pdf = content.startswith(b"%PDF-") or (file.filename and file.filename.lower().endswith(".pdf"))
    is_img = any(content.startswith(header) for header in [b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF"]) or (file.filename and file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))
    
    if not is_pdf and not is_img:
        return JSONResponse(status_code=400, content={"success": False, "error": "Only PDF and standard image files (PNG/JPG) are supported."})
        
    temp_id = str(uuid.uuid4())
    ext = ".pdf" if is_pdf else (os.path.splitext(file.filename)[1].lower() if file.filename else ".png")
    filepath = os.path.join(UPLOAD_DIR, f"crop_{temp_id}{ext}")
    
    try:
        with open(filepath, "wb") as f:
            f.write(content)
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": "Could not save uploaded file."})

    try:
        if is_pdf:
            try:
                doc = open_pdf_document(filepath, password)
                try:
                    total_pages = len(doc)
                finally:
                    doc.close()
            except ValueError as ve:
                err_text = str(ve)
                code = "PASSWORD_REQUIRED" if "password protected" in err_text.lower() else "INCORRECT_PASSWORD"
                try: os.remove(filepath)
                except: pass
                return JSONResponse(status_code=400, content={"success": False, "error": err_text, "code": code})
                
            preview_img, orig_w, orig_h = generate_page_preview(filepath, page_number=0, password=password, target_width=900)
            detect_res = smart_detect_card_layout(filepath, page_number=0, password=password)
        else:
            from PIL import Image as PILImage
            with PILImage.open(filepath) as pil_img:
                orig_w, orig_h = pil_img.size
                scale = 900.0 / orig_w if orig_w > 900 else 1.0
                new_size = (int(orig_w * scale), int(orig_h * scale))
                preview_img = pil_img.resize(new_size, PILImage.Resampling.LANCZOS).convert("RGB")
            total_pages = 1
            detect_res = smart_detect_card_layout(filepath, pil_image=preview_img)

        buf = io.BytesIO()
        preview_img.convert("RGB").save(buf, format="JPEG", quality=85)
        b64_preview = base64.b64encode(buf.getvalue()).decode("utf-8")
        preview_data_url = f"data:image/jpeg;base64,{b64_preview}"
        
        is_auto_detected = detect_res.get("detected", False)
        detected_card_type = detect_res.get("card_type", preset)
        detected_label = detect_res.get("card_label", "Auto-Detected Card")
        front_box = detect_res.get("front_box")
        back_box = detect_res.get("back_box")
        is_dual = detect_res.get("is_dual", (back_box is not None))
        
        # If user explicitly passed a non-voter preset and auto-detect wasn't conclusive:
        if not is_auto_detected and preset in PRESETS and preset != "voter":
            preset_info = PRESETS[preset]
            front_box = preset_info["front"]
            back_box = preset_info.get("back")
            is_dual = (back_box is not None)
            detected_card_type = preset
            detected_label = preset_info["name"]

        return {
            "success": True,
            "temp_id": temp_id,
            "filename": file.filename,
            "file_ext": ext,
            "total_pages": total_pages,
            "preview_url": preview_data_url,
            "original_width": orig_w,
            "original_height": orig_h,
            "detected": is_auto_detected,
            "detected_type": detected_card_type,
            "detected_label": detected_label,
            "front_box": front_box,
            "back_box": back_box,
            "is_dual": is_dual,
            "presets": PRESETS
        }
    except Exception as e:
        try: os.remove(filepath)
        except: pass
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": f"Preview generation failed: {str(e)}"})

@app.post("/api/crop/generate")
async def crop_generate(
    temp_id: str = Form(...),
    file_ext: str = Form(".pdf"),
    front_box: str = Form(...),
    back_box: str = Form(None),
    card_type: str = Form("voter"),
    page_number: int = Form(0),
    password: str = Form(None),
    duplex_mode: bool = Form(False),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    user_rate = float(getattr(current_user.credits, 'cost_per_card', 0.95) or 0.95)
    if current_user.credits.wallet_balance < user_rate:
        return JSONResponse(
            status_code=402,
            content={"success": False, "error": f"Insufficient wallet balance. Required: ₹{user_rate:.2f}"}
        )

    filepath = os.path.join(UPLOAD_DIR, f"crop_{temp_id}{file_ext}")
    if not os.path.exists(filepath):
        return JSONResponse(status_code=404, content={"success": False, "error": "Uploaded file session expired or not found. Please upload again."})

    try:
        f_box = json.loads(front_box) if isinstance(front_box, str) else front_box
        b_box = json.loads(back_box) if back_box and isinstance(back_box, str) and back_box.strip() and back_box not in ["null", "None"] else (back_box if isinstance(back_box, dict) else None)
        if not isinstance(f_box, dict) or "x" not in f_box or "y" not in f_box:
            raise ValueError("Invalid front box structure")
    except Exception as pe:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid crop coordinates provided."})

    run_id = str(uuid.uuid4())
    doc_label = f"crop ({card_type.upper()})"
    history = models.GenerationHistory(
        id=run_id,
        user_id=current_user.id,
        run_id=run_id,
        document_type=doc_label,
        status="processing"
    )
    db.add(history)
    db.commit()

    output_dir = os.path.join("static", "renders", run_id)
    os.makedirs(output_dir, exist_ok=True)

    try:
        result = await run_in_threadpool(
            process_crop_and_print,
            pdf_path=filepath,
            front_box=f_box,
            back_box=b_box,
            output_dir=output_dir,
            page_number=page_number,
            password=password,
            duplex_mode=duplex_mode
        )

        try: os.remove(filepath)
        except: pass

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
            "document_type": doc_label,
            "front_url": f"/download-card/{run_id}/front",
            "back_url": f"/download-card/{run_id}/back" if result.get("has_back") else None,
            "has_back": result.get("has_back", False),
            "pdf_url": f"/download-pdf/{run_id}",
            "wallet_balance": current_user.credits.wallet_balance
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        history.status = "failed"
        history.completed_at = datetime.datetime.utcnow()
        db.commit()
        try: os.remove(filepath)
        except: pass
        return JSONResponse(status_code=500, content={"success": False, "error": f"Crop processing failed: {str(e)}"})

class A4GenerateRequest(BaseModel):
    run_id: str
    cards_count: int = 1
    mirror_duplex: bool = False
    side_by_side: bool = True

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
        result = await run_in_threadpool(create_a4_print_pdf, fronts, backs, pdf_path, req.mirror_duplex, req.side_by_side)
        result["pdf_url"] = f"/download-pdf/{run_id}"
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"A4 Generation failure: {str(e)}"})

from fastapi.responses import FileResponse

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

    run_dir = os.path.join("static", "renders", run_id)
    pdf_path = os.path.join(run_dir, "a4_print.pdf")

    # Strict 5-minute (300 seconds) Zero-Retention Expiry Check
    is_expired = False
    if history.created_at:
        elapsed = (datetime.datetime.utcnow() - history.created_at).total_seconds()
        if elapsed > 300: # 5 minutes
            is_expired = True
    elif os.path.exists(pdf_path) and (time.time() - os.path.getmtime(pdf_path) > 300):
        is_expired = True

    if is_expired or not os.path.exists(pdf_path):
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir, ignore_errors=True)
            print(f"[Zero-Retention] Purged expired download session: {run_id}")
        return JSONResponse(
            status_code=410,
            content={"success": False, "error": "File session expired. For zero-retention privacy, temporary files are permanently purged after 5 minutes."}
        )
    
    return FileResponse(
        path=pdf_path,
        filename=f"PVC_Card_{run_id[:8]}.pdf",
        media_type="application/pdf"
    )

@app.get("/download-card/{run_id}/{side}")
async def download_card(
    run_id: str,
    side: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    if side not in ["front", "back"]:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid card side requested."})

    history = db.query(models.GenerationHistory).filter(
        models.GenerationHistory.run_id == run_id,
        models.GenerationHistory.user_id == current_user.id
    ).first()
    
    if not history:
        return JSONResponse(status_code=403, content={"success": False, "error": "Access denied or run_id not found"})

    run_dir = os.path.join("static", "renders", run_id)
    file_path = os.path.join(run_dir, f"{side}.png")

    # Strict 5-minute (300 seconds) Zero-Retention Expiry Check
    is_expired = False
    if history.created_at:
        elapsed = (datetime.datetime.utcnow() - history.created_at).total_seconds()
        if elapsed > 300: # 5 minutes
            is_expired = True
    elif os.path.exists(file_path) and (time.time() - os.path.getmtime(file_path) > 300):
        is_expired = True

    if is_expired or not os.path.exists(file_path):
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir, ignore_errors=True)
            print(f"[Zero-Retention] Purged expired card download session: {run_id}")
        return JSONResponse(
            status_code=410,
            content={"success": False, "error": "File session expired. For zero-retention privacy, temporary files are permanently purged after 5 minutes."}
        )

    return FileResponse(
        path=file_path,
        filename=f"PVC_{side.capitalize()}_{run_id[:8]}.png",
        media_type="image/png"
    )

@app.post("/api/purge-run/{run_id}")
async def purge_run(
    run_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    history = db.query(models.GenerationHistory).filter(
        models.GenerationHistory.run_id == run_id,
        models.GenerationHistory.user_id == current_user.id
    ).first()
    
    if history:
        run_dir = os.path.join("static", "renders", run_id)
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir, ignore_errors=True)
            print(f"[Zero-Retention] Instant user/timer purge triggered for run: {run_id}")
        return {"success": True, "purged": True}
    return JSONResponse(status_code=404, content={"success": False, "error": "Run not found"})
