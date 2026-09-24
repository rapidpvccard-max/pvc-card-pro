import os
import math
from typing import Dict, List, Optional, Tuple, Any
import pymupdf  # PyMuPDF
from PIL import Image, ImageOps, ImageFilter
from engine.a4_print import create_a4_print_pdf, CARD_WIDTH, CARD_HEIGHT

# Standard CR80 Dimensions
# Width: 85.60 mm, Height: 53.98 mm -> Ratio ~ 1.5858
CR80_ASPECT_RATIO = 85.60 / 53.98  # ~1.58577

import cv2
import numpy as np

# Presets for popular Indian cards (Normalized coordinates: 0.0 to 1.0)
PRESETS: Dict[str, Dict[str, Any]] = {
    "voter": {
        "name": "Voter ID (e-EPIC)",
        "icon": "🗳️",
        "description": "Standard Election Commission e-EPIC side-by-side layout",
        "dual": True,
        "front": {"x": 0.076, "y": 0.582, "w": 0.412, "h": 0.185},
        "back":  {"x": 0.512, "y": 0.582, "w": 0.412, "h": 0.185}
    },
    "voter_old": {
        "name": "Voter ID (Old / Stacked)",
        "icon": "🗳️",
        "description": "Older e-EPIC layout (vertical stacked)",
        "dual": True,
        "front": {"x": 0.294, "y": 0.430, "w": 0.412, "h": 0.185},
        "back":  {"x": 0.294, "y": 0.650, "w": 0.412, "h": 0.185}
    },
    "eshram": {
        "name": "e-Shram Card (Stacked)",
        "icon": "💼",
        "description": "Ministry of Labour official stacked layout (Front on Top, Back Below)",
        "dual": True,
        "front": {"x": 0.1824, "y": 0.0696, "w": 0.3880, "h": 0.1878},
        "back":  {"x": 0.1824, "y": 0.2615, "w": 0.3880, "h": 0.1872}
    },
    "abha": {
        "name": "ABHA Card (Health Account)",
        "icon": "🏥",
        "description": "Ayushman Bharat Health Account official stacked layout (Front Top, Back Bottom)",
        "dual": True,
        "front": {"x": 0.0186, "y": 0.0158, "w": 0.9628, "h": 0.4775},
        "back":  {"x": 0.0186, "y": 0.5067, "w": 0.9628, "h": 0.4783}
    },
    "eshram_side": {
        "name": "e-Shram (Side-by-Side)",
        "icon": "💼",
        "description": "State CSC side-by-side e-Shram layout",
        "dual": True,
        "front": {"x": 0.078, "y": 0.550, "w": 0.412, "h": 0.185},
        "back":  {"x": 0.510, "y": 0.550, "w": 0.412, "h": 0.185}
    },
    "pan_dual": {
        "name": "e-PAN (NSDL / UTI - Dual Cut)",
        "icon": "💳",
        "description": "e-PAN card bottom scissors cut section (Front & Back)",
        "dual": True,
        "front": {"x": 0.1137, "y": 0.7721, "w": 0.4032, "h": 0.1761},
        "back":  {"x": 0.5169, "y": 0.7721, "w": 0.3952, "h": 0.1761}
    },
    "pan_single": {
        "name": "e-PAN (Single Front Card)",
        "icon": "💳",
        "description": "e-PAN single bottom-left card cut section",
        "dual": False,
        "front": {"x": 0.1137, "y": 0.7721, "w": 0.4032, "h": 0.1761},
        "back":  None
    },
    "dl": {
        "name": "Driving Licence (Sarathi / DL)",
        "icon": "🚗",
        "description": "Parivahan Sarathi DL Form 7 print layout",
        "dual": True,
        "front": {"x": 0.078, "y": 0.330, "w": 0.412, "h": 0.185},
        "back":  {"x": 0.510, "y": 0.330, "w": 0.412, "h": 0.185}
    },
    "kisan": {
        "name": "Kisan Credit Card (KCC)",
        "icon": "🌾",
        "description": "PM-Kisan / KCC side-by-side or stacked layout",
        "dual": True,
        "front": {"x": 0.068, "y": 0.143, "w": 0.410, "h": 0.183},
        "back":  {"x": 0.521, "y": 0.143, "w": 0.411, "h": 0.183}
    },
    "ration": {
        "name": "Smart Ration Card",
        "icon": "🌾",
        "description": "NFSA / PDS Smart Ration Card layout",
        "dual": True,
        "front": {"x": 0.254, "y": 0.120, "w": 0.492, "h": 0.219},
        "back":  {"x": 0.254, "y": 0.381, "w": 0.492, "h": 0.218}
    },
    "labour": {
        "name": "Labour / Shramik Card",
        "icon": "👷",
        "description": "BOCW State Shramik Kalyan Card",
        "dual": True,
        "front": {"x": 0.078, "y": 0.550, "w": 0.412, "h": 0.185},
        "back":  {"x": 0.510, "y": 0.550, "w": 0.412, "h": 0.185}
    },
    "custom": {
        "name": "Universal Auto-Detect",
        "icon": "⚡",
        "description": "Automatic rectangular card & cut-line detection",
        "dual": True,
        "front": {"x": 0.078, "y": 0.550, "w": 0.412, "h": 0.185},
        "back":  {"x": 0.510, "y": 0.550, "w": 0.412, "h": 0.185}
    }
}


