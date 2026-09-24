import cv2
import numpy as np
import pymupdf
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def universal_detect(pdf_path):
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    pw, ph = page.rect.width, page.rect.height
    pix = page.get_pixmap(dpi=150)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
    img_h, img_w = img.shape[:2]
    tot_area = img_w * img_h

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 120)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=1)
    
    contours, hierarchy = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    candidates = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        aspect = w / h if h > 0 else 0
        area = w * h
        area_ratio = area / tot_area
        
        # Skip whole page border
        if area_ratio > 0.75 or area_ratio < 0.015:
            continue
            
        # Single CR80 Card (~1.58)
        if 1.35 <= aspect <= 1.85 and 0.02 <= area_ratio <= 0.45:
            candidates.append({'x': x/img_w, 'y': y/img_h, 'w': w/img_w, 'h': h/img_h, 'aspect': aspect, 'type': 'single'})
        # Stacked Dual Card (~0.79)
        elif 0.65 <= aspect <= 0.95 and 0.05 <= area_ratio <= 0.60:
            half_h = h // 2
            candidates.append({'x': x/img_w, 'y': y/img_h, 'w': w/img_w, 'h': half_h/img_h, 'aspect': w/half_h, 'type': 'stacked_top'})
            candidates.append({'x': x/img_w, 'y': (y+half_h)/img_h, 'w': w/img_w, 'h': half_h/img_h, 'aspect': w/half_h, 'type': 'stacked_bottom'})
        # Side-by-Side Dual Card (~3.0)
        elif 2.60 <= aspect <= 3.50 and 0.05 <= area_ratio <= 0.60:
            half_w = w // 2
            candidates.append({'x': x/img_w, 'y': y/img_h, 'w': half_w/img_w, 'h': h/img_h, 'aspect': half_w/h, 'type': 'side_left'})
            candidates.append({'x': (x+half_w)/img_w, 'y': y/img_h, 'w': half_w/img_w, 'h': h/img_h, 'aspect': half_w/h, 'type': 'side_right'})

    # If OpenCV didn't find cards or only found 1, check embedded images on page
    if len(candidates) < 2:
        for img_info in page.get_images():
            xref = img_info[0]
            for r in page.get_image_rects(xref):
                asp = r.width / r.height if r.height > 0 else 0
                if 2.60 <= asp <= 3.50 and 200 <= r.width <= 550:
                    half_w = r.width / 2
                    candidates.append({'x': r.x0 / pw, 'y': r.y0 / ph, 'w': half_w / pw, 'h': r.height / ph, 'aspect': half_w / r.height, 'type': 'img_side_left'})
                    candidates.append({'x': (r.x0 + half_w) / pw, 'y': r.y0 / ph, 'w': half_w / pw, 'h': r.height / ph, 'aspect': half_w / r.height, 'type': 'img_side_right'})
                elif 0.65 <= asp <= 0.95 and 200 <= r.width <= 550:
                    half_h = r.height / 2
                    candidates.append({'x': r.x0 / pw, 'y': r.y0 / ph, 'w': r.width / pw, 'h': half_h / ph, 'aspect': r.width / half_h, 'type': 'img_stacked_top'})
                    candidates.append({'x': r.x0 / pw, 'y': (r.y0 + half_h) / ph, 'w': r.width / pw, 'h': half_h / ph, 'aspect': r.width / half_h, 'type': 'img_stacked_bottom'})
                elif 1.35 <= asp <= 1.85 and 150 <= r.width <= 400:
                    candidates.append({'x': r.x0 / pw, 'y': r.y0 / ph, 'w': r.width / pw, 'h': r.height / ph, 'aspect': asp, 'type': 'img_single'})

    # Deduplicate overlapping candidates
    clean = []
    for c in candidates:
        dup = False
        for k in clean:
            if abs(k['x'] - c['x']) < 0.04 and abs(k['y'] - c['y']) < 0.04:
                dup = True
                break
        if not dup:
            clean.append(c)

    # Sort
    clean.sort(key=lambda b: (round(b['y'] * 10) / 10, b['x']))
    print(f"\nFile: {pdf_path}")
    print(f"  Found {len(clean)} card shapes:")
    for i, b in enumerate(clean):
        print(f"    [{i}] x={b['x']:.4f}, y={b['y']:.4f}, w={b['w']:.4f}, h={b['h']:.4f}, aspect={b['aspect']:.2f}, type={b['type']}")

files = [
    'C:/Users/NANO/Downloads/SAGAR PATIL PAN CARD.pdf',
    'C:/Users/NANO/Downloads/uan-card.pdf',
    'C:/Users/NANO/Downloads/881134207309171_signed_unlocked.pdf'
]
for f in files:
    universal_detect(f)
