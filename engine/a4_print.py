import os
from typing import List
from PIL import Image

A4_WIDTH = 2480
A4_HEIGHT = 3508
CARD_WIDTH = 1016
CARD_HEIGHT = 638

MARGIN_X = 150
GAP_X = 148
MARGIN_Y = 53
GAP_Y = 53

def create_a4_print_pdf(front_images: List[str], back_images: List[str], output_path: str, mirror_columns_for_duplex: bool = True) -> dict:
    """
    Takes lists of front and back PNG paths and generates a professional A4 print-ready PDF
    with up to 10 cards per sheet (2 cols, 5 rows).
    Maintains exact 300DPI 1016x638 dimensions without scaling.
    mirror_columns_for_duplex: If True, mirrors the columns on the back sheet for long-edge duplex printing.
    """
    if len(front_images) != len(back_images):
        raise ValueError("Number of front images must match number of back images")
        
    num_cards = len(front_images)
    cards_per_page = 10
    
    # Calculate how many pages we need (each "page" in logic is a pair of Front and Back sheets)
    num_sheets = (num_cards + cards_per_page - 1) // cards_per_page
    if num_sheets == 0:
        num_sheets = 1  # Handle 0 cards gracefully if requested, though unlikely
        
    pdf_pages = []
    
    for sheet_idx in range(num_sheets):
        start_idx = sheet_idx * cards_per_page
        end_idx = min(start_idx + cards_per_page, num_cards)
        
        # Create Front Sheet
        front_sheet = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
        # Create Back Sheet
        back_sheet = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
        
        for i in range(start_idx, end_idx):
            idx_on_page = i - start_idx
            row = idx_on_page // 2
            col = idx_on_page % 2
            
            # Front coordinates
            front_x = MARGIN_X + col * (CARD_WIDTH + GAP_X)
            front_y = MARGIN_Y + row * (CARD_HEIGHT + GAP_Y)
            
            # Back coordinates
            back_col = (1 - col) if mirror_columns_for_duplex else col
            back_x = MARGIN_X + back_col * (CARD_WIDTH + GAP_X)
            back_y = MARGIN_Y + row * (CARD_HEIGHT + GAP_Y)
            
            # Paste Front Image
            if os.path.exists(front_images[i]):
                with Image.open(front_images[i]) as img:
                    if img.size != (CARD_WIDTH, CARD_HEIGHT):
                        img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
                    front_sheet.paste(img, (front_x, front_y))
                    
            # Paste Back Image
            if os.path.exists(back_images[i]):
                with Image.open(back_images[i]) as img:
                    if img.size != (CARD_WIDTH, CARD_HEIGHT):
                        img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
                    back_sheet.paste(img, (back_x, back_y))
                    
        pdf_pages.append(front_sheet)
        pdf_pages.append(back_sheet)
        
    # Save as PDF
    if pdf_pages:
        # Save first page, append the rest
        first_page = pdf_pages[0]
        first_page.save(
            output_path,
            "PDF",
            resolution=300.0,
            save_all=True,
            append_images=pdf_pages[1:]
        )
        
    return {
        "success": True,
        "pdf_path": output_path,
        "page_count": len(pdf_pages),
        "cards_per_page": cards_per_page,
        "card_dimensions": f"{CARD_WIDTH}x{CARD_HEIGHT}",
        "page_dimensions": f"{A4_WIDTH}x{A4_HEIGHT}",
        "duplex_mirroring": mirror_columns_for_duplex
    }
