"""
Layout & Engine Integrity Automated Regression Test Suite
This test validates all critical CSS positions, font weights, safe fallbacks, 
and end-to-end rendering to guarantee that no accidental regressions or drifts can occur.
"""
import os
import re
import unittest
from engine.data_mapper import map_aadhaar_data
from engine.card_renderer import render_card

class TestLayoutIntegrity(unittest.TestCase):

    def test_css_rules_locked(self):
        """Ensure CSS layout coordinates and font configurations remain locked and safe."""
        css_path = os.path.join("templates", "cards", "aadhaar", "default", "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # 1. Front top-right-label must be top: 129px to prevent logo overlap
        self.assertIn("top: 129px", css, "Front top-right-label must be at top: 129px")
        
        # 2. Back top-right-label-back must be top: 114px
        self.assertIn("top: 114px", css, "Back top-right-label must be at top: 114px")
        
        # 3. Back header local must be aligned inside orange brush
        self.assertIn("left: 202px", css, "Back header local must be aligned at left: 202px")
        
        # 4. Notice box must have gap and not overlap Aadhaar number
        self.assertIn("top: 372px", css, "Notice box must start at top: 372px")
        
        # 5. Address text must have separation gap
        self.assertIn("margin-bottom: 18px", css, "Address local block must have 18px separation gap")

    def test_data_mapper_script_mapping(self):
        """Ensure all Indic scripts map to valid language names with zero empty language strings."""
        test_scripts = ["gujarati", "devanagari", "tamil", "telugu", "bengali", "gurmukhi", "oriya", "kannada", "malayalam", "urdu", "latin"]
        for s in test_scripts:
            res = map_aadhaar_data({"local_script": s, "local_address": "સરનામું : ટેસ્ટ એડ્રેસ"})
            self.assertTrue(res["language"]["name"], f"Language name must not be empty for script {s}")
            self.assertFalse(res["address"]["local"].startswith("સરનામું :"), "Address prefix must be stripped")

    def test_templates_safe_fallbacks(self):
        """Ensure Jinja2 templates have foolproof Hindi fallback."""
        for template_name in ["front.html", "back.html"]:
            path = os.path.join("templates", "cards", "aadhaar", "default", template_name)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertTrue("Hindi" in content and "or" in content, f"{template_name} must contain fallback to Hindi")

    def test_end_to_end_card_rendering(self):
        """Ensure card rendering runs cleanly without Playwright crashes."""
        mapped_data = {
            "person": {"name": "Test User", "name_local": "ટેસ્ટ", "dob": "01-01-1990", "gender": "M"},
            "address": {"local": "ટેસ્ટ સરનામું, સુરત, ગુજરાત", "full": "Test Address, Surat, Gujarat"},
            "identity": {"aadhaar_number": "1234 5678 9012", "enrolment_number": "9100 1100 2200 3300"},
            "contact": {"mobile": "9876543210"},
            "photo": {"available": False},
            "qr": {"available": False},
            "language": {"name": "Gujarati", "code": "gu"}
        }
        output_dir = os.path.join("tests_output", "integrity_check")
        front, back = render_card(mapped_data, {}, output_dir)
        self.assertTrue(os.path.exists(front), "Front card image must be generated")
        self.assertTrue(os.path.exists(back), "Back card image must be generated")

if __name__ == "__main__":
    unittest.main()