def open_pdf_document(pdf_path: str, password: Optional[str] = None) -> pymupdf.Document:
    """Opens and authenticates a PDF document with optional password."""
    doc = pymupdf.open(pdf_path)
    if doc.is_encrypted:
        if password:
            ok = doc.authenticate(password)
            if not ok:
                raise ValueError("Incorrect PDF password. Unable to unlock document.")
        else:
            raise ValueError("This PDF is password protected. Please provide a password.")
    return doc


def _box_overlap(b1: Dict[str, float], b2: Dict[str, float]) -> float:
    """Calculates intersection over minimum area between two bounding boxes."""
    x_l = max(b1["x"], b2["x"])
    y_t = max(b1["y"], b2["y"])
    x_r = min(b1["x"] + b1["w"], b2["x"] + b2["w"])
    y_b = min(b1["y"] + b1["h"], b2["y"] + b2["h"])
    if x_r <= x_l or y_b <= y_t:
        return 0.0
    inter = (x_r - x_l) * (y_b - y_t)
    min_a = min(b1["w"] * b1["h"], b2["w"] * b2["h"])
    return inter / min_a if min_a > 0 else 0.0


def find_best_card_pair(clean_boxes: List[Dict[str, float]]) -> Optional[Tuple[Dict[str, float], Dict[str, float]]]:
    """
    Universal Geometric Pair Finder:
    Evaluates all candidate boxes on ANY document (Kisan, Ration, Labour, Student, Voter, etc.)
    and discovers the matching Front & Back PVC cards:
    - Verifies identical dimensions (|w1 - w2| <= 15%, |h1 - h2| <= 15%).
    - Evaluates proximity to standard CR80 aspect ratio (~1.5858).
    - Checks geometric alignment:
      * Horizontal (side-by-side): Left is FRONT, Right is BACK.
      * Vertical (stacked): Top is FRONT, Bottom is BACK.
    """
    if len(clean_boxes) < 2:
        return None

    best_score = float('inf')
    best_pair = None
    n = len(clean_boxes)

    for i in range(n):
        for j in range(i + 1, n):
            b1 = clean_boxes[i]
            b2 = clean_boxes[j]

            # Cards must not overlap
            if _box_overlap(b1, b2) > 0.05:
                continue

            max_w = max(b1['w'], b2['w'])
            max_h = max(b1['h'], b2['h'])
            w_diff = abs(b1['w'] - b2['w']) / max_w if max_w > 0 else 1.0
            h_diff = abs(b1['h'] - b2['h']) / max_h if max_h > 0 else 1.0

            # Real PVC cards on official documents have matched sizes (< 15% diff)
            if w_diff > 0.15 or h_diff > 0.15:
                continue

            asp_err1 = abs(b1['aspect'] - CR80_ASPECT_RATIO)
            asp_err2 = abs(b2['aspect'] - CR80_ASPECT_RATIO)

            is_horiz = abs(b1['y'] - b2['y']) < 0.06
            is_vert = abs(b1['x'] - b2['x']) < 0.06

            align_score = 0.0
            if is_horiz:
                align_score = abs(b1['y'] - b2['y']) * 3.0
            elif is_vert:
                align_score = abs(b1['x'] - b2['x']) * 3.0
            else:
                align_score = 4.0  # diagonal / unaligned penalty

            # Size penalty + aspect ratio penalty + alignment score
            score = (w_diff * 4.0) + (h_diff * 4.0) + (asp_err1 + asp_err2) * 2.0 + align_score

            if score < best_score:
                best_score = score
                if is_horiz:
                    front = b1 if b1['x'] < b2['x'] else b2
                    back = b2 if b1['x'] < b2['x'] else b1
                elif is_vert:
                    front = b1 if b1['y'] < b2['y'] else b2
                    back = b2 if b1['y'] < b2['y'] else b1
                else:
                    front, back = (b1, b2) if (b1['y'], b1['x']) < (b2['y'], b2['x']) else (b2, b1)
                best_pair = (front, back)

    return best_pair


