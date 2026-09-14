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

def create_a4_print_pdf(front_images: List[str], back_images: List[str], output_path: str, mirror_columns_for_duplex: bool = False, side_by_side: bool = True) -> dict:
    """
    Takes lists of front and back PNG paths and generates a professional 300 DPI A4 print-ready PDF
    with exact CR80 1016x638 dimensions without scaling.
    
    Layout Modes:
    1. side_by_side=True (Default):
       Places Front (Left) and Back (Right) on the SAME single A4 sheet side-by-side ("Aju-Baju").
       - 1 Card = 1 Page (Front on Left, Back on Right).
       - Holds up to 5 complete cards per sheet (5 rows, 2 columns).
       
    2. mirror_columns_for_duplex=True (When side_by_side=False):
       Long-edge duplex mode with Fronts on Sheet 1 and mirrored Backs on Sheet 2.
    """
    if len(front_images) != len(back_images):
        raise ValueError("Number of front images must match number of back images")
        
    num_cards = len(front_images)
    pdf_pages = []

    # If mirror_columns_for_duplex is explicitly requested and side_by_side is disabled
    if mirror_columns_for_duplex and not side_by_side:
        cards_per_sheet = 10
        num_sheets = (num_cards + cards_per_sheet - 1) // cards_per_sheet
        if num_sheets == 0:
            num_sheets = 1
            
        for sheet_idx in range(num_sheets):
            start_idx = sheet_idx * cards_per_sheet
            end_idx = min(start_idx + cards_per_sheet, num_cards)
            
            front_sheet = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
            back_sheet = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
            
            for i in range(start_idx, end_idx):
                idx_on_page = i - start_idx
                row = idx_on_page // 2
                col = idx_on_page % 2
                
                front_x = MARGIN_X + col * (CARD_WIDTH + GAP_X)
                front_y = MARGIN_Y + row * (CARD_HEIGHT + GAP_Y)
                
                back_col = 1 - col
                back_x = MARGIN_X + back_col * (CARD_WIDTH + GAP_X)
                back_y = MARGIN_Y + row * (CARD_HEIGHT + GAP_Y)
                
                if os.path.exists(front_images[i]):
                    with Image.open(front_images[i]) as img:
                        if img.size != (CARD_WIDTH, CARD_HEIGHT):
                            img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
                        front_sheet.paste(img, (front_x, front_y))
                        
                if os.path.exists(back_images[i]):
                    with Image.open(back_images[i]) as img:
                        if img.size != (CARD_WIDTH, CARD_HEIGHT):
                            img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
                        back_sheet.paste(img, (back_x, back_y))
                        
            pdf_pages.append(front_sheet)
            pdf_pages.append(back_sheet)
            
        layout_mode = "duplex_mirrored"
    else:
        # Standard Cyber Cafe / CSC Single-Page Side-by-Side ("Aju-Baju") Format
        # Row holds: Col 0 = Front (Left), Col 1 = Back (Right) on the SAME A4 page
        cards_per_sheet = 5  # 5 rows per A4 page
        num_sheets = (num_cards + cards_per_sheet - 1) // cards_per_sheet
        if num_sheets == 0:
            num_sheets = 1
            
        for sheet_idx in range(num_sheets):
            start_idx = sheet_idx * cards_per_sheet
            end_idx = min(start_idx + cards_per_sheet, num_cards)
            
            sheet = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
            
            for i in range(start_idx, end_idx):
                row = i - start_idx
                y = MARGIN_Y + row * (CARD_HEIGHT + GAP_Y)
                
                front_x = MARGIN_X
                back_x = MARGIN_X + CARD_WIDTH + GAP_X
                
                # Paste Front Image (Left side)
                if os.path.exists(front_images[i]):
                    with Image.open(front_images[i]) as img:
                        if img.size != (CARD_WIDTH, CARD_HEIGHT):
                            img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
                        sheet.paste(img, (front_x, y))
                        
                # Paste Back Image (Right side)
                if os.path.exists(back_images[i]):
                    with Image.open(back_images[i]) as img:
                        if img.size != (CARD_WIDTH, CARD_HEIGHT):
                            img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
                        sheet.paste(img, (back_x, y))
                        
            pdf_pages.append(sheet)
            
        layout_mode = "side_by_side"
        
    # Save as PDF
    if pdf_pages:
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
        "cards_per_page": cards_per_sheet,
        "card_dimensions": f"{CARD_WIDTH}x{CARD_HEIGHT}",
        "page_dimensions": f"{A4_WIDTH}x{A4_HEIGHT}",
        "duplex_mirroring": mirror_columns_for_duplex,
        "layout_mode": layout_mode
    }
