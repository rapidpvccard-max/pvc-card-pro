"""
passport_photo.py - Enterprise AI Passport Photo Studio Engine
--------------------------------------------------------------
Features:
- Smart AI face detection & auto-framing according to Indian standard 35mm x 45mm passport ratio.
- Automated AI background removal & studio color replacement (White, Light Blue, Navy Blue, Red, Grey).
- Optional Name & Date of Photo (DOP) label strip for government exam portals (SSC, Police, Railway).
- High-speed 300 DPI print sheet generator:
    * 4x6 Inch Glossy Paper: 8 Photos (2x4 standard) or 6 Photos or 12 Photos.
    * A4 Sheet Paper: 30 Photos or 36 Photos.
    * Single Digital Photo (auto-compressed under 50KB for online form upload).
- Crisp cutting guide marks for easy scissor/trimmer trimming.
"""

import os
import io
import math
from typing import Optional, Tuple, Any, Dict, List
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cv2
import numpy as np

# Standard Dimensions at 300 DPI
# 35mm x 45mm Indian Passport Photo = ~413 x 531 pixels
PHOTO_WIDTH = 413
PHOTO_HEIGHT = 531

# 4x6 Inch Sheet at 300 DPI = 1800 x 1200 pixels (Landscape) or 1200 x 1800 (Portrait)
SHEET_4X6_W = 1800
SHEET_4X6_H = 1200

# A4 Sheet at 300 DPI = 2480 x 3508 pixels
SHEET_A4_W = 2480
SHEET_A4_H = 3508

# Standard Background Color Palette
COLOR_PALETTE = {
    "white": (255, 255, 255),
    "light_blue": (180, 215, 255),    # Classic Indian exam & school light studio blue
    "studio_blue": (75, 156, 211),   # Standard studio blue
    "navy_blue": (30, 58, 138),      # Dark formal blue
    "red": (220, 38, 38),            # Standard red background
    "light_grey": (229, 231, 235),   # Visa & embassy standard grey
    "transparent": None
}


_REMBG_SESSION = None

def _get_rembg_session() -> Any:
    """Returns a cached, lightweight rembg session (silueta or u2netp)."""
    global _REMBG_SESSION
    if _REMBG_SESSION is None:
        try:
            from rembg import new_session
            try:
                _REMBG_SESSION = new_session("silueta")
            except Exception:
                _REMBG_SESSION = new_session("u2netp")
        except Exception:
            _REMBG_SESSION = None
    return _REMBG_SESSION


def _get_cascade_classifier() -> Any:
    """Load OpenCV Haar Cascade face detector if available."""
    try:
        if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            if os.path.exists(cascade_path):
                return cv2.CascadeClassifier(cascade_path)
    except Exception:
        pass
    return None


