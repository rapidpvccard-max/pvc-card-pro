import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.card_renderer import render_card
from engine.a4_print import create_a4_print_pdf
from PIL import Image

def test_pipeline():
    out_dir = os.path.abspath("tests_output/test_colour_pipeline")
    os.makedirs(out_dir, exist_ok=True)

    test_data = {
        "person": {
            "name": "Rajesh Sharma",
            "name_local": "राजेश शर्मा",
            "dob": "15-08-1985",
            "gender": "M"
        },
        "address": {
            "local": "मकान नं. 45, गांधी नगर, स्टेशन रोड, जयपुर, राजस्थान - 302015",
            "full_html": "House No. 45, Gandhi Nagar, Station Road, Jaipur, Rajasthan - 302015",
            "full": "House No. 45, Gandhi Nagar, Station Road, Jaipur, Rajasthan - 302015"
        },
        "identity": {
            "aadhaar_number": "9876 5432 1098",
            "enrolment_number": "1234 5678 9012 3456"
        },
        "contact": {
            "mobile": "9829012345"
        },
        "photo": {"available": False},
        "qr": {"available": False},
        "language": {"name": "Hindi", "code": "hi"}
    }

    print("\n--- 1. Testing Default (Standard White) Template ---")
    f_def, b_def = render_card(test_data, {}, os.path.join(out_dir, "default"), document_type="aadhaar", template_style="default")
    assert os.path.exists(f_def) and os.path.getsize(f_def) > 10000, "Default front render failed"
    assert os.path.exists(b_def) and os.path.getsize(b_def) > 10000, "Default back render failed"
    print(f"Default card rendered successfully: {f_def} ({os.path.getsize(f_def)} bytes)")

    print("\n--- 2. Testing Colourful Template (via template_style='color') ---")
    f_col, b_col = render_card(test_data, {}, os.path.join(out_dir, "color"), document_type="aadhaar", template_style="color")
    assert os.path.exists(f_col) and os.path.getsize(f_col) > 10000, "Color front render failed"
    assert os.path.exists(b_col) and os.path.getsize(b_col) > 10000, "Color back render failed"
    print(f"Color card rendered successfully: {f_col} ({os.path.getsize(f_col)} bytes)")

    print("\n--- 3. Testing Colourful Template (via document_type='aadhaar_color') ---")
    f_col2, b_col2 = render_card(test_data, {}, os.path.join(out_dir, "color_doc"), document_type="aadhaar_color")
    assert os.path.exists(f_col2) and os.path.getsize(f_col2) > 10000, "Color doc front render failed"
    assert os.path.exists(b_col2) and os.path.getsize(b_col2) > 10000, "Color doc back render failed"
    print(f"Color doc card rendered successfully: {f_col2} ({os.path.getsize(f_col2)} bytes)")

    print("\n--- 4. Verifying Image Dimensions and Specs ---")
    im_f = Image.open(f_col)
    im_b = Image.open(b_col)
    assert im_f.size == (1016, 638), f"Expected (1016, 638), got {im_f.size}"
    assert im_b.size == (1016, 638), f"Expected (1016, 638), got {im_b.size}"
    print(f"Card dimensions verified: {im_f.size} (CR80 Standard)")

    print("\n--- 5. Testing Duplex A4 Print PDF Generation ---")
    pdf_path = os.path.join(out_dir, "color_a4_print.pdf")
    create_a4_print_pdf([f_col], [b_col], pdf_path, False)
    assert os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 50000, "A4 PDF generation failed"
    print(f"A4 Print PDF created successfully: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")

    print("\n--- 6. Multilingual Render Test on Colour Template ---")
    for lang, name_loc, addr_loc in [
        ("Gujarati", "રાજેશ શર્મા", "ગાંધી નગર, સ્ટેશન રોડ, અમદાવાદ, ગુજરાત - 380001"),
        ("Marathi", "राजेश शर्मा", "गांधी नगर, स्टेशन रोड, पुणे, महाराष्ट्र - 411001"),
        ("Bengali", "রাজেশ শর্মা", "গান্ধী নগর, স্টেশন রোড, কলকাতা, পশ্চিমবঙ্গ - 700001"),
        ("Tamil", "ராஜேஷ் சர்மா", "காந்தி நகர், ஸ்டேஷன் ரோடு, சென்னை, தமிழ்நாடு - 600001"),
    ]:
        data_copy = dict(test_data)
        data_copy["language"] = {"name": lang, "code": lang.lower()[:2]}
        data_copy["person"] = dict(test_data["person"], name_local=name_loc)
        data_copy["address"] = dict(test_data["address"], local=addr_loc)
        
        lang_dir = os.path.join(out_dir, f"color_{lang}")
        f_l, b_l = render_card(data_copy, {}, lang_dir, template_style="color")
        assert os.path.exists(f_l) and os.path.getsize(f_l) > 10000
        assert os.path.exists(b_l) and os.path.getsize(b_l) > 10000
        print(f"  [OK] Language '{lang}' rendered cleanly.")

    print("\nALL TESTS PASSED WITH 100% SUCCESS!")

if __name__ == "__main__":
    test_pipeline()
