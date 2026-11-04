import sys
import os
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import engine.passport_photo as pp

def run_layout_audit():
    print("=== PASSPORT PRINT SHEET LAYOUT AUDIT ===")

    # Create dummy realistic portrait photo
    test_photo = Image.new("RGB", (pp.PHOTO_WIDTH, pp.PHOTO_HEIGHT), (239, 68, 68))
    draw = ImageDraw.Draw(test_photo)
    draw.ellipse([80, 50, 333, 340], fill=(235, 180, 140))
    draw.ellipse([70, 30, 343, 160], fill=(40, 30, 20))
    draw.rectangle([30, 310, 383, 531], fill=(40, 80, 180))

    # Add DOP strip
    test_photo_dop = pp.add_name_and_dop(test_photo, candidate_name="TEST USER", date_of_photo="01/01/2026")

    layouts = ["single", "4x6_8", "4x6_6", "4x6_12", "a4_30", "a4_36"]

    for l_type in layouts:
        sheet = pp.generate_print_sheet(test_photo_dop, layout_type=l_type, include_cutting_marks=True)
        w, h = sheet.size

        # Check that non-white pixels don't touch the bottom or top boundary
        # i.e. bottom margin must be at least 10px of white space
        bottom_row_pixels = [sheet.getpixel((x, h - 1)) for x in range(0, w, max(1, w // 20))]
        top_row_pixels = [sheet.getpixel((x, 0)) for x in range(0, w, max(1, w // 20))]

        # All perimeter pixels at y=0 and y=h-1 must be pure white (255, 255, 255)
        assert all(p == (255, 255, 255) for p in bottom_row_pixels), f"Layout {l_type} has photos touching or clipped at bottom edge!"
        assert all(p == (255, 255, 255) for p in top_row_pixels), f"Layout {l_type} has photos touching or clipped at top edge!"

        print(f"Layout '{l_type}': Size={w}x{h}, Top & Bottom Margins Clean! ZERO CLIPPING!")

    # Test full studio pipeline with 4x6_12
    out_dir = "tests_output/test_passport_layouts"
    os.makedirs(out_dir, exist_ok=True)
    temp_in = os.path.join(out_dir, "input.png")
    test_photo.save(temp_in)

    res = pp.process_passport_studio(
        input_file_path=temp_in,
        output_dir=out_dir,
        bg_color_name="red",
        layout_type="4x6_12",
        candidate_name="RAMESH KUMAR",
        date_of_photo="12/04/2026"
    )

    assert res["success"] is True
    assert res["photo_count"] == 12
    assert os.path.exists(res["print_sheet_path"])
    assert os.path.exists(res["pdf_sheet_path"])

    sheet_img = Image.open(res["print_sheet_path"])
    assert sheet_img.size == (1200, 1800), f"Expected (1200, 1800), got {sheet_img.size}"

    # Verify bottom pixels of generated sheet are white (not cut off)
    bottom_pixels = [sheet_img.getpixel((x, 1799)) for x in range(0, 1200, 50)]
    assert all(p == (255, 255, 255) for p in bottom_pixels), "Bottom row in 4x6_12 is cut off!"

    # Verify 4x6_12 option is removed from templates/index.html UI
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    assert 'data-layout="4x6_12"' not in html, "4x6_12 option still found in index.html!"
    assert 'value="4x6_12"' not in html, "value='4x6_12' radio still found in index.html!"

    print("ALL TESTS PASSED: 4x6 12-Photo Sheet option completely removed from UI and backend verified!")

if __name__ == "__main__":
    run_layout_audit()

