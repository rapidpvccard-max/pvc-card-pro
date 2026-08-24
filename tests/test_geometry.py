from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8000/generator")
        
        # Get bounding client rects
        file_input = page.locator("#pdf-file").bounding_box()
        upload_zone = page.locator("#file-drop-area").bounding_box()
        btn = page.locator("#upload-btn").bounding_box()
        
        print(f"File Input Rect: {file_input}")
        print(f"Upload Zone Rect: {upload_zone}")
        print(f"Button Rect: {btn}")
        
        # Evaluate element at button center
        target = page.evaluate("""
            () => {
                const btn = document.getElementById('upload-btn');
                const rect = btn.getBoundingClientRect();
                const x = rect.left + rect.width / 2;
                const y = rect.top + rect.height / 2;
                const el = document.elementFromPoint(x, y);
                return el ? el.tagName + '#' + el.id + '.' + el.className : 'none';
            }
        """)
        print(f"Element at Button Center: {target}")
        
        browser.close()

if __name__ == '__main__':
    run()