def detect_and_frame_face(pil_img: Image.Image) -> Image.Image:
    """
    Detects the candidate's face and smart-crops with standard 35mm x 45mm framing:
    - Head height covers ~70-75% of the photo height.
    - Top head margin is ~8-10% of total height.
    - Face is centered horizontally.
    """
    img_rgb = pil_img.convert("RGB")
    cv_img = np.array(img_rgb)
    orig_w, orig_h = img_rgb.size

    classifier = _get_cascade_classifier()
    faces = []
    if classifier is not None:
        try:
            gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
            faces = classifier.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(60, 60)
            )
        except Exception:
            faces = []

    if len(faces) > 0:
        # Pick the largest face (closest to camera)
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        fx, fy, fw, fh = faces[0]

        # Desired: face height (fh) should be approx 50-60% of total photo height
        # (With hair/chin, total head is ~70-75%)
        target_photo_h = int(fh * 1.85)
        target_photo_w = int(target_photo_h * (PHOTO_WIDTH / PHOTO_HEIGHT))

        # Face center
        cx = fx + fw // 2
        cy = fy + fh // 2

        # In standard passport photo, eyes/nose center is slightly above the vertical middle
        # Cy should be approx at 42-45% of total height from top
        crop_top = int(cy - (target_photo_h * 0.44))
        crop_bottom = crop_top + target_photo_h
        crop_left = int(cx - (target_photo_w / 2))
        crop_right = crop_left + target_photo_w

        # Handle out-of-bounds with padding if necessary
        pad_top = max(0, -crop_top)
        pad_bottom = max(0, crop_bottom - orig_h)
        pad_left = max(0, -crop_left)
        pad_right = max(0, crop_right - orig_w)

        if pad_top > 0 or pad_bottom > 0 or pad_left > 0 or pad_right > 0:
            padded_cv = cv2.copyMakeBorder(
                cv_img,
                pad_top, pad_bottom, pad_left, pad_right,
                cv2.BORDER_REPLICATE
            )
            padded_pil = Image.fromarray(padded_cv)
            crop_x1 = crop_left + pad_left
            crop_y1 = crop_top + pad_top
            crop_x2 = crop_right + pad_left
            crop_y2 = crop_bottom + pad_top
            cropped = padded_pil.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        else:
            cropped = img_rgb.crop((crop_left, crop_top, crop_right, crop_bottom))

    else:
        # Fallback: Intelligent portrait framing from silhouette if rembg is available
        framed_via_mask = False
        try:
            from rembg import remove
            # Quick small preview to find silhouette
            preview = img_rgb.copy()
            preview.thumbnail((500, 500))
            sess = _get_rembg_session()
            cutout = remove(preview, session=sess) if sess is not None else remove(preview)
            alpha = np.array(cutout)[:, :, 3]
            y_indices, x_indices = np.where(alpha > 35)
            if len(y_indices) > 50 and len(x_indices) > 50:
                scale_x = orig_w / preview.width
                scale_y = orig_h / preview.height
                
                min_x = int(np.min(x_indices) * scale_x)
                max_x = int(np.max(x_indices) * scale_x)
                min_y = int(np.min(y_indices) * scale_y)
                max_y = int(np.max(y_indices) * scale_y)
                
                # Person center and width
                person_cx = (min_x + max_x) // 2
                person_w = max_x - min_x
                person_h = max_y - min_y
                
                # Estimate head height from person bounding box
                est_head_h = int(person_w * 0.95) if person_w > 0 else int(person_h * 0.35)
                target_photo_h = int(est_head_h / 0.65)
                target_photo_w = int(target_photo_h * (PHOTO_WIDTH / PHOTO_HEIGHT))
                
                # Top margin 8% above head top
                crop_top = max(0, int(min_y - target_photo_h * 0.08))
                crop_bottom = min(orig_h, crop_top + target_photo_h)
                crop_left = max(0, int(person_cx - target_photo_w / 2))
                crop_right = min(orig_w, crop_left + target_photo_w)
                
                if (crop_right - crop_left) > 50 and (crop_bottom - crop_top) > 50:
                    cropped = img_rgb.crop((crop_left, crop_top, crop_right, crop_bottom))
                    framed_via_mask = True
        except Exception as e:
            pass

        if not framed_via_mask:
            # Fallback: Center crop to 35:45 aspect ratio
            current_ratio = orig_w / orig_h
            target_ratio = PHOTO_WIDTH / PHOTO_HEIGHT
            if current_ratio > target_ratio:
                new_w = int(orig_h * target_ratio)
                left = (orig_w - new_w) // 2
                cropped = img_rgb.crop((left, 0, left + new_w, orig_h))
            else:
                new_h = int(orig_w / target_ratio)
                top = int((orig_h - new_h) * 0.15)  # Keep upper 85% for head and shoulders
                cropped = img_rgb.crop((0, top, orig_w, top + new_h))

    # Resize to exact standard dimensions at 300 DPI
    final_framed = cropped.resize((PHOTO_WIDTH, PHOTO_HEIGHT), Image.Resampling.LANCZOS)
    return final_framed


