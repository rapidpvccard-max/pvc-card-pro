import os
import requests
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"

def test_tabs():
    print("==================================================")
    print("TESTING AYUSHMAN / AADHAAR TAB SWITCHING UI")
    print("==================================================")

    # 1. Login via session
    session = requests.Session()
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "live_tester@example.com",
        "password": "Password123!"
    })
    token = r.cookies.get("access_token")
    print(f"Login successful, got cookie: {token is not None}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        if token:
            context.add_cookies([{
                "name": "access_token",
                "value": token,
                "domain": "127.0.0.1",
                "path": "/"
            }])
        page = context.new_page()
        page.goto(f"{BASE_URL}/generator")
        page.wait_for_load_state("networkidle")

        # Check Initial State (Aadhaar active)
        btn_aadhaar = page.locator("#doc-btn-aadhaar")
        btn_ayushman = page.locator("#doc-btn-ayushman")
        upload_text = page.locator("#upload-zone-text")
        doc_type_input = page.locator("#selected-document-type")

        aadhaar_class = btn_aadhaar.get_attribute("class") or ""
        ayushman_class = btn_ayushman.get_attribute("class") or ""
        print(f"Initial State -> Aadhaar class: '{aadhaar_class}', Ayushman class: '{ayushman_class}'")
        assert "active" in aadhaar_class, "Aadhaar button should be active initially"
        assert "active" not in ayushman_class, "Ayushman button should NOT be active initially"
        assert "Upload Aadhaar PDF" in upload_text.text_content()
        assert doc_type_input.input_value() == "aadhaar"
        print("  [PASS] Initial Aadhaar tab state verified.")

        # Click Ayushman Tab
        print("\nClicking 'Ayushman (PM-JAY) Card' button...")
        btn_ayushman.click()
        page.wait_for_timeout(300)

        aadhaar_class = btn_aadhaar.get_attribute("class") or ""
        ayushman_class = btn_ayushman.get_attribute("class") or ""
        print(f"After Ayushman Click -> Aadhaar class: '{aadhaar_class}', Ayushman class: '{ayushman_class}'")
        assert "active" in ayushman_class, "Ayushman button should now be active"
        assert "active" not in aadhaar_class, "Aadhaar button should now be inactive"
        assert "Upload Ayushman PDF" in upload_text.text_content()
        assert doc_type_input.input_value() == "ayushman"
        print(f" -> Upload zone text: '{upload_text.text_content()}'")
        print(f" -> Hidden doc_type value: '{doc_type_input.input_value()}'")
        print("  [PASS] Ayushman tab switch verified successfully!")

        # Click Aadhaar Tab Again
        print("\nClicking 'Aadhaar Card' button to switch back...")
        btn_aadhaar.click()
        page.wait_for_timeout(300)

        aadhaar_class = btn_aadhaar.get_attribute("class") or ""
        ayushman_class = btn_ayushman.get_attribute("class") or ""
        print(f"After Aadhaar Re-click -> Aadhaar class: '{aadhaar_class}', Ayushman class: '{ayushman_class}'")
        assert "active" in aadhaar_class, "Aadhaar button should be active again"
        assert "active" not in ayushman_class, "Ayushman button should be inactive again"
        assert "Upload Aadhaar PDF" in upload_text.text_content()
        assert doc_type_input.input_value() == "aadhaar"
        print("  [PASS] Re-switching to Aadhaar tab verified successfully!")

        browser.close()

    print("\n==================================================")
    print("ALL TAB SWITCHING TESTS PASSED 100%!")
    print("==================================================")

if __name__ == "__main__":
    test_tabs()
