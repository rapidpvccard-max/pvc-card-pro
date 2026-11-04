import sys
import os
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database, models, auth

def test_demo_badges():
    db = next(database.get_db())
    # Find or update user to 0 wallet balance so demo shows
    user = db.query(models.User).filter(models.User.status == "active").first()
    uc = db.query(models.UserCredits).filter(models.UserCredits.user_id == user.id).first()
    if uc:
        original_bal = uc.wallet_balance
        uc.wallet_balance = 0.0
        uc.sample_aadhaar = 1
        uc.sample_ayushman = 1
        uc.sample_aadhaar_color = 1
        uc.sample_crop = 1
        uc.sample_passport = 1
        db.commit()
    
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
        page.wait_for_timeout(1000)
        
        services_grid = page.locator(".services-showcase-grid")
        services_grid.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        services_grid.screenshot(path="C:/Users/NANO/.gemini/antigravity/brain/7ea1a93d-7ea4-442d-a150-3f2da8dbe098/dashboard_cards_demo.png")
        print("Saved dashboard demo cards screenshot.")
        
        page.goto("http://127.0.0.1:8000/generator")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        
        tabs_bar = page.locator(".doc-type-selector-bar")
        tabs_bar.screenshot(path="C:/Users/NANO/.gemini/antigravity/brain/7ea1a93d-7ea4-442d-a150-3f2da8dbe098/generator_tabs_demo.png")
        print("Saved generator demo tabs screenshot.")
        
        browser.close()
        
    # Restore balance
    if uc:
        uc.wallet_balance = original_bal
        db.commit()

if __name__ == "__main__":
    test_demo_badges()

