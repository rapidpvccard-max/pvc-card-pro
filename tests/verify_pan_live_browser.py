import os
import sys
import requests
from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000"

def verify_pan_live():
    print("Testing PAN Card live browser 1-click auto-crop on fresh server...")
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
    sample_pdf = os.path.join(os.environ.get("USERPROFILE", "C:/Users/NANO"), "Downloads", "SAGAR PATIL PAN CARD.pdf")

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

        # 1. Open Generator with crop tab
        page.goto(f"{BASE_URL}/generator?type=crop")
        page.wait_for_load_state("networkidle")
        print("  1. Loaded /generator?type=crop")
        
        # 1-Click option is checked by default (#chk-instant-autocrop)
        chk = page.locator("#chk-instant-autocrop")
        print(f"  2. 1-Click Auto-Crop is checked: {chk.is_checked()}")

        # 2. Upload PAN PDF with 1-click enabled
        print(f"  3. Uploading {sample_pdf} (1-click direct mode)...")
        page.set_input_files("#pdf-file", sample_pdf)

        # In 1-click mode, it should automatically detect, display toast/processing, and generate!
        print("  4. Waiting for result section...")
        page.wait_for_selector("#result-section", state="visible", timeout=25000)
        page.wait_for_timeout(2000)

        result_path = "tests_output/pan_1click_live_result_fixed.png"
        page.screenshot(path=result_path)
        print(f"  5. Screenshot saved: {result_path}")

        # Download front and back preview images to inspect
        front_img = page.locator("#front-preview")
        back_img = page.locator("#back-preview")
        print(f"  6. Front preview src: {front_img.get_attribute('src')}")
        print(f"  7. Back preview src: {back_img.get_attribute('src')}")

        browser.close()

    print("\n[SUCCESS] PAN Card Live Browser Verification complete!")

if __name__ == "__main__":
    verify_pan_live()
