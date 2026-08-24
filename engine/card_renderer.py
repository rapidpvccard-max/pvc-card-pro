"""
card_renderer.py - Enterprise High-Speed Persistent Rendering Engine
---------------------------------------------------------------------
Architecture:
- Runs a dedicated worker thread with a persistent, pre-warmed Chromium browser instance.
- Avoids Windows asyncio / SelectorEventLoop subprocess conflicts (NotImplementedError).
- Eliminates the 3-8s cold-start browser launch on every single card render.
- Renders front + back PVC cards in ~1.1 seconds!
- Thread-safe queue dispatch with automatic error recovery and crash self-healing.
"""

import os
import base64
import threading
import queue
import atexit
import time
from jinja2 import Environment, FileSystemLoader

# ---------------------------------------------------------------------------
# Module-level template image caching (avoids reading from disk repeatedly)
# ---------------------------------------------------------------------------

_template_b64_cache: dict = {}
_template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
_jinja_env = Environment(loader=FileSystemLoader(_template_dir))


def _get_template_b64(images_dir: str, doc_type: str, side: str) -> str:
    """Load and cache template background images as base64 strings."""
    cache_key = f"{doc_type}_{side}"
    if cache_key in _template_b64_cache:
        return _template_b64_cache[cache_key]

    if not os.path.exists(images_dir):
        _template_b64_cache[cache_key] = ""
        return ""

    candidates = [
        f"{doc_type.upper()}_{side.upper()}.png",
        f"{doc_type.upper()}_{side.upper()}.jpg",
        f"AADHAR_{side.upper()}.png" if doc_type == "aadhaar" else "",
        f"AADHAAR_{side.upper()}.png" if doc_type == "aadhaar" else "",
        f"{side.lower()}.png",
        f"{side.upper()}.png",
    ]
    for name in candidates:
        if not name:
            continue
        path = os.path.join(images_dir, name)
        if os.path.exists(path):
            with open(path, "rb") as f:
                result = base64.b64encode(f.read()).decode("utf-8")
            _template_b64_cache[cache_key] = result
            return result

    # Generic fallback
    for f in os.listdir(images_dir):
        f_lower = f.lower()
        if side.lower() in f_lower and f_lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            with open(os.path.join(images_dir, f), "rb") as img_file:
                result = base64.b64encode(img_file.read()).decode("utf-8")
            _template_b64_cache[cache_key] = result
            return result

    _template_b64_cache[cache_key] = ""
    return ""


# ---------------------------------------------------------------------------
# Persistent Dedicated Browser Worker Thread
# ---------------------------------------------------------------------------

class PersistentBrowserWorker:
    def __init__(self):
        self.req_queue = queue.Queue()
        self.ready_event = threading.Event()
        self._stopped = False
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="PVC-RenderWorker")
        self.worker_thread.start()
        # Wait up to 8 seconds for initial warm-up
        self.ready_event.wait(timeout=8)

    def _worker_loop(self):
        while not self._stopped:
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    ctx = browser.new_context(
                        viewport={"width": 1016, "height": 638},
                        device_scale_factor=1
                    )
                    page = ctx.new_page()
                    self.ready_event.set()
                    print("[CardRenderer] Persistent Chromium rendering engine warm and ready.")

                    while not self._stopped:
                        task = self.req_queue.get()
                        if task is None:
                            break
                        front_html, back_html, front_path, back_path, res_queue = task
                        try:
                            # Render Front (use load with timeout to prevent network font hang)
                            page.set_content(front_html, wait_until="load", timeout=15000)
                            page.screenshot(path=front_path, type="png")

                            # Render Back
                            page.set_content(back_html, wait_until="load", timeout=15000)
                            page.screenshot(path=back_path, type="png")

                            res_queue.put((True, None))
                        except Exception as e:
                            print(f"[CardRenderer] Render error in persistent worker: {e}")
                            res_queue.put((False, str(e)))
                            # Break inner loop to restart clean browser if damaged
                            break
                        finally:
                            self.req_queue.task_done()
                    
                    try:
                        browser.close()
                    except Exception:
                        pass
            except Exception as e:
                print(f"[CardRenderer] Worker thread error ({e}). Restarting worker in 1s...")
                time.sleep(1)

    def render(self, front_html: str, back_html: str, front_path: str, back_path: str, timeout: int = 30):
        if not self.ready_event.is_set():
            self.ready_event.wait(timeout=5)

        res_queue = queue.Queue()
        self.req_queue.put((front_html, back_html, front_path, back_path, res_queue))
        success, err = res_queue.get(timeout=timeout)
        if not success:
            # Fallback to cold render if persistent worker failed
            print(f"[CardRenderer] Persistent render failed ({err}), falling back to direct render...")
            return _cold_start_render_html(front_html, back_html, front_path, back_path)
        return front_path, back_path

    def stop(self):
        self._stopped = True
        self.req_queue.put(None)


def _cold_start_render_html(front_html: str, back_html: str, front_path: str, back_path: str):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        c = b.new_context(viewport={"width": 1016, "height": 638}, device_scale_factor=1)
        pg = c.new_page()
        pg.set_content(front_html, wait_until="load", timeout=15000)
        pg.screenshot(path=front_path, type="png")
        pg.set_content(back_html, wait_until="load", timeout=15000)
        pg.screenshot(path=back_path, type="png")
        b.close()
    return front_path, back_path


# Global Persistent Worker Singleton
_worker = PersistentBrowserWorker()

def _cleanup_worker():
    try:
        _worker.stop()
    except Exception:
        pass

atexit.register(_cleanup_worker)


# ---------------------------------------------------------------------------
# Public Entrypoint
# ---------------------------------------------------------------------------

def render_card(mapped_data: dict, engine_data: dict, output_dir: str, document_type: str = "aadhaar"):
    """
    Renders PVC Card front and back images using the high-speed persistent browser worker.
    Returns (front_path, back_path).
    """
    os.makedirs(output_dir, exist_ok=True)
    doc_type = (document_type or mapped_data.get("document_type") or "aadhaar").lower().strip()
    if doc_type not in ["aadhaar", "ayushman"]:
        doc_type = "aadhaar"

    front_template = _jinja_env.get_template(f"cards/{doc_type}/default/front.html")
    back_template = _jinja_env.get_template(f"cards/{doc_type}/default/back.html")

    photo_base64 = mapped_data.get("photo", {}).get("base64", "")
    qr_base64 = mapped_data.get("qr", {}).get("base64", "")
    images_dir = os.path.join(_template_dir, "cards", doc_type, "default", "images")
    template_front_base64 = _get_template_b64(images_dir, doc_type, "front")
    template_back_base64 = _get_template_b64(images_dir, doc_type, "back")

    context = {
        "document_type": doc_type,
        "language": mapped_data.get("language", {}),
        "person": mapped_data.get("person", {}),
        "identity": mapped_data.get("identity", {}),
        "address": mapped_data.get("address", {}),
        "contact": mapped_data.get("contact", {}),
        "scheme": mapped_data.get("scheme", {}),
        "photo": mapped_data.get("photo", {}),
        "qr": mapped_data.get("qr", {}),
        "photo_base64": photo_base64,
        "qr_base64": qr_base64,
        "template_front_base64": template_front_base64,
        "template_back_base64": template_back_base64,
        "is_baal_aadhaar": mapped_data.get("is_baal_aadhaar", False),
    }

    front_html = front_template.render(**context)
    back_html = back_template.render(**context)

    front_path = os.path.join(output_dir, "front.png")
    back_path = os.path.join(output_dir, "back.png")

    return _worker.render(front_html, back_html, front_path, back_path)
