import os
from engine.card_renderer import render_card

languages = ["Hindi", "Gujarati", "Marathi", "Bengali", "Tamil", "Telugu", "Kannada", "Malayalam", "Punjabi", "Odia", "Urdu"]

for lang in languages:
    mapped_data = {
        "person": {"name": "Test User", "name_local": "ટેસ્ટ", "dob": "01-01-1990", "gender": "M"},
        "address": {
            "local": "સંજય, પ્લ-76, જગદંબા નગર, ડિનડોળી, નવાગામ, સુરત સીટી, ઉધના, સુરત, ગુજરાત - 394210",
            "full": "C/O sanjay, pl-76, Dindoli, navagam, Udhna, jagdamba nagar, Surat, Gujarat, 394210"
        },
        "identity": {"aadhaar_number": "5845 5708 9924", "enrolment_number": "9150 4978 9908 8433"},
        "contact": {},
        "photo": {"available": False},
        "qr": {"available": False},
        "language": {"name": lang, "code": lang.lower()[:2]}
    }
    output_dir = os.path.join("tests_output", f"lang_{lang}")
    render_card(mapped_data, {}, output_dir)

print("Rendered all language tests!")
