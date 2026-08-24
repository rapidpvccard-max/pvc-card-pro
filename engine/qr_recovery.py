import io
import base64
import re
from typing import Optional
from PIL import Image

# We import the exact same candidate extraction logic from the powerhouse engine
# to guarantee we look at the exact same image list that the engine did.
from engine.aadhaar_extractor import extract_candidate_qr_images

def recover_qr_from_pdf(pdf_path: str, password: Optional[str], engine_trace: list[str]) -> Optional[str]:
    """
    Recovers the original QR image byte stream from the PDF without modifying or decoding it.
    It identifies the correct image by matching the index chosen by the extraction engine's trace.
    Returns the image as a base64 encoded PNG string.
    """
    chosen_index = -1
    
    # 1. Identify which candidate the engine successfully used
    for line in engine_trace:
        match = re.search(r"QR candidate #(\d+) produced a usable name", line)
        if match:
            chosen_index = int(match.group(1))
            break
            
    if chosen_index == -1:
        # The engine didn't successfully use any QR candidate (fallback or failure)
        return None
        
    # 2. Extract the exact same candidates
    try:
        candidates = extract_candidate_qr_images(pdf_path, password=password, trace=[])
    except Exception:
        return None
        
    if chosen_index >= len(candidates):
        return None
        
    qr_bytes = candidates[chosen_index]
    
    # 3. Convert original image bytes to PNG base64 for browser compatibility
    try:
        pil_img = Image.open(io.BytesIO(qr_bytes)).convert("RGB")
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        return base64.b64encode(png_bytes).decode("ascii")
    except Exception:
        return None
