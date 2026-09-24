import cv2
import numpy as np
import pymupdf
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

doc = pymupdf.open('C:/Users/NANO/Downloads/SAGAR PATIL PAN CARD.pdf')
page = doc[0]
pix = page.get_pixmap(dpi=150)
img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
blurred = cv2.GaussianBlur(gray, (5, 5), 0)
edges = cv2.Canny(blurred, 30, 120)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
dilated = cv2.dilate(edges, kernel, iterations=1)
contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

img_h, img_w = img.shape[:2]
tot_area = img_w * img_h
print(f"Pixmap size: {img_w} x {img_h}, total area: {tot_area}")
print(f"Total contours: {len(contours)}")

for i, c in enumerate(contours):
    x, y, w, h = cv2.boundingRect(c)
    aspect = w / h if h > 0 else 0
    area = w * h
    area_ratio = area / tot_area
    if area_ratio > 0.01:
        print(f"Contour {i}: x={x}, y={y}, w={w}, h={h}, aspect={aspect:.2f}, area_ratio={area_ratio:.3f}, norm: x={x/img_w:.3f}, y={y/img_h:.3f}, w={w/img_w:.3f}, h={h/img_h:.3f}")
