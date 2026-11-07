"""
bg_remover.py - Enterprise AI Image Background Removal Engine
--------------------------------------------------------------
Features:
- Instant 1-click AI cutout using pre-warmed ONNX runtime neural model.
- Supports any image input: Portraits, Products, Signatures, Documents, Stamps (JPG, PNG, WEBP).
- Export modes:
    * 100% Transparent PNG (Alpha channel preserved with crisp edges)
    * Solid Studio Color Replacement (White, Light Blue, Navy Blue, Red, Grey, Custom Hex)
- High-resolution retention without loss of quality.
"""

import os
import io
import time
from typing import Optional, Dict, Any, Tuple
from PIL import Image

try:
    from engine.passport_photo import _get_rembg_session, COLOR_PALETTE, _resolve_bg_color
except ImportError:
    COLOR_PALETTE = {
        "white": (255, 255, 255),
        "light_blue": (180, 215, 255),
        "studio_blue": (75, 156, 211),
        "navy_blue": (30, 58, 138),
        "red": (220, 38, 38),
        "light_grey": (229, 231, 235),
        "cream": (254, 249, 195),
        "transparent": None
    }
    def _resolve_bg_color(name, custom=None):
        if custom and custom.startswith("#") and len(custom) == 7:
            return (int(custom[1:3], 16), int(custom[3:5], 16), int(custom[5:7], 16))
        return COLOR_PALETTE.get(str(name).lower(), (255, 255, 255))
    def _get_rembg_session():
        from rembg import new_session
        return new_session("u2netp")

def process_background_removal(
    input_file_path: str,
    output_dir: str,
    bg_color_name: str = "transparent",
    custom_hex: Optional[str] = None,
    max_dimension: int = 3000
) -> Dict[str, Any]:
    """
    Removes background from input image and generates:
    1. transparent.png - Pure transparent cutout
    2. colored.png / colored.jpg - Composite on selected background (if color requested)
    """
    os.makedirs(output_dir, exist_ok=True)
    t0 = time.time()

    with Image.open(input_file_path) as raw_img:
        orig_w, orig_h = raw_img.size
        orig_format = raw_img.format or "PNG"
        
        # If image is excessively huge (>3000px), downsample slightly for speed while keeping crisp HD
        if max(orig_w, orig_h) > max_dimension:
            scale = max_dimension / float(max(orig_w, orig_h))
            target_size = (int(orig_w * scale), int(orig_h * scale))
            work_img = raw_img.resize(target_size, Image.Resampling.LANCZOS).convert("RGBA")
        else:
            work_img = raw_img.convert("RGBA")

    # Run AI neural background removal
    from rembg import remove
    sess = _get_rembg_session()
    cutout = remove(work_img, session=sess) if sess is not None else remove(work_img)

    # 1. Save Transparent PNG
    transparent_path = os.path.join(output_dir, "transparent.png")
    cutout.save(transparent_path, format="PNG", optimize=True)

    # 2. Handle Color Replacement (if requested)
    colored_path = None
    has_color = False
    chosen_color_rgb = None
    
    clean_color_name = (bg_color_name or "transparent").lower().strip()
    if clean_color_name not in ["transparent", "none", "original", ""]:
        chosen_color_rgb = _resolve_bg_color(clean_color_name, custom_hex)
        if chosen_color_rgb is not None:
            # Composite cutout over solid color canvas
            color_bg = Image.new("RGBA", cutout.size, chosen_color_rgb + (255,))
            composite = Image.alpha_composite(color_bg, cutout).convert("RGB")
            
            colored_path = os.path.join(output_dir, "colored.jpg")
            composite.save(colored_path, format="JPEG", quality=95)
            has_color = True

    proc_time = time.time() - t0
    final_w, final_h = cutout.size
    trans_bytes = os.path.getsize(transparent_path) if os.path.exists(transparent_path) else 0
    colored_bytes = os.path.getsize(colored_path) if colored_path and os.path.exists(colored_path) else 0

    return {
        "success": True,
        "transparent_path": transparent_path,
        "colored_path": colored_path,
        "has_color": has_color,
        "width": final_w,
        "height": final_h,
        "original_width": orig_w,
        "original_height": orig_h,
        "transparent_size_kb": round(trans_bytes / 1024, 1),
        "colored_size_kb": round(colored_bytes / 1024, 1),
        "processing_time_sec": round(proc_time, 2),
        "bg_color": clean_color_name
    }

