import os
from engine.card_renderer import render_card

mapped_data = {
    "person": {
        "name": "sanjay",
        "name_local": "સંજય",
        "dob": "01-01-1980",
        "gender": "M"
    },
    "address": {
        "local": "સંજય, પ્લ-76, જગદંબા નગર, ડિનડોળી, નવાગામ, સુરત સીટી, ઉધના, સુરત, ગુજરાત - 394210",
        "full": "C/O sanjay, pl-76, Dindoli, navagam, Udhna, jagdamba nagar, Surat, Gujarat, 394210"
    },
    "identity": {
        "aadhaar_number": "5845 5708 9924",
        "enrolment_number": "9150 4978 9908 8433"
    },
    "contact": {},
    "photo": {"available": False},
    "qr": {"available": False},
    "language": {"name": "Gujarati", "code": "gu"}
}

engine_data = {}
output_dir = os.path.join("tests_output", "user_case_exact")
front_path, back_path = render_card(mapped_data, engine_data, output_dir)
print(f"Generated front: {front_path}")
print(f"Generated back: {back_path}")
