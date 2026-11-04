import sys
import os
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database, models, auth

def test_ui():
    db = next(database.get_db())
    user = db.query(models.User).filter(models.User.status == "active").first()
    token = auth.create_access_token({"sub": str(user.id)})
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1366, "height": 900})
        context.add_cookies([{
            "name": "access_token",
            "value": token,
            "domain": "127.0.0.1",
            "path": "/"
        }])
        page = context.new_page()
        
        page.goto("http://127.0.0.1:8000/dashboard")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        
        # Scroll to services grid
        services_grid = page.locator(".services-showcase-grid")
        services_grid.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        
        # Save screenshot of dashboard cards specifically
        services_grid.screenshot(path="C:/Users/NANO/.gemini/antigravity/brain/7ea1a93d-7ea4-442d-a150-3f2da8dbe098/dashboard_cards_fixed.png")
        print("Saved dashboard cards screenshot.")
        browser.close()

if __name__ == "__main__":
    test_ui()
