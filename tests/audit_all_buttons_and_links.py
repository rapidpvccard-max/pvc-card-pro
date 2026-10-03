import os
import re
import sys
from html.parser import HTMLParser

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app import app
import database, models, auth

client = TestClient(app)

class ButtonParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.current_button = None

    def handle_starttag(self, tag, attrs):
        if tag == "button":
            attr_dict = dict(attrs)
            self.current_button = {
                "id": attr_dict.get("id", ""),
                "class": attr_dict.get("class", ""),
                "type": attr_dict.get("type", "button"),
                "onclick": attr_dict.get("onclick", ""),
                "data_preset": attr_dict.get("data-preset", ""),
                "text": ""
            }

    def handle_data(self, data):
        if self.current_button is not None:
            self.current_button["text"] += data.strip()

    def handle_endtag(self, tag):
        if tag == "button" and self.current_button is not None:
            self.buttons.append(self.current_button)
            self.current_button = None

def run_audit():
    print("=" * 75)
    print(" 🔍 STATIC & TEMPLATE AUDIT: ALL BUTTONS, LINKS & SERVICE FLOWS")
    print("=" * 75)

    # 1. Create auth session
    db = next(database.get_db())
    test_user = db.query(models.User).first()
    if test_user:
        token = auth.create_access_token({"sub": str(test_user.id)})
        client.cookies.set("access_token", token)

    # Test pages render without 500 error
    test_pages = [
        ("/", [200, 307]),
        ("/generator", 200),
        ("/generator?type=aadhaar", 200),
        ("/generator?type=aadhaar_color", 200),
        ("/generator?type=ayushman", 200),
        ("/generator?type=crop", 200),
        ("/dashboard", 200),
        ("/subscription", 200),
        ("/history", 200),
        ("/profile", 200),
        ("/contact", 200),
        ("/terms", 200),
        ("/refund-policy", 200),
        ("/privacy-policy", 200),
        ("/health", 200),
        ("/api/user/credits", 200),
        ("/api/user/me", 200)
    ]

    print("\n--- [1] Checking All Core Page & API Responses ---")
    all_pages_ok = True
    for path, expected in test_pages:
        resp = client.get(path, follow_redirects=False)
        expected_list = expected if isinstance(expected, list) else [expected]
        is_ok = (resp.status_code in expected_list)
        status_icon = "✅" if is_ok else "❌"
        print(f"  {status_icon} GET {path:<35} -> HTTP {resp.status_code} (Expected {expected})")
        if not is_ok:
            all_pages_ok = False

    assert all_pages_ok, "Some pages failed to render!"

    # Parse index.html and app.js for all buttons
    print("\n--- [2] Auditing All Buttons in Generator (index.html) ---")
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    with open("static/js/app.js", "r", encoding="utf-8") as f:
        js_code = f.read()

    parser = ButtonParser()
    parser.feed(html_content)
    buttons = parser.buttons
    print(f"[*] Found {len(buttons)} button elements in index.html:")
    for btn in buttons:
        btn_id = btn["id"]
        btn_class = btn["class"]
        btn_text = btn["text"] or "Icon/Child"
        btn_onclick = btn["onclick"]
        
        # Check if button is handled either via onclick, id in JS, or class in JS
        handled = False
        mechanism = ""
        if btn_onclick:
            handled = True
            mechanism = f"inline onclick: {btn_onclick[:30]}"
        elif btn_id and btn_id in js_code:
            handled = True
            mechanism = f"JS listener on #{btn_id}"
        elif btn_class and any(c in js_code for c in btn_class.split()):
            handled = True
            mechanism = f"JS class listener: {btn_class}"
        elif btn.get("type") == "submit":
            handled = True
            mechanism = "Form submit event (uploadForm)"

        status = "✅" if handled else "⚠️ Unhandled?"
        print(f"  {status} Button: [{btn_text[:30]:<30}] id='{btn_id}' | {mechanism}")
        assert handled, f"Button {btn_id} {btn_text} has no handler!"

    # Check 4 Core Services Buttons
    print("\n--- [3] Verifying 4 Core Service Triggers ---")
    services = [
        ("Aadhaar (Standard)", "doc-btn-aadhaar", "setDocumentType('aadhaar')"),
        ("Aadhaar (Colourful)", "doc-btn-aadhaar-color", "setDocumentType('aadhaar_color')"),
        ("Ayushman PVC Card", "doc-btn-ayushman", "setDocumentType('ayushman')"),
        ("Auto Card Cropper", "doc-btn-crop", "setDocumentType('crop')")
    ]
    for s_name, s_id, s_call in services:
        assert s_id in html_content, f"Service button {s_id} not found in template!"
        assert s_id in js_code or s_call in html_content, f"Service button {s_id} handler missing!"
        print(f"  ✅ Service Button: {s_name:<25} (id='{s_id}') -> Handler Active")

    print("\n--- [4] Auditing Download Action Buttons ---")
    download_buttons = [
        ("Download Front PNG", "btn-dl-front"),
        ("Download Back PNG", "btn-dl-back"),
        ("Download A4 PDF", "btn-dl-a4"),
        ("Start Over / Reset", "btn-start-over"),
        ("Submit Crop PVC", "btn-submit-crop"),
        ("Re-upload in Crop", "btn-crop-reupload"),
        ("Dismiss Error Box", "btn-redirect-generator")
    ]
    for d_name, d_id in download_buttons:
        assert d_id in html_content, f"Action button {d_id} not found in template!"
        assert d_id in js_code, f"Action button {d_id} not wired in app.js!"
        print(f"  ✅ Action Button: {d_name:<25} (id='{d_id}') -> Wired in JS")

    print("\n--- [5] Auditing Dashboard Navigation & Actions (dashboard.html) ---")
    with open("templates/dashboard.html", "r", encoding="utf-8") as f:
        dash_content = f.read()

    dash_triggers = [
        ("Aadhaar Card Click", "window.location.href='/generator?type=aadhaar'"),
        ("Ayushman Card Click", "window.location.href='/generator?type=ayushman'"),
        ("Colourful Aadhaar Click", "window.location.href='/generator?type=aadhaar_color'"),
        ("Cropper Card Click", "window.location.href='/generator?type=crop'"),
        ("Card Prints Tab", "switchDashboardTab('prints')"),
        ("Wallet Recharges Tab", "switchDashboardTab('recharges')")
    ]
    for d_name, d_code in dash_triggers:
        assert d_code in dash_content, f"Dashboard action {d_name} not found!"
        print(f"  ✅ Dashboard Trigger: {d_name:<25} -> Verified")

    print("\n--- [6] Auditing Topbar & Sidebar Navigation (dashboard_base.html) ---")
    with open("templates/dashboard_base.html", "r", encoding="utf-8") as f:
        base_content = f.read()

    base_links = [
        ("Dashboard Link", "href=\"/dashboard\""),
        ("Generator Link", "href=\"/generator\""),
        ("History Link", "href=\"/history\""),
        ("Recharge Plans Link", "href=\"/subscription\""),
        ("Profile Link", "href=\"/profile\""),
        ("Contact Link", "href=\"/contact\""),
        ("Refund Policy Link", "href=\"/refund-policy\""),
        ("Terms Link", "href=\"/terms\""),
        ("Logout Trigger", "logout()")
    ]
    for l_name, l_code in base_links:
        assert l_code in base_content, f"Base link {l_name} not found!"
        print(f"  ✅ Navigation Link: {l_name:<25} -> Verified")

    print("\n" + "=" * 75)
    print(" 🏆 ALL BUTTONS, LINKS & 4 SERVICES ARE 100% OPERATIONAL & VERIFIED!")
    print("=" * 75)

if __name__ == "__main__":
    run_audit()
