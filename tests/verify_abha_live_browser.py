import os
import sys
import requests
from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000"

def verify_abha_live():
    print("Testing ABHA Card live browser auto-crop...")
    session = requests.Session()
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "test_cropper@example.com",
        "password": "password123"
    })
    token = None
    if r.status_code == 200:
        token = r.cookies.get("access_token")
    else:
        r2 = session.post(f"{BASE_URL}/auth/login", json={
            "email": "qa@test.com",
            "password": "password123"
        })
        token = r2.cookies.get("access_token")

    os.makedirs("tests_output", exist_ok=True)
    sample_pdf = os.path.join(os.environ.get("USERPROFILE", "C:/Users/NANO"), "Downloads", "ABHA-Card-52-8664-8328-6259.pdf")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1366, "height": 900})
        if token:
            context.add_cookies([{
                "name": "access_token",
                "value": token,
                "domain": "127.0.0.1",
                "path": "/"
            }])
        page = context.new_page()

        # Part 1: Test interactive editor positioning (uncheck instant autocrop)
        page.goto(f"{BASE_URL}/generator?type=crop")
        page.wait_for_load_state("networkidle")
        print("  1. Loaded /generator?type=crop")

        # Uncheck instant autocrop to view the editor bounding boxes
        page.uncheck("#chk-instant-autocrop")
        print("  2. Unchecked instant 1-click mode to inspect bounding boxes in editor...")

        # Upload ABHA PDF
        print(f"  3. Uploading {sample_pdf}...")
        page.set_input_files("#pdf-file", sample_pdf)

        page.wait_for_selector("#crop-editor-section", state="visible", timeout=15000)
        page.wait_for_timeout(1000)

        # Verify badge and active chip
        badge = page.locator("#crop-auto-detect-badge")
        print(f"  4. Badge visible: {badge.is_visible()}, Text: {badge.inner_text()}")

        active_chip = page.locator(".preset-chip-btn.active")
        print(f"  5. Active preset chip: {active_chip.inner_text() if active_chip.count() > 0 else 'None'}")

        editor_screenshot = "tests_output/abha_crop_editor_boxes.png"
        page.screenshot(path=editor_screenshot)
        print(f"  6. Editor bounding boxes screenshot saved: {editor_screenshot}")

        # Part 2: Generate card
        print("  7. Clicking 'Crop & Generate PVC Card'...")
        page.click("#btn-submit-crop")

        page.wait_for_selector("#result-section", state="visible", timeout=25000)
        page.wait_for_timeout(2000)

        result_screenshot = "tests_output/abha_result_ready.png"
        page.screenshot(path=result_screenshot)
        print(f"  8. Result screenshot saved: {result_screenshot}")

        # Print preview URLs
        front_img = page.locator("#front-preview")
        back_img = page.locator("#back-preview")
        print(f"  9. Front preview src: {front_img.get_attribute('src')}")
        print(f" 10. Back preview src: {back_img.get_attribute('src')}")

        browser.close()

    print("\n[SUCCESS] ABHA Card Live Browser Verification complete!")

if __name__ == "__main__":
    verify_abha_live()
