import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.card_cropper import (
    PRESETS, 
    generate_page_preview, 
    detect_card_boxes_in_page, 
    process_crop_and_print,
    open_pdf_document
)

def test_cropper():
    test_pdf = os.path.join("tests", "test_ayushman.pdf")
    if not os.path.exists(test_pdf):
        print("test_ayushman.pdf not found, skipping file test.")
        return
        
    print(f"Testing Card Cropper Engine with {test_pdf}...")
    doc = open_pdf_document(test_pdf)
    print(f"  Pages in doc: {len(doc)}")
    
    # Test preview generation
    preview_img, orig_w, orig_h = generate_page_preview(test_pdf, page_number=0)
    print(f"  Preview generated: size={preview_img.size}, original={orig_w}x{orig_h} pt")
    assert preview_img.size[0] > 0 and preview_img.size[1] > 0
    
    # Test auto detection
    detected = detect_card_boxes_in_page(doc[0])
    print(f"  Detected card boxes: {len(detected)}")
    
    # Test process_crop_and_print with voter preset
    preset = PRESETS["voter"]
    output_dir = os.path.join("tests_output", "test_cropper")
    os.makedirs(output_dir, exist_ok=True)
    
    res = process_crop_and_print(
        pdf_path=test_pdf,
        front_box=preset["front"],
        back_box=preset["back"],
        output_dir=output_dir,
        page_number=0
    )
    
    print("  Crop & Print result:", res)
    assert os.path.exists(res["front_path"]), "Front card PNG not found"
    assert os.path.exists(res["pdf_path"]), "A4 print PDF not found"
    print("All Card Cropper engine tests PASSED!")

if __name__ == "__main__":
    test_cropper()
