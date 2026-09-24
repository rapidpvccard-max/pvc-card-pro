import os
import requests
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"

def test_live_ui():
    print("Connecting to localhost:8000 to test Auto Card Cropper UI...")
    session = requests.Session()
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "qa@test.com",
        "password": "password123"
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.cookies.get("access_token")

    os.makedirs("tests_output", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1366, "height": 850})
        if token:
            context.add_cookies([{
                "name": "access_token",
                "value": token,
                "domain": "127.0.0.1",
                "path": "/"
            }])
        page = context.new_page()

        # 1. Dashboard View
        print("  1. Checking Dashboard with new Auto Card Cropper card...")
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="tests_output/dashboard_with_crop_card.png")
        print("     Saved: tests_output/dashboard_with_crop_card.png")

        # 2. Generator Page with crop tab active
        print("  2. Checking Generator page (/generator?type=crop)...")
        page.goto(f"{BASE_URL}/generator?type=crop")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="tests_output/generator_crop_tab.png")
        print("     Saved: tests_output/generator_crop_tab.png")

        # 3. Upload file and test interactive cropper
        test_file = os.path.abspath(os.path.join("tests", "test_ayushman.pdf"))
        print(f"  3. Uploading {test_file} into crop dropzone...")
        page.set_input_files("#pdf-file", test_file)

        # Wait for crop editor to show up
        print("     Waiting for precision crop editor (#crop-editor-section)...")
        page.wait_for_selector("#crop-editor-section", state="visible", timeout=15000)
        page.wait_for_timeout(1000) # Wait for preview image render
        page.screenshot(path="tests_output/crop_interactive_editor.png")
        print("     Saved: tests_output/crop_interactive_editor.png")

        # Test clicking preset chips (e.g. e-Shram, PAN, Voter)
        btn_eshram = page.locator("button.preset-chip-btn[data-preset='eshram']")
        if btn_eshram.count() > 0:
            btn_eshram.click()
            page.wait_for_timeout(300)

        # 4. Click Crop & Generate PVC Card
        print("  4. Clicking 'Crop & Generate PVC Card'...")
        page.click("#btn-submit-crop")

        # Wait for result section
        page.wait_for_selector("#result-section", state="visible", timeout=20000)
        page.wait_for_timeout(1000)
        page.screenshot(path="tests_output/crop_result_screen.png")
        print("     Saved: tests_output/crop_result_screen.png")

        browser.close()

    print("\n[SUCCESS] Live UI verification complete! All screenshots saved in tests_output/")

if __name__ == "__main__":
    test_live_ui()