def remove_and_replace_background(
    pil_img: Image.Image,
    bg_color_name: str = "light_blue",
    custom_hex: Optional[str] = None
) -> Image.Image:
    """
    Removes background using AI (rembg) and replaces it with the requested studio color.
    Falls back gracefully to original background if rembg is not available or fails.
    """
    target_color = (180, 215, 255)  # default light blue
    if custom_hex and custom_hex.startswith("#") and len(custom_hex) == 7:
        try:
            r = int(custom_hex[1:3], 16)
            g = int(custom_hex[3:5], 16)
            b = int(custom_hex[5:7], 16)
            target_color = (r, g, b)
        except Exception:
            pass
    elif bg_color_name.lower() in COLOR_PALETTE:
        val = COLOR_PALETTE[bg_color_name.lower()]
        if val is not None:
            target_color = val
        else:
            # transparent requested
            target_color = None

    # Try AI removal via rembg
    try:
        from rembg import remove
        sess = _get_rembg_session()
        cutout = remove(pil_img, session=sess) if sess is not None else remove(pil_img)
        # Cutout is RGBA
        if target_color is not None:
            bg = Image.new("RGBA", cutout.size, target_color + (255,))
            combined = Image.alpha_composite(bg, cutout).convert("RGB")
            return combined
        else:
            return cutout
    except Exception as e:
        # Fallback if rembg is not available: return framed image
        print(f"[PassportEngine] rembg notice: {e}, preserving framed image.")
        return pil_img.convert("RGB")


