import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from engine.card_renderer import render_card

# Mock Data
def run_test(name, person_data, address_data, identity_data):
    print(f"Running test for: {name}")
    mapped_data = {
        "person": person_data,
        "address": address_data,
        "identity": identity_data,
        "contact": person_data.get("contact", {}),
        "photo": {"available": False},
        "qr": {"available": False},
        "language": {"name": name, "code": name.lower()}
    }
    
    # Empty engine data (missing photo and QR raw bytes)
    engine_data = {}
    
    output_dir = os.path.join("tests_output", name)
    front_path, back_path = render_card(mapped_data, engine_data, output_dir)
    print(f"Generated: {front_path}")
    print(f"Generated: {back_path}")

if __name__ == "__main__":
    # Hindi
    run_test("Hindi", 
             {"name": "Rahul Sharma", "name_local": "राहुल शर्मा", "dob": "01-01-1990", "gender": "M", "contact": {"mobile": "9876543210"}},
             {"full": "C/O Ramesh Sharma, 12, New Delhi", "local": "सी/ओ रमेश शर्मा, १२, नई दिल्ली"},
             {"aadhaar_number": "XXXX XXXX 1234", "enrolment_number": "9145461292669694"})

    # Gujarati
    run_test("Gujarati", 
             {"name": "Patel Ravi", "name_local": "પટેલ રવિ", "dob": "15-08-1985", "gender": "M"},
             {"full": "S/O Naval, A-6, Beside Shivalik Square ,Near Rami Park, dindoli, Surat City, Udhna, Govardhan Nagar -2, Surat, Gujarat, 394210", "local": "સરનામું : S/O નવલ, એ-6, ગોવર્ધન નગર -2, શીવાલિક સ્કવેર બાજુમાં,રામી પાર્ક પાસે, ડિંડોલી, સુરત સીટી, ઉધના, સુરત, ગુજરાત - 394210"},
             {"aadhaar_number": "XXXX XXXX 5678", "enrolment_number": ""})
             
    # Telugu
    run_test("Telugu", 
             {"name": "Rao Venkat", "name_local": "రావు వెంకట్", "dob": "10-10-1980", "gender": "M"},
             {"full": "C/O Krishna Rao, Plot 42, Hyderabad", "local": "సి/ఓ కృష్ణ రావు, ప్లాట్ 42, హైదరాబాద్"},
             {"aadhaar_number": "XXXX XXXX 9012", "enrolment_number": ""})

    # User exact case
    run_test("UserCase", 
             {"name": "Naval Patel", "name_local": "નવલ પટેલ", "dob": "15-08-1985", "gender": "M"},
             {"full": "S/O Naval, A-6, Beside Shivalik Square ,Near Rami Park, dindoli, Surat City, Udhna, Govardhan Nagar -2, Surat, Gujarat, 394210", 
              "local": "સરનામું : S/O નવલ, એ-6, ગોવર્ધન નગર -2, શીવાલિક સ્કવેર બાજુમાં,રામી પાર્ક પાસે, ડિંડોલી, સુરત સીટી, ઉધના, સુરત, ગુજરાત - 394210"},
             {"aadhaar_number": "7065 0525 5602", "enrolment_number": "9119 8982 3145 4816"})
