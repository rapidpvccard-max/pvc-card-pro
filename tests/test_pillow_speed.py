import time
import os
from PIL import Image, ImageDraw, ImageFont

def test_pillow_render():
    t0 = time.time()
    
    # 1. Base template
    template_path = "templates/cards/aadhaar/default/images/AADHAAR_FRONT.png"
    if not os.path.exists(template_path):
        print("Template not found!")
        return
        
    img = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    # 2. Draw text
    # In production we use Noto Sans / local fonts
    draw.text((210, 35), "Government of India", fill="black")
    draw.text((210, 80), "MALE / पुरुष", fill="black")
    draw.text((210, 120), "1234 5678 9012", fill="red")
    
    os.makedirs("tests_output", exist_ok=True)
    img.save("tests_output/pillow_test.png", "PNG", dpi=(300, 300))
    t1 = time.time()
    
    print(f"Pillow Direct Render Time: {(t1-t0)*1000:.2f} ms")

if __name__ == "__main__":
    test_pillow_render()
