import os
import requests
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"

def capture_tab_screenshots():
    session = requests.Session()
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "live_tester@example.com",
        "password": "Password123!"
    })
    token = r.cookies.get("access_token")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
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

        os.makedirs("tests_output", exist_ok=True)
        page.screenshot(path="tests_output/generator_aadhaar_active.png")

        btn_ayushman = page.locator("#doc-btn-ayushman")
        btn_ayushman.click()
        page.wait_for_timeout(300)
        page.screenshot(path="tests_output/generator_ayushman_active.png")

        browser.close()
    print("Screenshots captured at tests_output/generator_aadhaar_active.png and tests_output/generator_ayushman_active.png")

if __name__ == "__main__":
    capture_tab_screenshots()
