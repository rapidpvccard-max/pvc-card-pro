import os
from engine.card_renderer import render_card

mapped_data = {
    "person": {
        "name": "Thakur Anilbhai Daturam",
        "name_local": "ઠાકુર અનિલભાઈ દતુરામ",
        "dob": "01-01-1985",
        "gender": "F"
    },
    "address": {
        "local": "W/O: ઠાકુર અનિલભાઈ દતુરામ, બ્લૉક નં. એ/24, રૂમ નં. 284, ઍસ.આર.પી. ગ્રૂપ-8, ગોંડલ, ગોંડલ, રાજકોટ, ગુજરાત - 360311",
        "full": "W/O: Thakur Anilbhai Daturam, Block No. A/24, S.R.P. Group-8, Gondal, Gondal, Room No. 284, Rajkot, Gujarat, 360311"
    },
    "identity": {
        "aadhaar_number": "6306 1714 9411",
        "enrolment_number": "9108 7688 8768 8269"
    },
    "contact": {},
    "photo": {"available": False},
    "qr": {"available": False},
    "language": {"name": "Gujarati", "code": "gu"}
}

engine_data = {}
output_dir = os.path.join("tests_output", "user_thakur")
front_path, back_path = render_card(mapped_data, engine_data, output_dir)
print(f"Generated back: {back_path}")
