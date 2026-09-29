import pymupdf
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os

pdf_path = os.path.join(os.environ.get("USERPROFILE", "C:/Users/NANO"), "Downloads", "SAGAR PATIL PAN CARD.pdf")
if not os.path.exists(pdf_path):
    print(f"Sample PAN card PDF not found at {pdf_path}, skipping inspection.")
    sys.exit(0)

doc = pymupdf.open(pdf_path)
page = doc[0]
pw, ph = page.rect.width, page.rect.height
print(f"Page size: {pw} x {ph}")

print("\n--- TEXT SEARCH ---")
for word in ['Cut', 'Fold', 'INCOME TAX DEPARTMENT', 'भारत सरकार', 'CXSPP7117G']:
    quads = page.search_for(word)
    print(f"Word '{word}': {quads}")

print("\n--- DRAWINGS ---")
drawings = page.get_drawings()
print(f"Total drawings: {len(drawings)}")
for d in drawings:
    r = d.get('rect')
    if r and r.height > 10:
        print(f"Drawing: {r}, aspect={r.width/r.height:.2f}, y0_norm={r.y0/ph:.3f}, y1_norm={r.y1/ph:.3f}")

print("\n--- IMAGES ---")
images = page.get_images()
print(f"Total images: {len(images)}")
for img in images:
    xref = img[0]
    for r in page.get_image_rects(xref):
        print(f"Image xref {xref}: {r}, aspect={r.width/r.height:.2f}, x0_norm={r.x0/pw:.3f}, y0_norm={r.y0/ph:.3f}, w_norm={r.width/pw:.3f}, h_norm={r.height/ph:.3f}")
