import os
import requests
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"

def test_crop_tab_navigation():
    print("==================================================")
    print("TESTING DIRECT /generator?type=crop & TAB CLICK")
    print("==================================================")

    session = requests.Session()
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "live_tester@example.com",
        "password": "Password123!"
    })
    token = r.cookies.get("access_token")

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

        # TEST 1: Direct navigation to /generator?type=crop
        print("Navigating to /generator?type=crop ...")
        page.goto(f"{BASE_URL}/generator?type=crop")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        btn_crop = page.locator("#doc-btn-crop")
        btn_aadhaar = page.locator("#doc-btn-aadhaar")
        doc_type_input = page.locator("#selected-document-type")
        upload_text = page.locator("#upload-zone-text")
        instant_container = page.locator("#instant-autocrop-container")

        crop_class = btn_crop.get_attribute("class") or ""
        aadhaar_class = btn_aadhaar.get_attribute("class") or ""
        print(f"Direct URL State -> Crop class: '{crop_class}', Aadhaar class: '{aadhaar_class}'")
        print(f"selected-document-type: {doc_type_input.input_value()}")
        print(f"upload_text: {upload_text.text_content()}")
        print(f"instant_container display: {instant_container.is_visible()}")

        assert "active" in crop_class, "Auto Card Cropper tab MUST be active on ?type=crop"
        assert "active" not in aadhaar_class, "Aadhaar tab must NOT be active on ?type=crop"
        assert doc_type_input.input_value() == "crop", "doc_type_input must be 'crop'"
        assert instant_container.is_visible(), "Instant auto-crop container must be visible"
        print("  [PASS] Direct URL /generator?type=crop auto-selection verified!")

        # TEST 2: Navigate to plain /generator, then click #doc-btn-crop
        print("\nNavigating to plain /generator ...")
        page.goto(f"{BASE_URL}/generator")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(300)

        print("Clicking #doc-btn-crop tab...")
        page.locator("#doc-btn-crop").click()
        page.wait_for_timeout(300)

        crop_class = btn_crop.get_attribute("class") or ""
        aadhaar_class = btn_aadhaar.get_attribute("class") or ""
        print(f"After Click State -> Crop class: '{crop_class}', Aadhaar class: '{aadhaar_class}'")
        assert "active" in crop_class, "Auto Card Cropper tab MUST be active after click"
        assert "active" not in aadhaar_class, "Aadhaar tab must NOT be active after click"
        assert doc_type_input.input_value() == "crop", "doc_type_input must be 'crop'"
        assert instant_container.is_visible(), "Instant auto-crop container must be visible"

        page.screenshot(path="tests_output/crop_tab_active_test.png")
        print("  [PASS] Tab click switching verified! Screenshot saved to tests_output/crop_tab_active_test.png")

        browser.close()

if __name__ == "__main__":
    test_crop_tab_navigation()
