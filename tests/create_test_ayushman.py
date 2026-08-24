import os
import fitz  # PyMuPDF
import io
import base64
from PIL import Image, ImageDraw

def create_sample_ayushman_pdf(output_path="test_ayushman.pdf"):
    """Creates a synthetic 2-page test Ayushman PDF with embedded photo, QR, and text."""
    doc = fitz.open()

    # Page 1: Front / Beneficiary Info
    page1 = doc.new_page(width=595, height=842) # A4

    # Create dummy portrait photo image
    photo_img = Image.new("RGB", (150, 190), color=(180, 200, 220))
    d = ImageDraw.Draw(photo_img)
    d.rectangle([20, 20, 130, 170], fill=(100, 140, 180))
    photo_bytes = io.BytesIO()
    photo_img.save(photo_bytes, format="PNG")
    photo_rect = fitz.Rect(50, 150, 150, 280)
    page1.insert_image(photo_rect, stream=photo_bytes.getvalue())

    # Create dummy QR code image
    qr_img = Image.new("RGB", (120, 120), color=(255, 255, 255))
    qd = ImageDraw.Draw(qr_img)
    qd.rectangle([10, 10, 40, 40], fill=(0, 0, 0))
    qd.rectangle([80, 10, 110, 40], fill=(0, 0, 0))
    qd.rectangle([10, 80, 40, 110], fill=(0, 0, 0))
    qd.rectangle([50, 50, 70, 70], fill=(0, 0, 0))
    qr_bytes = io.BytesIO()
    qr_img.save(qr_bytes, format="PNG")
    qr_rect = fitz.Rect(450, 150, 550, 250)
    page1.insert_image(qr_rect, stream=qr_bytes.getvalue())

    # Text content on Page 1
    p1_text = """
National Health Authority
Pradhan Mantri Jan Arogya Yojana
AYUSHMAN CARD

NAME
NISHAD GANESHBHAI DINDYALBHAI

YOB: 1958 | GENDER: MALE
Village/Ward: 
Subdivision/Town: 
District: RAJKOT
State: Gujarat

Mobile: 9737779794
PM-JAY ID: P9QBPEP3Y
ABHA Number: 14-1234-5678-9012
Ration/Other ID: 240100123456

આયુષ્માન ભારત પ્રધાનમંત્રી જન આરોગ્ય યોજના
AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA
"""
    page1.insert_text((50, 50), p1_text, fontsize=11, fontname="helv")

    # Page 2: Instructions
    page2 = doc.new_page(width=595, height=842)
    p2_text = """
સ્વાસ્થ્યનું વરદાન, આયુષ્માન
Health Protection for Every Family

1. આ આયુષ્માન કાર્ડ, આપને અને આપના કુટુંબના દરેક સભ્યને આયુષ્માન ભારત PMJAY યોજના સાથે સંલગ્ન ગુજરાતની કોઈપણ હોસ્પિટલમાં, કુટુંબ દીઠ વાર્ષિક રૂપિયા ૫ લાખ સુધીનું આરોગ્ય કવચ મેળવવામાં મદદ કરશે.
This Ayushman card will help you in availing benefits of free hospitalization cover of Rs. 5 Lakhs per annum to you and your family collectively at any empanelled hospital across India under Ayushman Bharat PM-JAY.

2. આયુષ્માન ભારત PMJAY યોજના અંતર્ગત ભારતભરની AB PMJAY યોજના સાથે સંલગ્ન હોસ્પિટલોમાં આપે કોઈ પૈસા ચૂકવવા/જમા કરવાની જરૂર નથી.
You are not required to pay/deposit any money at the AB PM-JAY empanelled hospital across India under Ayushman Bharat PM-JAY.

3. યોજના સંબંધિત ફરિયાદની જાણ કરવા અથવા તમારી નજીકના AB PMJAY એમ્પેનલ્ડ હોસ્પિટલો વિશે વધુ જાણકારી મેળવવા, કૃપા કરીને અમારો સંપર્ક કરો. (ટોલ ફ્રી નં- ૧૮૦૦ ૨૩૩ ૧૦૨૨)
For any help, to report a grievance or to know more about AB PM-JAY empanelled hospitals near you, please reach out to us. (Toll Free No- 1800 233 1022)

Please download the App / એપ ડાઉનલોડ કરો
Google Play
સંપર્ક કરો / Please contact: 14555 / 1800 233 1022
લોગ ઓન કરો / or log on to: https://pmjay.gov.in
"""
    page2.insert_text((50, 50), p2_text, fontsize=10, fontname="helv")

    doc.save(output_path)
    doc.close()
    print(f"Created test Ayushman PDF at {output_path}")

if __name__ == "__main__":
    create_sample_ayushman_pdf()
