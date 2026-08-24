import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from engine.a4_print import create_a4_print_pdf

def test_print_layouts():
    print("Testing A4 Print Layouts...")
    
    # We use the images generated during the renderer test for our source material
    front_img = os.path.join("tests_output", "Hindi", "front.png")
    back_img = os.path.join("tests_output", "Hindi", "back.png")
    
    if not os.path.exists(front_img) or not os.path.exists(back_img):
        print(f"Test images not found at {front_img} and {back_img}. Run test_renderer.py first.")
        return
        
    test_cases = [1, 2, 5, 10, 12]  # Testing various counts including one that overflows to a second page
    
    output_dir = os.path.join("tests_output", "A4_Prints")
    os.makedirs(output_dir, exist_ok=True)
    
    for count in test_cases:
        print(f"Generating PDF for {count} cards...")
        
        # Duplicate the same image paths to simulate multiple cards
        fronts = [front_img] * count
        backs = [back_img] * count
        
        output_pdf = os.path.join(output_dir, f"print_{count}_cards.pdf")
        
        result = create_a4_print_pdf(fronts, backs, output_pdf)
        
        print(f"  Success: {result['success']}")
        print(f"  Pages: {result['page_count']}")
        print(f"  Saved to: {result['pdf_path']}")
        
        # Validation checks
        assert os.path.exists(output_pdf), f"PDF was not created for {count} cards"
        
        # Verify page count
        # For each 10 cards, we have 1 front sheet + 1 back sheet = 2 pages
        expected_pages = ((count + 9) // 10) * 2
        if count == 0:
            expected_pages = 2
        assert result['page_count'] == expected_pages, f"Expected {expected_pages} pages, got {result['page_count']}"
        
    print("All A4 PDF generation tests passed!")

if __name__ == "__main__":
    test_print_layouts()
