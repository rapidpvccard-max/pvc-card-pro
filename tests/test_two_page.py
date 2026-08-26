import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
    ctx = b.new_context(viewport={'width': 1016, 'height': 638}, device_scale_factor=1)
    
    p1 = ctx.new_page()
    p2 = ctx.new_page()
    
    html1 = '<html><body style="margin:0;padding:0;width:1016px;height:638px;background:red;"><h1>Front</h1></body></html>'
    html2 = '<html><body style="margin:0;padding:0;width:1016px;height:638px;background:blue;"><h1>Back</h1></body></html>'
    
    t0 = time.time()
    p1.set_content(html1, wait_until='commit')
    p1.screenshot(path='tests_output/p1.png')
    p2.set_content(html2, wait_until='commit')
    p2.screenshot(path='tests_output/p2.png')
    t1 = time.time()
    
    print(f"Two pages render with commit: {(t1-t0)*1000:.2f} ms")
    b.close()
