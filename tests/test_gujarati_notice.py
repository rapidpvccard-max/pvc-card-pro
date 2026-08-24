import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from engine.card_renderer import render_card

mapped_data = {
    "person": {
        "name": "Ajage Kalpna Harishchndra",
        "name_local": "અજગે કલ્પના હરિશચન્દ્ર",
        "dob": "01-01-1984",
        "gender": "F"
    },
    "contact": {
        "mobile": "9998196992"
    },
    "address": {
        "local": "સરનામું...",
        "full": "Address..."
    },
    "identity": {
        "aadhaar_number": "4586 1698 0520",
        "enrolment_number": "9186 6169 6126 6370"
    },
    "photo": {"available": False},
    "qr": {"available": False},
    "language": {"name": "Gujarati", "code": "gu"}
}

engine_data = {}
output_dir = os.path.join("tests_output", "user_gujarati_notice")
front_path, back_path = render_card(mapped_data, engine_data, output_dir)
print(f"Generated front: {front_path}")
