import os
import sys
import base64
import io
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.card_renderer import render_card

def create_sample_avatar():
    # Create a 200x250 sample portrait image
    img = Image.new("RGB", (200, 250), color="#2563eb")
    d = ImageDraw.Draw(img)
    # Head
    d.ellipse([60, 40, 140, 120], fill="#fde047")
    # Body
    d.rectangle([40, 130, 160, 250], fill="#1e40af")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def run():
    photo_b64 = ""
    user_photo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests_output", "user_photo.png")
    if os.path.exists(user_photo_path):
        with open(user_photo_path, "rb") as f:
            photo_b64 = base64.b64encode(f.read()).decode("utf-8")
    if not photo_b64:
        photo_b64 = create_sample_avatar()
    
    test_data = {
        "person": {
            "name": "Avinash Naval Patil",
            "name_local": "અવિનાશ નવલ પાટીલ",
            "dob": "01/06/1996",
            "gender": "MALE"
        },
        "address": {
            "local": "સરનામું : S/O નવલ, એ-6, ગોવર્ધન નગર -2, સુરત, ગુજરાત - 394210",
            "full_html": "Address: S/O Naval, A-6, Govardhan Nagar -2, Surat, Gujarat - 394210",
            "full": "Address: S/O Naval, A-6, Govardhan Nagar -2, Surat, Gujarat - 394210"
        },
        "identity": {
            "aadhaar_number": "7065 0525 5602",
            "enrolment_number": "9119 8982 3145 4816"
        },
        "contact": {
            "mobile": "7990278793"
        },
        "photo": {
            "available": True,
            "base64": photo_b64
        },
        "qr": {
            "available": False
        },
        "language": {
            "name": "Gujarati",
            "code": "gu"
        },
        "template_style": "color"
    }

    out_dir = os.path.abspath("tests_output/test_ghost_photo")
    os.makedirs(out_dir, exist_ok=True)

    print("Rendering Colour Aadhaar Card with Ghost Photo...")
    f_path, b_path = render_card(test_data, {}, out_dir, document_type="aadhaar", template_style="color")
    print(f"Rendered Front: {f_path}")
    print(f"Rendered Back: {b_path}")

if __name__ == "__main__":
    run()
