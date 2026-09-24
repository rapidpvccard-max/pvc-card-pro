import os
import sys
import requests
from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000"

def verify_eshram_live():
    print("Testing e-Shram live browser interaction...")
    session = requests.Session()
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "test_cropper@example.com",
        "password": "password123"
    })
    
    token = None
    if r.status_code == 200:
        token = r.cookies.get("access_token")
    else:
        # Fallback to QA user
        r2 = session.post(f"{BASE_URL}/auth/login", json={
            "email": "qa@test.com",
            "password": "password123"
        })
        token = r2.cookies.get("access_token")

    os.makedirs("tests_output", exist_ok=True)
    sample_pdf = os.path.join(os.environ.get("USERPROFILE", "C:/Users/NANO"), "Downloads", "uan-card.pdf")

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
        
        # Verify 1-Click option container is visible
        instant_container = page.locator("#instant-autocrop-container")
        assert instant_container.is_visible(), "instant-autocrop-container should be visible on crop tab"
        print("  2. Instant Auto-Crop container is visible!")

        # Uncheck instant autocrop to inspect the interactive editor first
        page.uncheck("#chk-instant-autocrop")

        # 2. Upload e-Shram PDF
        print(f"  3. Uploading {sample_pdf}...")
        page.set_input_files("#pdf-file", sample_pdf)

        # Wait for crop editor
        page.wait_for_selector("#crop-editor-section", state="visible", timeout=15000)
        page.wait_for_timeout(1000)

        # Check badge
        badge = page.locator("#crop-auto-detect-badge")
        print(f"  4. Badge visible: {badge.is_visible()}, Text: {badge.inner_text()}")

        # Check active preset chip
        active_chip = page.locator(".preset-chip-btn.active")
        print(f"  5. Active preset chip: {active_chip.inner_text() if active_chip.count() > 0 else 'None'}")

        # Take screenshot of perfectly aligned crop boxes
        page.screenshot(path="tests_output/eshram_crop_editor_auto_aligned.png")
        print("     Saved: tests_output/eshram_crop_editor_auto_aligned.png")

        # 3. Generate PVC Card
        print("  6. Clicking 'Crop & Generate PVC Card'...")
        page.click("#btn-submit-crop")

        page.wait_for_selector("#result-section", state="visible", timeout=20000)
        page.wait_for_timeout(1000)
        page.screenshot(path="tests_output/eshram_result_ready.png")
        print("     Saved: tests_output/eshram_result_ready.png")

        browser.close()

    print("\n[SUCCESS] e-Shram Live Browser Verification complete!")

if __name__ == "__main__":
    verify_eshram_live()
