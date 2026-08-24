import os
from engine.card_renderer import render_card

mapped_data = {
    "person": {
        "name": "O Bhundaram Chowdary",
        "name_local": "ఓ బుందారం చౌదరి",
        "dob": "01-07-1975",
        "gender": "M"
    },
    "contact": {
        "mobile": "9908328436"
    },
    "address": {
        "local": "చిరునామా...",
        "full": "Address..."
    },
    "identity": {
        "aadhaar_number": "5048 7604 4734",
        "enrolment_number": "9153 6180 6175 7361"
    },
    "photo": {"available": False},
    "qr": {"available": False},
    "language": {"name": "Telugu", "code": "te"}
}

engine_data = {}
output_dir = os.path.join("tests_output", "user_notice_test")
front_path, back_path = render_card(mapped_data, engine_data, output_dir)
print(f"Generated front: {front_path}")