def add_name_and_dop(
    photo: Image.Image,
    candidate_name: str = "",
    date_of_photo: str = ""
) -> Image.Image:
    """
    Adds standard white strip at bottom of photo with Candidate Name and Date of Photo (DOP)
    required by official Indian exam portals (SSC, Police Bharti, UPSC, Army).
    """
    if not candidate_name and not date_of_photo:
        return photo

    result = photo.copy().convert("RGB")
    draw = ImageDraw.Draw(result)

    # Strip height = ~15% of total height
    strip_h = int(PHOTO_HEIGHT * 0.14)
    strip_top = PHOTO_HEIGHT - strip_h

    # Draw solid white bottom box with thin top border
    draw.rectangle([(0, strip_top), (PHOTO_WIDTH, PHOTO_HEIGHT)], fill=(255, 255, 255))
    draw.line([(0, strip_top), (PHOTO_WIDTH, strip_top)], fill=(200, 200, 200), width=1)

    # Try loading a clean font, fallback to default
    try:
        font_dir = os.path.join(os.path.dirname(__file__), "..", "static", "fonts")
        font_path = os.path.join(font_dir, "NirmalaB.ttf")
        font_name = ImageFont.truetype(font_path, 22) if os.path.exists(font_path) else ImageFont.load_default()
        font_dop = ImageFont.truetype(font_path, 19) if os.path.exists(font_path) else ImageFont.load_default()
    except Exception:
        font_name = ImageFont.load_default()
        font_dop = ImageFont.load_default()

    # Draw Name and Date
    if candidate_name and date_of_photo:
        # Two lines
        name_bbox = draw.textbbox((0, 0), candidate_name.upper(), font=font_name)
        nw = name_bbox[2] - name_bbox[0]
        draw.text(((PHOTO_WIDTH - nw) // 2, strip_top + 6), candidate_name.upper(), fill=(0, 0, 0), font=font_name)

        dop_str = f"DOP: {date_of_photo}" if not date_of_photo.upper().startswith("DOP") else date_of_photo
        dop_bbox = draw.textbbox((0, 0), dop_str, font=font_dop)
        dw = dop_bbox[2] - dop_bbox[0]
        draw.text(((PHOTO_WIDTH - dw) // 2, strip_top + 38), dop_str, fill=(0, 0, 0), font=font_dop)

    elif candidate_name:
        # Centered single line
        name_bbox = draw.textbbox((0, 0), candidate_name.upper(), font=font_name)
        nw = name_bbox[2] - name_bbox[0]
        draw.text(((PHOTO_WIDTH - nw) // 2, strip_top + (strip_h - 24) // 2), candidate_name.upper(), fill=(0, 0, 0), font=font_name)

    elif date_of_photo:
        dop_str = f"DOP: {date_of_photo}" if not date_of_photo.upper().startswith("DOP") else date_of_photo
        dop_bbox = draw.textbbox((0, 0), dop_str, font=font_dop)
        dw = dop_bbox[2] - dop_bbox[0]
        draw.text(((PHOTO_WIDTH - dw) // 2, strip_top + (strip_h - 22) // 2), dop_str, fill=(0, 0, 0), font=font_dop)

    return result


def add_cutting_border(photo: Image.Image) -> Image.Image:
    """Adds a crisp 1px light-grey cutting border around the passport photo."""
    result = photo.copy().convert("RGB")
    draw = ImageDraw.Draw(result)
    w, h = result.size
    draw.rectangle([(0, 0), (w - 1, h - 1)], outline=(180, 180, 180), width=1)
    return result


def generate_print_sheet(
    photo: Image.Image,
    layout_type: str = "4x6_8",  # "4x6_8", "4x6_6", "4x6_12", "a4_30", "a4_36"
    include_cutting_marks: bool = True
) -> Image.Image:
    """
    Arranges the passport photo into a high-density 300 DPI print-ready sheet.
    Layouts:
    - 4x6_8  : 4x6 inch paper (1800x1200) -> 8 Photos (4 cols x 2 rows) - Most popular for cyber cafes
    - 4x6_6  : 4x6 inch paper (1800x1200) -> 6 Photos (3 cols x 2 rows)
    - 4x6_12 : 4x6 inch paper (1800x1200) -> 12 Photos (4 cols x 3 rows, stamp size)
    - a4_30  : A4 paper (2480x3508)       -> 30 Photos (5 cols x 6 rows)
    - a4_36  : A4 paper (2480x3508)       -> 36 Photos (6 cols x 6 rows)
    """
    photo_bordered = add_cutting_border(photo)

    if layout_type.startswith("4x6"):
        sheet_w, sheet_h = SHEET_4X6_W, SHEET_4X6_H
        if layout_type == "4x6_6":
            cols, rows = 3, 2
        elif layout_type == "4x6_12":
            cols, rows = 4, 3
        else:
            cols, rows = 4, 2  # standard 8 photos

    elif layout_type.startswith("a4"):
        sheet_w, sheet_h = SHEET_A4_W, SHEET_A4_H
        if layout_type == "a4_30":
            cols, rows = 5, 6
        else:
            cols, rows = 6, 6  # standard 36 photos
    else:
        # Default to 4x6 8 photos
        sheet_w, sheet_h = SHEET_4X6_W, SHEET_4X6_H
        cols, rows = 4, 2

    # Scale photo if needed for 12 or 36 layouts
    if layout_type == "4x6_12":
        cur_w, cur_h = int(PHOTO_WIDTH * 0.82), int(PHOTO_HEIGHT * 0.82)
        unit_photo = photo_bordered.resize((cur_w, cur_h), Image.Resampling.LANCZOS)
    elif layout_type == "a4_36":
        cur_w, cur_h = int(PHOTO_WIDTH * 0.90), int(PHOTO_HEIGHT * 0.90)
        unit_photo = photo_bordered.resize((cur_w, cur_h), Image.Resampling.LANCZOS)
    else:
        cur_w, cur_h = PHOTO_WIDTH, PHOTO_HEIGHT
        unit_photo = photo_bordered

    sheet = Image.new("RGB", (sheet_w, sheet_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)

    # Calculate balanced margins
    total_content_w = cols * cur_w
    total_content_h = rows * cur_h

    gap_x = 24 if cols > 1 else 0
    gap_y = 24 if rows > 1 else 0

    total_w_with_gaps = total_content_w + (cols - 1) * gap_x
    total_h_with_gaps = total_content_h + (rows - 1) * gap_y

    start_x = max(20, (sheet_w - total_w_with_gaps) // 2)
    start_y = max(20, (sheet_h - total_h_with_gaps) // 2)

    for r in range(rows):
        for c in range(cols):
            x = start_x + c * (cur_w + gap_x)
            y = start_y + r * (cur_h + gap_y)
            sheet.paste(unit_photo, (x, y))

            # Draw corner/cutting guide marks between photos
            if include_cutting_marks:
                # Top-left cutting mark
                draw.line([(x - 8, y), (x - 2, y)], fill=(210, 210, 210), width=1)
                draw.line([(x, y - 8), (x, y - 2)], fill=(210, 210, 210), width=1)
                # Bottom-right cutting mark
                draw.line([(x + cur_w + 2, y + cur_h), (x + cur_w + 8, y + cur_h)], fill=(210, 210, 210), width=1)
                draw.line([(x + cur_w, y + cur_h + 2), (x + cur_w, y + cur_h + 8)], fill=(210, 210, 210), width=1)

    return sheet


def export_single_photo_compressed(photo: Image.Image, max_kb: int = 50) -> bytes:
    """
    Compresses single passport photo to meet exact Indian government exam upload specs
    (e.g. between 20KB and 50KB at 35mm x 45mm).
    """
    img_rgb = photo.convert("RGB")
    quality = 90
    buf = io.BytesIO()
    img_rgb.save(buf, format="JPEG", quality=quality, dpi=(300, 300))

    while len(buf.getvalue()) > max_kb * 1024 and quality > 30:
        quality -= 5
        buf = io.BytesIO()
        img_rgb.save(buf, format="JPEG", quality=quality, dpi=(300, 300))

    return buf.getvalue()


def process_passport_studio(
    input_file_path: str,
    output_dir: str,
    bg_color_name: str = "light_blue",
    custom_hex: Optional[str] = None,
    layout_type: str = "4x6_8",
    candidate_name: str = "",
    date_of_photo: str = ""
) -> dict:
    """
    Main orchestration entrypoint for AI Passport Photo Studio.
    Returns:
    - single_photo_path: Single 35x45mm cut photo
    - print_sheet_path: 4x6 or A4 print-ready high-res image
    - pdf_sheet_path: 300 DPI PDF for 1-click printing
    - single_compressed_path: Under-50KB JPEG for online application portals
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Open input image
    if input_file_path.lower().endswith(".pdf"):
        import fitz
        doc = fitz.open(input_file_path)
        page = doc[0]
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")
        doc.close()
        raw_pil = Image.open(io.BytesIO(img_bytes))
    else:
        raw_pil = Image.open(input_file_path)

    # 2. Smart Face Framing (35x45mm ratio)
    framed = detect_and_frame_face(raw_pil)

    # 3. AI Background Removal & Color Replacement
    colored = remove_and_replace_background(framed, bg_color_name, custom_hex)

    # 4. Optional Name & DOP Strip
    final_single = add_name_and_dop(colored, candidate_name, date_of_photo)

    # 5. Save Single Master Photo
    single_path = os.path.join(output_dir, "passport_single.png")
    final_single.save(single_path, "PNG", dpi=(300, 300))

    # 6. Save Compressed Single Photo (under 50KB for online portals)
    single_comp_bytes = export_single_photo_compressed(final_single, max_kb=50)
    single_comp_path = os.path.join(output_dir, "passport_single_online.jpg")
    with open(single_comp_path, "wb") as f:
        f.write(single_comp_bytes)

    # 7. Generate Print Sheet (4x6 or A4)
    sheet_img = generate_print_sheet(final_single, layout_type=layout_type, include_cutting_marks=True)
    sheet_path = os.path.join(output_dir, "passport_sheet.png")
    sheet_img.save(sheet_path, "PNG", dpi=(300, 300))

    # 8. Save 300 DPI Print PDF
    pdf_path = os.path.join(output_dir, "passport_print.pdf")
    sheet_img.save(pdf_path, "PDF", resolution=300.0)

    photo_count = 8
    if layout_type == "4x6_6": photo_count = 6
    elif layout_type == "4x6_12": photo_count = 12
    elif layout_type == "a4_30": photo_count = 30
    elif layout_type == "a4_36": photo_count = 36

    return {
        "success": True,
        "single_photo_path": single_path,
        "single_compressed_path": single_comp_path,
        "print_sheet_path": sheet_path,
        "pdf_sheet_path": pdf_path,
        "photo_count": photo_count,
        "layout_type": layout_type,
        "dimensions": f"{PHOTO_WIDTH}x{PHOTO_HEIGHT}",
        "dpi": 300
    }
