import os
from engine.card_renderer import render_card

mapped_data = {
    "person": {
        "name": "Chauhan Kusum",
        "name_local": "ચૌહાણ કુસુમ",
        "dob": "01-01-1974",
        "gender": "F"
    },
    "contact": {
        "mobile": "8080062993"
    },
    "address": {
        "local": "સરનામું...",
        "full": "Address..."
    },
    "identity": {
        "aadhaar_number": "5316 7298 8942",
        "enrolment_number": "9191 3704 7090 8609"
    },
    "photo": {"available": False},
    "qr": {"available": False},
    "language": {"name": "Gujarati", "code": "gu"}
}

engine_data = {}
output_dir = os.path.join("tests_output", "user_kusum")
front_path, back_path = render_card(mapped_data, engine_data, output_dir)
print(f"Generated front: {front_path}")
print(f"Generated back: {back_path}")
