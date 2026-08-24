import os
import json
import uuid
import shutil
from fastapi import UploadFile

CONFIG_DIR = "config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "banner_config.json")
BANNER_UPLOAD_DIR = os.path.join("static", "uploads", "banners")

DEFAULT_BANNER_CONFIG = {
    "enabled": True,
    "banner_type": "custom_text",  # "image" or "custom_text"
    "image_url": "",
    "link_url": "/subscription",
    "headline": "HIGH QUALITY PVC CARD",
    "badge_text": "STARTING AT JUST",
    "price_text": "₹ 0.95",
    "sub_text": "Professional PVC Cards Made Easy!",
    "bg_color": "#0f172a",
    "text_color": "#ffffff"
}

def ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(BANNER_UPLOAD_DIR, exist_ok=True)

def get_banner_config() -> dict:
    ensure_dirs()
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_BANNER_CONFIG, f, indent=2)
        return DEFAULT_BANNER_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = DEFAULT_BANNER_CONFIG.copy()
            merged.update(data)
            return merged
    except Exception:
        return DEFAULT_BANNER_CONFIG.copy()

def update_banner_config(updates: dict) -> dict:
    ensure_dirs()
    current = get_banner_config()
    current.update(updates)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return current

async def save_banner_image(file: UploadFile) -> str:
    ensure_dirs()
    ext = os.path.splitext(file.filename)[1].lower() or ".png"
    if ext not in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]:
        ext = ".png"
    
    unique_filename = f"banner_{uuid.uuid4().hex[:12]}{ext}"
    dest_path = os.path.join(BANNER_UPLOAD_DIR, unique_filename)
    
    with open(dest_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    return f"/static/uploads/banners/{unique_filename}"
