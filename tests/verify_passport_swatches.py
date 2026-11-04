import sys
import os
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database, models, auth

def test_passport_swatches():
    db = next(database.get_db())
    user = db.query(models.User).filter(models.User.status == "active").first()
    token = auth.create_access_token({"sub": str(user.id)})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Test standard 1366x768 screen
        context = browser.new_context(viewport={"width": 1366, "height": 850})
        context.add_cookies([{
            "name": "access_token",
            "value": token,
            "domain": "127.0.0.1",
            "path": "/"
        }])
        page = context.new_page()

        print("Navigating to http://127.0.0.1:8000/generator?type=passport...")
        page.goto("http://127.0.0.1:8000/generator?type=passport")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Ensure container is visible
        container = page.locator("#passport-studio-container")
        assert container.is_visible(), "Passport studio container is not visible!"

        # Scroll to background color swatches
        wrapper = page.locator(".passport-bg-color-wrapper")
        wrapper.scroll_into_view_if_needed()
        page.wait_for_timeout(500)

        # Check all swatches
        swatches = page.locator(".passport-swatch-item").all()
        print(f"Found {len(swatches)} swatches in the bar.")
        assert len(swatches) >= 10, f"Expected at least 10 swatches, found {len(swatches)}"

        # Verify all swatches have the same Y-coordinate (meaning they are in ONE SINGLE LINE!)
        y_coords = []
        for i, sw in enumerate(swatches):
            box = sw.bounding_box()
            y_coords.append(round(box["y"]))
            color_name = sw.get_attribute("data-name")
            print(f"Swatch {i+1}: '{color_name}' at x={box['x']:.1f}, y={box['y']:.1f}")

        print(f"All Swatch Y coordinates: {y_coords}")
        assert len(set(y_coords)) == 1, f"Swatches are not in 1 line! Y coords: {y_coords}"
        print("SUCCESS: All swatches are in ONE SINGLE LINE!")

        # Test clicking White swatch
        white_swatch = page.locator(".passport-swatch-item[data-color='white']")
        white_swatch.click()
        page.wait_for_timeout(300)
        badge = page.locator("#selected-passport-color-badge")
        print("After clicking White, badge text:", badge.inner_text())
        assert "White" in badge.inner_text()

        # Test clicking Sky Blue swatch
        sky_swatch = page.locator(".passport-swatch-item[data-color='sky_blue']")
        sky_swatch.click()
        page.wait_for_timeout(300)
        print("After clicking Sky Blue, badge text:", badge.inner_text())
        assert "Sky Blue" in badge.inner_text()

        # Click back to Light Blue
        page.locator(".passport-swatch-item[data-color='light_blue']").click()
        page.wait_for_timeout(300)

        # Take screenshot of the settings container
        container.screenshot(path="C:/Users/NANO/.gemini/antigravity/brain/7ea1a93d-7ea4-442d-a150-3f2da8dbe098/passport_settings_single_line.png")
        print("Screenshot saved to passport_settings_single_line.png.")

        browser.close()

if __name__ == "__main__":
    test_passport_swatches()