def smart_detect_card_layout(
    pdf_path_or_page: Any,
    page_number: int = 0,
    password: Optional[str] = None,
    pil_image: Optional[Image.Image] = None
) -> Dict[str, Any]:
    """
    Advanced multi-layered universal card boundary and type detection:
    1. Document Text/Keyword analysis (identifies Kisan, Ration, Labour, e-Shram, Voter, PAN, DL, etc.)
    2. Computer Vision:
       - Pass A: OpenCV Canny edge detection + cv2.RETR_TREE (captures black borders & scissor lines)
       - Pass B: Otsu binary thresholding with inversion (captures solid/tinted colored cards)
       - Detects individual CR80 cards (~1.58 ratio) even inside outer borders
       - Detects stacked dual-cards (~0.79 ratio) and splits into Front & Back
       - Detects side-by-side dual-cards (~3.0 ratio) and splits into Front & Back
    3. PyMuPDF embedded image bounding boxes and vector drawing inspection
    4. Smart Overlap NMS to discard inner text boxes and isolate card boundaries
    5. Universal Geometric Pair Matching: Pairs Front and Back cards with 100% precision
    """
    page_text = ""
    img_bgr = None
    pw, ph = 0, 0
    doc_to_close = None
    page = None

    try:
        if pil_image is not None:
            img_bgr = cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)
            ph, pw = img_bgr.shape[:2]
        elif isinstance(pdf_path_or_page, str):
            ext = os.path.splitext(pdf_path_or_page)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp"]:
                with Image.open(pdf_path_or_page) as pi:
                    img_bgr = cv2.cvtColor(np.array(pi.convert("RGB")), cv2.COLOR_RGB2BGR)
                    ph, pw = img_bgr.shape[:2]
            else:
                doc = open_pdf_document(pdf_path_or_page, password)
                doc_to_close = doc
                if page_number < 0 or page_number >= len(doc):
                    page_number = 0
                page = doc[page_number]
                pw, ph = page.rect.width, page.rect.height
                page_text = page.get_text().lower()
                pix = page.get_pixmap(dpi=150)
                img_bgr = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
                img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_RGB2BGR)
        elif hasattr(pdf_path_or_page, "rect"):
            # It's a PyMuPDF Page
            page = pdf_path_or_page
            pw, ph = page.rect.width, page.rect.height
            page_text = page.get_text().lower()
            pix = page.get_pixmap(dpi=150)
            img_bgr = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
            img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_RGB2BGR)

        # 1. Text Keyword Hints
        filename_hint = ""
        if isinstance(pdf_path_or_page, str):
            filename_hint = os.path.basename(pdf_path_or_page).lower()

        detected_type = None
        card_label = "Auto-Detected Card"
        import re
        if any(k in page_text for k in ["election commission", "epic", "voter", "निर्वाचन आयोग", "electoral photo", "electoral roll"]) or "voter" in filename_hint or "epic" in filename_hint:
            detected_type = "voter"
            card_label = "Voter ID (e-EPIC)"
        elif any(k in page_text for k in ["kisan", "krishi", "kcc", "किसान", "कृषि", "pm-kisan", "pm kisan"]) or "kisan" in filename_hint or "kcc" in filename_hint:
            detected_type = "kisan"
            card_label = "Kisan Credit Card (KCC)"
        elif any(k in page_text for k in ["ration card", "khadya", "food & civil supplies", "nfsa", "राशन", "खाद्य", "pds", "ration"]) or "ration" in filename_hint:
            # Prevent 'registration' from matching 'ration'
            if "ration card" in page_text or re.search(r'\bration\b', page_text) or any(k in page_text for k in ["khadya", "food & civil supplies", "nfsa", "राशन", "खाद्य", "pds"]) or "ration" in filename_hint:
                detected_type = "ration"
                card_label = "Smart Ration Card"
        elif any(k in page_text for k in ["labour", "shramik", "bocw", "भवन एवं सन्निर्माण", "श्रमिक", "मजदूर"]) or "labour" in filename_hint or "shramik" in filename_hint:
            detected_type = "labour"
            card_label = "Labour / Shramik Card"
        elif any(k in page_text for k in ["jan aadhaar", "जन आधार"]) or "jan" in filename_hint:
            detected_type = "janaadhaar"
            card_label = "Jan Aadhaar Card"
        elif any(k in page_text for k in ["e-shram", "eshram", "universal account number", "uan", "ई-श्रम", "shram.gov.in"]) or "uan" in filename_hint or "eshram" in filename_hint:
            detected_type = "eshram"
            card_label = "e-Shram Card"
        elif any(k in page_text for k in ["abha", "abdm", "@abdm", "health account", "स्वास्थ्य खाता", "national health authority", "राष्ट्रीय स्वास्थ्य प्राधिकरण"]) or "abha" in filename_hint:
            detected_type = "abha"
            card_label = "ABHA Card (Health Account)"
        elif any(k in page_text for k in ["income tax department", "permanent account number", "pan", "cxs"]) or "pan" in filename_hint:
            detected_type = "pan_dual"
            card_label = "e-PAN Card"
        elif any(k in page_text for k in ["driving licence", "transport department", "dl no", "form 7", "parivahan"]) or "dl" in filename_hint:
            detected_type = "dl"
            card_label = "Driving Licence"
        elif any(k in page_text for k in ["pmjay", "ayushman", "pm-jay", "आयुष्मान"]) or "ayushman" in filename_hint:
            detected_type = "ayushman"
            card_label = "Ayushman / Health Card"

        if not detected_type and re.search(r'\b\d{2}-\d{4}-\d{4}-\d{4}\b', page_text):
            detected_type = "abha"
            card_label = "ABHA Card (Health Account)"

        raw_boxes: List[Dict[str, float]] = []

        # 2. Dual-Pass OpenCV Contour Vision Analysis
        if img_bgr is not None:
            img_h, img_w = img_bgr.shape[:2]
            tot_area = img_w * img_h
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

            # Pass A: Canny edge detection (thin lines, printed borders, dashed cut lines)
            edges = cv2.Canny(blurred, 30, 120)
            dilated_edges = cv2.dilate(edges, kernel, iterations=1)
            cnts_canny, _ = cv2.findContours(dilated_edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            # Pass B: Otsu binary thresholding with inversion (colored card bodies on white paper)
            _, thresh_otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            dilated_otsu = cv2.dilate(thresh_otsu, kernel, iterations=1)
            cnts_otsu, _ = cv2.findContours(dilated_otsu, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            all_contours = list(cnts_canny) + list(cnts_otsu)

            for c in all_contours:
                x, y, w, h = cv2.boundingRect(c)
                aspect = w / h if h > 0 else 0
                area = w * h
                area_ratio = area / tot_area

                # Skip outer page border or tiny text/barcode noise
                if area_ratio > 0.85 or area_ratio < 0.015:
                    continue

                # A. Individual CR80 Card (aspect ~ 1.58)
                if 1.25 <= aspect <= 1.95 and 0.02 <= area_ratio <= 0.65:
                    raw_boxes.append({
                        "x": max(0.0, min(1.0, x / img_w)),
                        "y": max(0.0, min(1.0, y / img_h)),
                        "w": max(0.05, min(1.0, w / img_w)),
                        "h": max(0.05, min(1.0, h / img_h)),
                        "aspect": aspect
                    })
                # B. Stacked Dual Card (aspect ~ 0.79, e.g. official e-Shram, Ration)
                elif 0.65 <= aspect <= 0.95 and 0.05 <= area_ratio <= 0.65:
                    half_h = h // 2
                    raw_boxes.append({
                        "x": max(0.0, min(1.0, x / img_w)),
                        "y": max(0.0, min(1.0, y / img_h)),
                        "w": max(0.05, min(1.0, w / img_w)),
                        "h": max(0.05, min(1.0, half_h / img_h)),
                        "aspect": w / half_h
                    })
                    raw_boxes.append({
                        "x": max(0.0, min(1.0, x / img_w)),
                        "y": max(0.0, min(1.0, (y + half_h) / img_h)),
                        "w": max(0.05, min(1.0, w / img_w)),
                        "h": max(0.05, min(1.0, half_h / img_h)),
                        "aspect": w / half_h
                    })
                # C. Side-by-Side Dual Card (aspect ~ 3.0, e.g. e-PAN, Voter)
                elif 2.60 <= aspect <= 3.50 and 0.05 <= area_ratio <= 0.65:
                    half_w = w // 2
                    raw_boxes.append({
                        "x": max(0.0, min(1.0, x / img_w)),
                        "y": max(0.0, min(1.0, y / img_h)),
                        "w": max(0.05, min(1.0, half_w / img_w)),
                        "h": max(0.05, min(1.0, h / img_h)),
                        "aspect": half_w / h
                    })
                    raw_boxes.append({
                        "x": max(0.0, min(1.0, (x + half_w) / img_w)),
                        "y": max(0.0, min(1.0, y / img_h)),
                        "w": max(0.05, min(1.0, half_w / img_w)),
                        "h": max(0.05, min(1.0, h / img_h)),
                        "aspect": half_w / h
                    })

        # 3. If OpenCV found fewer than 2 boxes, inspect embedded images & vector strokes
        if len(raw_boxes) < 2 and page is not None and pw > 0 and ph > 0:
            for img_info in page.get_images():
                xref = img_info[0]
                for r in page.get_image_rects(xref):
                    rw, rh = r.width, r.height
                    asp = rw / rh if rh > 0 else 0
                    if 2.60 <= asp <= 3.50 and 200 <= rw <= 550:
                        half_w = rw / 2
                        raw_boxes.append({
                            "x": max(0.0, min(1.0, r.x0 / pw)),
                            "y": max(0.0, min(1.0, r.y0 / ph)),
                            "w": max(0.05, min(1.0, half_w / pw)),
                            "h": max(0.05, min(1.0, rh / ph)),
                            "aspect": half_w / rh
                        })
                        raw_boxes.append({
                            "x": max(0.0, min(1.0, (r.x0 + half_w) / pw)),
                            "y": max(0.0, min(1.0, r.y0 / ph)),
                            "w": max(0.05, min(1.0, half_w / pw)),
                            "h": max(0.05, min(1.0, rh / ph)),
                            "aspect": half_w / rh
                        })
                    elif 0.65 <= asp <= 0.95 and 200 <= rw <= 550:
                        half_h = rh / 2
                        raw_boxes.append({
                            "x": max(0.0, min(1.0, r.x0 / pw)),
                            "y": max(0.0, min(1.0, r.y0 / ph)),
                            "w": max(0.05, min(1.0, rw / pw)),
                            "h": max(0.05, min(1.0, half_h / ph)),
                            "aspect": rw / half_h
                        })
                        raw_boxes.append({
                            "x": max(0.0, min(1.0, r.x0 / pw)),
                            "y": max(0.0, min(1.0, (r.y0 + half_h) / ph)),
                            "w": max(0.05, min(1.0, rw / pw)),
                            "h": max(0.05, min(1.0, half_h / ph)),
                            "aspect": rw / half_h
                        })
                    elif 1.35 <= asp <= 1.85 and (150 <= rw <= 600 or 0.35 <= (rw / pw) <= 0.99):
                        raw_boxes.append({
                            "x": max(0.0, min(1.0, r.x0 / pw)),
                            "y": max(0.0, min(1.0, r.y0 / ph)),
                            "w": max(0.05, min(1.0, rw / pw)),
                            "h": max(0.05, min(1.0, rh / ph)),
                            "aspect": asp
                        })

            for item in page.get_drawings():
                r = item.get("rect")
                if not r: continue
                rw, rh = r.width, r.height
                if rw <= 0 or rh <= 0: continue
                asp = rw / rh if rh > 0 else 0
                if 1.35 <= asp <= 1.85 and 180 <= rw <= 340 and 110 <= rh <= 220:
                    raw_boxes.append({
                        "x": max(0.0, min(1.0, r.x0 / pw)),
                        "y": max(0.0, min(1.0, r.y0 / ph)),
                        "w": max(0.05, min(1.0, rw / pw)),
                        "h": max(0.05, min(1.0, rh / ph)),
                        "aspect": asp
                    })

        # 4. Smart Overlap & Non-Maximum Suppression (NMS) Filtering
        # Filters duplicate nested boxes and inner text contours
        sorted_raw = sorted(raw_boxes, key=lambda b: abs(b["aspect"] - CR80_ASPECT_RATIO))
        clean_boxes: List[Dict[str, float]] = []
        for b in sorted_raw:
            has_overlap = False
            for cb in clean_boxes:
                if _box_overlap(b, cb) > 0.20 or (abs(cb["x"] - b["x"]) < 0.06 and abs(cb["y"] - b["y"]) < 0.06):
                    has_overlap = True
                    break
            if not has_overlap:
                clean_boxes.append(b)

        # Sort: Top-to-bottom, Left-to-right
        clean_boxes.sort(key=lambda b: (round(b["y"] * 10) / 10, b["x"]))

        # 5. Infer card type from geometry if not already identified from text
        if not detected_type and len(clean_boxes) >= 2:
            b0, b1 = clean_boxes[0], clean_boxes[1]
            if abs(b0["x"] - b1["x"]) < 0.05 and b0["y"] < 0.22 and b1["y"] < 0.45:
                detected_type = "eshram"
                card_label = "e-Shram Card (Front & Back)"
            elif abs(b0["x"] - b1["x"]) < 0.08 and b0["w"] > 0.80 and b0["y"] < 0.15 and b1["y"] >= 0.45:
                detected_type = "abha"
                card_label = "ABHA Card (Front & Back)"
            elif abs(b0["y"] - b1["y"]) < 0.08 and b0["y"] >= 0.70:
                detected_type = "pan_dual"
                card_label = "e-PAN Card (Front & Back)"
            elif abs(b0["y"] - b1["y"]) < 0.08 and 0.45 <= b0["y"] < 0.70:
                detected_type = "voter"
                card_label = "Voter ID / Dual Card"
            elif abs(b0["y"] - b1["y"]) < 0.08 and 0.05 <= b0["y"] <= 0.25:
                detected_type = "voter"
                card_label = "Voter ID (e-EPIC)"
            elif abs(b0["y"] - b1["y"]) < 0.08 and 0.25 <= b0["y"] <= 0.45:
                detected_type = "dl"
                card_label = "Driving Licence (DL)"

        # 6. Resolve Front & Back using Universal Geometric Pair Finder
        front_box = None
        back_box = None
        is_detected = False

        # First, test if specific presets or known types have targeted candidate subsets
        if detected_type == "pan_dual":
            pan_candidates = [b for b in clean_boxes if b["y"] >= 0.65 and b["w"] < 0.60]
            if len(pan_candidates) >= 2:
                pan_candidates.sort(key=lambda b: b["x"])
                front_box = pan_candidates[0]
                back_box = pan_candidates[1]
                is_detected = True

        # Universal Pair Discovery across all clean candidate boxes
        if not is_detected:
            pair = find_best_card_pair(clean_boxes)
            if pair is not None:
                front_box, back_box = pair
                is_detected = True
                if card_label == "Auto-Detected Card":
                    card_label = "Smart PVC Card (Dual Front & Back)"

        # Single Card Discovery (if document contains only 1 front card)
        if not is_detected:
            single_candidates = [b for b in clean_boxes if 1.25 <= b["aspect"] <= 1.95]
            if single_candidates:
                single_candidates.sort(key=lambda b: abs(b["aspect"] - CR80_ASPECT_RATIO))
                front_box = single_candidates[0]
                back_box = None
                is_detected = True
                if card_label == "Auto-Detected Card":
                    card_label = "Smart PVC Card (Single Front)"
            elif detected_type and detected_type in PRESETS:
                p = PRESETS[detected_type]
                front_box = p["front"]
                back_box = p.get("back")
                is_detected = True
            else:
                p = PRESETS["voter"]
                front_box = p["front"]
                back_box = p.get("back")
                is_detected = False

        return {
            "detected": is_detected,
            "card_type": detected_type or "custom",
            "card_label": card_label,
            "front_box": front_box,
            "back_box": back_box,
            "is_dual": (back_box is not None),
            "boxes": clean_boxes
        }

    finally:
        if doc_to_close:
            try: doc_to_close.close()
            except: pass


def detect_card_boxes_in_page(page: pymupdf.Page) -> List[Dict[str, float]]:
    """
    Detects card boundary boxes on a PDF page using smart_detect_card_layout.
    Returns list of normalized boxes: [{"x": float, "y": float, "w": float, "h": float}, ...]
    """
    res = smart_detect_card_layout(page)
    return res.get("boxes", [])


def generate_page_preview(
    pdf_path: str, 
    page_number: int = 0, 
    password: Optional[str] = None, 
    target_width: int = 900
) -> Tuple[Image.Image, int, int]:
    """
    Renders a page of the PDF into a clean RGB PIL Image for web display,
    returning (image, original_width_pt, original_height_pt).
    """
    doc = open_pdf_document(pdf_path, password)
    try:
        if page_number < 0 or page_number >= len(doc):
            page_number = 0
        page = doc[page_number]
        
        orig_w = page.rect.width
        orig_h = page.rect.height
        
        # Calculate scale factor for target_width
        scale = target_width / orig_w if orig_w > 0 else 1.5
        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img, int(orig_w), int(orig_h)
    finally:
        try: doc.close()
        except: pass


def crop_card_box(
    pdf_path: str,
    box: Dict[str, float],
    page_number: int = 0,
    password: Optional[str] = None,
    output_dpi: int = 300,
    edge_to_edge: bool = True
) -> Image.Image:
    """
    Crops a specific normalized box [x, y, w, h] from a PDF page or image file at full 300 DPI resolution.
    Resizes/normalizes output to exact CR80 1016x638 px.
    """
    ext = os.path.splitext(pdf_path)[1].lower()
    if ext in [".png", ".jpg", ".jpeg", ".webp"]:
        # Handle direct image crop
        with Image.open(pdf_path) as full_img:
            pw, ph = full_img.size
            x0 = max(0, int(box["x"] * pw))
            y0 = max(0, int(box["y"] * ph))
            x1 = min(pw, int((box["x"] + box["w"]) * pw))
            y1 = min(ph, int((box["y"] + box["h"]) * ph))
            card_img = full_img.crop((x0, y0, x1, y1)).convert("RGB")
            if card_img.size != (CARD_WIDTH, CARD_HEIGHT):
                card_img = card_img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
            return card_img

    doc = open_pdf_document(pdf_path, password)
    try:
        if page_number < 0 or page_number >= len(doc):
            page_number = 0
        page = doc[page_number]
        
        pw = page.rect.width
        ph = page.rect.height
        
        # Convert normalized (0.0 to 1.0) back to PDF points
        x0 = max(0.0, box["x"] * pw)
        y0 = max(0.0, box["y"] * ph)
        x1 = min(pw, (box["x"] + box["w"]) * pw)
        y1 = min(ph, (box["y"] + box["h"]) * ph)
        
        clip_rect = pymupdf.Rect(x0, y0, x1, y1)
        
        # Render direct high-res pixmap using PyMuPDF clip
        scale = output_dpi / 72.0
        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, clip=clip_rect, alpha=False)
        
        card_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    finally:
        try: doc.close()
        except: pass
    
    # Normalize to exact CR80 (1016 x 638 px)
    if card_img.size != (CARD_WIDTH, CARD_HEIGHT):
        card_img = card_img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
        
    return card_img


def process_crop_and_print(
    pdf_path: str,
    front_box: Dict[str, float],
    back_box: Optional[Dict[str, float]],
    output_dir: str,
    page_number: int = 0,
    password: Optional[str] = None,
    duplex_mode: bool = False
) -> Dict[str, Any]:
    """
    Performs high-res crop for Front (and Back if present),
    saves them to output_dir as front.png and back.png,
    and generates the ready-to-print A4 PDF.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Crop Front Card
    front_img = crop_card_box(pdf_path, front_box, page_number=page_number, password=password)
    front_path = os.path.join(output_dir, "front.png")
    front_img.save(front_path, "PNG", dpi=(300, 300))
    
    # 2. Crop Back Card if provided
    has_back = False
    back_path = None
    if back_box and back_box.get("w", 0) > 0.02 and back_box.get("h", 0) > 0.02:
        back_img = crop_card_box(pdf_path, back_box, page_number=page_number, password=password)
        back_path = os.path.join(output_dir, "back.png")
        back_img.save(back_path, "PNG", dpi=(300, 300))
        has_back = True
    else:
        # Create an empty/white back card for single card printing
        dummy_back = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), "white")
        back_path = os.path.join(output_dir, "back_placeholder.png")
        dummy_back.save(back_path, "PNG", dpi=(300, 300))
        
    # 3. Create A4 Ready-to-Print PDF
    pdf_output_path = os.path.join(output_dir, "a4_print.pdf")
    
    # In side-by-side mode: Front on left, Back on right
    # If no back card, pass None or the placeholder
    a4_result = create_a4_print_pdf(
        front_images=[front_path],
        back_images=[back_path if has_back else back_path],
        output_path=pdf_output_path,
        mirror_columns_for_duplex=duplex_mode,
        side_by_side=(not duplex_mode)
    )
    
    return {
        "success": True,
        "front_path": front_path,
        "back_path": back_path if has_back else None,
        "has_back": has_back,
        "pdf_path": pdf_output_path,
        "card_dimensions": f"{CARD_WIDTH}x{CARD_HEIGHT}",
        "dpi": 300
    }
