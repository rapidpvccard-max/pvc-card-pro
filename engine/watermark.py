import os
from typing import Optional, Union
from PIL import Image, ImageDraw, ImageFont

def get_watermark_font(size: int) -> ImageFont.FreeTypeFont:
    """Load high-quality bold TTF font with graceful fallbacks."""
    font_paths = [
        os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "NirmalaB.ttf"),
        os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "Nirmala.ttf"),
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\segoeuib.ttf",
        "/usr/local/share/fonts/nirmala/NirmalaB.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def apply_card_watermark(image_input: Union[str, Image.Image], output_path: Optional[str] = None) -> Union[str, Image.Image]:
    """
    Applies an elegant, tamper-proof, high-contrast watermark to a PVC Card.
    Watermark includes:
    - Center bold diagonal banner:
        RAPID PVC
        ★ SAMPLE DEMO ★
        rapidpvc.online • NOT FOR OFFICIAL USE
    - Repeating secondary diagonal safety stamps (top & bottom)
    - Corner security banner
    
    Can accept a filepath (str) or a PIL Image instance.
    If image_input is a filepath, it overwrites or saves to output_path and returns the path.
    If image_input is a PIL Image, it returns the watermarked PIL Image.
    """
    is_path = isinstance(image_input, str)
    if is_path:
        card = Image.open(image_input).convert("RGBA")
        save_target = output_path or image_input
    else:
        card = image_input.convert("RGBA")
        save_target = output_path

    cw, ch = card.size

    # Create oversized transparent canvas for rotation
    diag_size = int((cw ** 2 + ch ** 2) ** 0.5) + 200
    overlay = Image.new("RGBA", (diag_size, diag_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_huge = get_watermark_font(int(ch * 0.11))   # ~70px
    font_med = get_watermark_font(int(ch * 0.065))   # ~41px
    font_small = get_watermark_font(int(ch * 0.045)) # ~28px

    cx = diag_size // 2
    cy = diag_size // 2

    # High-contrast dual fill (visible on dark, bright, or colorful cards)
    # White fill (150 alpha) with dark navy stroke (130 alpha)
    fill_main = (255, 255, 255, 140)
    stroke_dark = (15, 23, 42, 130)
    stroke_w = max(2, int(ch * 0.004))

    fill_accent = (239, 68, 68, 150) # Red accent for "SAMPLE DEMO"
    stroke_accent = (255, 255, 255, 150)

    # 1. Main Center Group
    line1 = "RAPID PVC"
    line2 = "• SAMPLE DEMO •"
    line3 = "rapidpvc.online • NOT FOR OFFICIAL USE"

    # Draw centered lines
    draw.text((cx, cy - int(ch * 0.08)), line1, font=font_huge, fill=fill_main, stroke_fill=stroke_dark, stroke_width=stroke_w, anchor="mm")
    draw.text((cx, cy + int(ch * 0.01)), line2, font=font_med, fill=fill_accent, stroke_fill=stroke_accent, stroke_width=2, anchor="mm")
    draw.text((cx, cy + int(ch * 0.085)), line3, font=font_small, fill=fill_main, stroke_fill=stroke_dark, stroke_width=stroke_w, anchor="mm")

    # 2. Secondary Repeating Diagonal Lines (Top & Bottom)
    rep_text_1 = "RAPID PVC • SAMPLE DEMO • rapidpvc.online"
    rep_text_2 = "TEST PRINT ONLY • RECHARGE TO REMOVE WATERMARK"
    draw.text((cx, cy - int(ch * 0.26)), rep_text_1, font=font_small, fill=fill_main, stroke_fill=stroke_dark, stroke_width=stroke_w, anchor="mm")
    draw.text((cx, cy + int(ch * 0.26)), rep_text_2, font=font_small, fill=fill_main, stroke_fill=stroke_dark, stroke_width=stroke_w, anchor="mm")

    # Rotate overlay by -28 degrees
    rotated = overlay.rotate(-28, resample=Image.Resampling.BICUBIC, center=(cx, cy))

    # Crop rotated overlay back to card size (centered)
    rx0 = (diag_size - cw) // 2
    ry0 = (diag_size - ch) // 2
    cropped_overlay = rotated.crop((rx0, ry0, rx0 + cw, ry0 + ch))

    # 3. Add Top Corner Ribbon / Badge on card overlay
    card_overlay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(card_overlay)

    # Subtle top-right watermark badge
    badge_text = "FREE DEMO SAMPLE"
    badge_font = get_watermark_font(int(ch * 0.035)) # ~22px
    badge_bg = (220, 38, 38, 175) # Semi-transparent crimson red
    badge_w = int(cw * 0.28)
    badge_h = int(ch * 0.055)
    c_draw.rounded_rectangle([cw - badge_w - 12, 12, cw - 12, 12 + badge_h], radius=6, fill=badge_bg)
    c_draw.text((cw - 12 - (badge_w // 2), 12 + (badge_h // 2)), badge_text, font=badge_font, fill=(255, 255, 255, 240), anchor="mm")

    # Combine overlays onto base card
    final_card = Image.alpha_composite(card, cropped_overlay)
    final_card = Image.alpha_composite(final_card, card_overlay)
    result_rgb = final_card.convert("RGB")

    if is_path:
        result_rgb.save(save_target, "PNG", dpi=(300, 300))
        return save_target
    else:
        if save_target:
            result_rgb.save(save_target, "PNG", dpi=(300, 300))
        return result_rgb
