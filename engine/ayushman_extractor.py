"""
ayushman_extractor.py
---------------------------------------------------------------------
Deterministic extraction of Ayushman / PM-JAY demographic data --
Name, YOB, Gender, PM-JAY ID, Mobile, Photo, QR Code, Location (Village,
Subdivision/Town, District, State), ABHA Number, and State/Language Scheme branding --
from a 2-page Ayushman PDF.

Decodes embedded QR codes on rendered pages to extract full demographic details
(including Mobile, District, Subdivision, Village/Ward, and PM-JAY ID) across all
variations of Ayushman / PM-JAY PDF formats.
"""

from __future__ import annotations

import io
import re
import base64
import logging
from dataclasses import dataclass, asdict, field
from typing import Optional, Any, Dict

import fitz  # PyMuPDF
from PIL import Image, ImageOps
from pyzbar.pyzbar import decode as zbar_decode

try:
    import qrcode
except ImportError:
    qrcode = None

logger = logging.getLogger("ayushman_extractor")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)


# State to Local Language and Scheme Titles Mapping for all Indian States
STATE_LANGUAGE_MAP: Dict[str, Dict[str, str]] = {
    "maharashtra": {
        "lang_code": "mr",
        "lang_name": "Marathi",
        "state_local": "महाराष्ट्र",
        "state_en": "MAHARASHTRA",
        "state_label": "राज्य :",
        "name_label": "नाव/NAME",
        "yob_label": "जन्म वर्ष/ YOB :",
        "gender_label": "लिंग/ GENDER :",
        "village_ward_label": "गाव/वार्ड-Village/Ward :",
        "subdivision_town_label": "तालुका/शहर-Subdivision/Town :",
        "district_label": "जिल्हा/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाखांपर्यंत",
        "treatment_text_local": "मोफत उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना–महात्मा ज्योतिराव फुले जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI - JAN AROGYA YOJANA-MAHATMA JYOTIRAO PHULE JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID - MJPJAY ID :",
        "ration_label": "Ration Card No :",
        "back_header_local": "आरोग्याचे वरदान, आयुष्मान",
        "app_download_local": "ॲप डाउनलोड करा",
        "contact_label_local": "संपर्क करा",
        "log_on_label_local": "लॉग ऑन करा",
        "point1_local": "हे आयुष्मान कार्ड तुम्हाला आणि तुमच्या कुटुंबातील प्रत्येक सदस्याला देशभरातील कोणत्याही संलग्न रुग्णालयात प्रति कुटुंब वार्षिक ५ लाख रुपयांपर्यंतचे मोफत आरोग्य कवच मिळवून देईल.",
        "point2_local": "आयुष्मान भारत PM-JAY योजनेअंतर्गत संलग्न रुग्णालयांमध्ये तुम्हाला कोणतेही पैसे देण्याची आवश्यकता नाही.",
        "point3_local": "तक्रार नोंदवण्यासाठी किंवा जवळच्या रुग्णालयांची माहिती मिळवण्यासाठी आमच्या टोल फ्री नंबर १४५५५ वर संपर्क साधा."
    },
    "gujarat": {
        "lang_code": "gu",
        "lang_name": "Gujarati",
        "state_local": "ગુજરાત",
        "state_en": "GUJARAT",
        "state_label": "રાજ્ય:",
        "name_label": "નામ / NAME",
        "yob_label": "જન્મ વર્ષ / YOB :",
        "gender_label": "જાતિ / GENDER :",
        "village_ward_label": "ગામ/વોર્ડ - Village/Ward :",
        "subdivision_town_label": "તાલુકા/શહેર - Subdivision/Town :",
        "district_label": "જિલ્લો/District :",
        "card_title_local": "આયુષ્માન કાર્ડ",
        "coverage_amount_local": "₹ ૫ લાખ સુધીની",
        "treatment_text_local": "મફત સારવાર",
        "scheme_footer_local": "આયુષ્માન ભારત પ્રધાનમંત્રી જન આરોગ્ય યોજના",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "સ્વાસ્થ્યનું વરદાન, આયુષ્માન",
        "app_download_local": "એપ ડાઉનલોડ કરો",
        "contact_label_local": "સંપર્ક કરો",
        "log_on_label_local": "લોગ ઓન કરો",
        "point1_local": "આ આયુષ્માન કાર્ડ, આપને અને આપના કુટુંબના દરેક સભ્યને આયુષ્માન ભારત PMJAY યોજના સાથે સંલગ્ન ગુજરાતની કોઈપણ હોસ્પિટલમાં, કુટુંબ દીઠ વાર્ષિક રૂપિયા ૫ લાખ સુધીનું આરોગ્ય કવચ મેળવવામાં મદદ કરશે.",
        "point2_local": "આયુષ્માન ભારત PMJAY યોજના અંતર્ગત ભારતભરની AB PMJAY યોજના સાથે સંલગ્ન હોસ્પિટલોમાં આપે કોઈ પૈસા ચૂકવવા/જમા કરવાની જરૂર નથી.",
        "point3_local": "યોજના સંબંધિત ફરિયાદની જાણ કરવા અથવા તમારી નજીકના AB PMJAY એમ્પેનલ્ડ હોસ્પિટલો વિશે વધુ જાણકારી મેળવવા, કૃપા કરીને અમારો સંપર્ક કરો. (ટોલ ફ્રી નં- ૧૮૦૦ ૨૩૩ ૧૦૨૨)"
    },
    "default_hindi": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "भारत",
        "state_en": "INDIA",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "यह आयुष्मान कार्ड आपको और आपके परिवार के प्रत्येक सदस्य को प्रति वर्ष ₹ 5 लाख तक के मुफ्त इलाज की सुविधा प्रदान करेगा।",
        "point2_local": "आयुष्मान भारत PM-JAY के तहत संबद्ध अस्पतालों में आपको कोई भी शुल्क या राशि जमा करने की आवश्यकता नहीं है।",
        "point3_local": "किसी भी सहायता या शिकायत के लिए हमारे टोल फ्री नंबर 14555 / 1800 111 565 पर संपर्क करें।"
    },
    "uttar pradesh": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "उत्तर प्रदेश",
        "state_en": "UTTAR PRADESH",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "यह आयुष्मान कार्ड आपको और आपके परिवार के प्रत्येक सदस्य को प्रति वर्ष ₹ 5 लाख तक के मुफ्त इलाज की सुविधा प्रदान करेगा।",
        "point2_local": "आयुष्मान भारत PM-JAY के तहत संबद्ध अस्पतालों में आपको कोई भी शुल्क या राशि जमा करने की आवश्यकता नहीं है।",
        "point3_local": "किसी भी सहायता या शिकायत के लिए हमारे टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "madhya pradesh": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "मध्य प्रदेश",
        "state_en": "MADHYA PRADESH",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "यह आयुष्मान कार्ड आपको और आपके परिवार को प्रति वर्ष ₹ 5 लाख तक के मुफ्त इलाज की सुविधा प्रदान करेगा।",
        "point2_local": "संबद्ध अस्पतालों में कोई शुल्क जमा करने की आवश्यकता नहीं है।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "rajasthan": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "राजस्थान",
        "state_en": "RAJASTHAN",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "यह आयुष्मान कार्ड प्रति वर्ष ₹ 5 लाख तक के मुफ्त इलाज की सुविधा प्रदान करेगा।",
        "point2_local": "संबद्ध अस्पतालों में कोई शुल्क नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "bihar": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "बिहार",
        "state_en": "BIHAR",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "haryana": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "हरियाणा",
        "state_en": "HARYANA",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "delhi": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "दिल्ली",
        "state_en": "DELHI",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "jharkhand": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "झारखंड",
        "state_en": "JHARKHAND",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "chhattisgarh": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "छत्तीसगढ़",
        "state_en": "CHHATTISGARH",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "uttarakhand": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "उत्तराखंड",
        "state_en": "UTTARAKHAND",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "himachal pradesh": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "हिमाचल प्रदेश",
        "state_en": "HIMACHAL PRADESH",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "chandigarh": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "चंडीगढ़",
        "state_en": "CHANDIGARH",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "jammu and kashmir": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "जम्मू और कश्मीर",
        "state_en": "JAMMU AND KASHMIR",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "ladakh": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "लद्दाख",
        "state_en": "LADAKH",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "goa": {
        "lang_code": "hi",
        "lang_name": "Hindi",
        "state_local": "गोवा",
        "state_en": "GOA",
        "state_label": "राज्य:",
        "name_label": "नाम / NAME",
        "yob_label": "जन्म वर्ष / YOB :",
        "gender_label": "लिंग / GENDER :",
        "village_ward_label": "गाँव/वार्ड - Village/Ward :",
        "subdivision_town_label": "उपखंड/कस्बा - Subdivision/Town :",
        "district_label": "ज़िला/District :",
        "card_title_local": "आयुष्मान कार्ड",
        "coverage_amount_local": "₹ ५ लाख तक",
        "treatment_text_local": "मुफ्त उपचार",
        "scheme_footer_local": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "स्वास्थ्य का वरदान, आयुष्मान",
        "app_download_local": "ऐप डाउनलोड करें",
        "contact_label_local": "संपर्क करें",
        "log_on_label_local": "लॉग ऑन करें",
        "point1_local": "प्रति वर्ष ₹ 5 लाख तक का मुफ्त इलाज।",
        "point2_local": "अस्पतालों में कोई पैसा नहीं देना होगा।",
        "point3_local": "टोल फ्री नंबर 14555 पर संपर्क करें।"
    },
    "telangana": {
        "lang_code": "te",
        "lang_name": "Telugu",
        "state_local": "తెలంగాణ",
        "state_en": "TELANGANA",
        "state_label": "రాష్ట్రం:",
        "name_label": "పేరు / NAME",
        "yob_label": "పుట్టిన సంవత్సరం / YOB :",
        "gender_label": "లింగం / GENDER :",
        "village_ward_label": "గ్రామం/వార్డు - Village/Ward :",
        "subdivision_town_label": "సబ్ డివిజన్/పట్టణం - Subdivision/Town :",
        "district_label": "జిల్లా/District :",
        "card_title_local": "ఆయుష్మాన్ కార్డ్",
        "coverage_amount_local": "₹ 5 లక్షల వరకు",
        "treatment_text_local": "ఉచిత చికిత్స",
        "scheme_footer_local": "ఆయుష్మాన్ భారత్ ప్రధాన మంత్రి జన్ ఆరోగ్య యోజన",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "ఆరోగ్య వరం, ఆయుష్మాన్",
        "app_download_local": "యాప్‌ని డౌన్‌లోడ్ చేయండి",
        "contact_label_local": "సంప్రదించండి",
        "log_on_label_local": "లాగిన్ అవ్వండి",
        "point1_local": "ఈ ఆయుష్మాన్ కార్డ్ కుటుంబానికి సంవత్సరానికి రూ. 5 లక్షల వరకు ఉచిత చికిత్సను అందిస్తుంది.",
        "point2_local": "ఆసుపత్రులలో ఎటువంటి రుసుము చెల్లించాల్సిన అవసరం లేదు.",
        "point3_local": "టోల్ ఫ్రీ నంబర్ 14555 కు కాల్ చేయండి."
    },
    "andhra pradesh": {
        "lang_code": "te",
        "lang_name": "Telugu",
        "state_local": "ఆంధ్రప్రదేశ్",
        "state_en": "ANDHRA PRADESH",
        "state_label": "రాష్ట్రం:",
        "name_label": "పేరు / NAME",
        "yob_label": "పుట్టిన సంవత్సరం / YOB :",
        "gender_label": "లింగం / GENDER :",
        "village_ward_label": "గ్రామం/వార్డు - Village/Ward :",
        "subdivision_town_label": "సబ్ డివిజన్/పట్టణం - Subdivision/Town :",
        "district_label": "జిల్లా/District :",
        "card_title_local": "ఆయుష్మాన్ కార్డ్",
        "coverage_amount_local": "₹ 5 లక్షల వరకు",
        "treatment_text_local": "ఉచిత చికిత్స",
        "scheme_footer_local": "ఆయుష్మాన్ భారత్ ప్రధాన మంత్రి జన్ ఆరోగ్య యోజన",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "ఆరోగ్య వరం, ఆయుష్మాన్",
        "app_download_local": "యాప్‌ని డౌన్‌లోడ్ చేయండి",
        "contact_label_local": "సంప్రదించండి",
        "log_on_label_local": "లాగిన్ అవ్వండి",
        "point1_local": "కుటుంబానికి సంవత్సరానికి రూ. 5 లక్షల వరకు ఉచిత చికిత్స.",
        "point2_local": "ఎటువంటి రుసుము చెల్లించాల్సిన అవసరం లేదు.",
        "point3_local": "టోల్ ఫ్రీ నంబర్ 14555."
    },
    "tamil nadu": {
        "lang_code": "ta",
        "lang_name": "Tamil",
        "state_local": "தமிழ்நாடு",
        "state_en": "TAMIL NADU",
        "state_label": "மாநிலம்:",
        "name_label": "பெயர் / NAME",
        "yob_label": "பிறந்த ஆண்டு / YOB :",
        "gender_label": "பாலினம் / GENDER :",
        "village_ward_label": "கிராமம்/வார்டு - Village/Ward :",
        "subdivision_town_label": "துணைப்பிரிவு/நகரம் - Subdivision/Town :",
        "district_label": "மாவட்டம்/District :",
        "card_title_local": "ஆயுஷ்மான் அட்டை",
        "coverage_amount_local": "₹ 5 லட்சம் வரை",
        "treatment_text_local": "இலவச சிகிச்சை",
        "scheme_footer_local": "ஆயுஷ்மான் பாரத் பிரதமர் மக்கள் ஆரோக்கிய திட்டம்",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "சுகாதார வரம், ஆயுஷ்மான்",
        "app_download_local": "செயலியைப் பதிவிறக்கவும்",
        "contact_label_local": "தொடர்பு கொள்ளவும்",
        "log_on_label_local": "உள்நுழைக",
        "point1_local": "குடும்பத்திற்கு ஆண்டுக்கு ரூ. 5 லட்சம் வரை இலவச மருத்துவ சிகிச்சை.",
        "point2_local": "மருத்துவமனைகளில் எந்தக் கட்டணமும் செலுத்த தேவையில்லை.",
        "point3_local": "கட்டணமில்லா எண் 14555 ஐத் தொடர்பு கொள்ளவும்."
    },
    "puducherry": {
        "lang_code": "ta",
        "lang_name": "Tamil",
        "state_local": "புதுச்சேரி",
        "state_en": "PUDUCHERRY",
        "state_label": "மாநிலம்:",
        "name_label": "பெயர் / NAME",
        "yob_label": "பிறந்த ஆண்டு / YOB :",
        "gender_label": "பாலினம் / GENDER :",
        "village_ward_label": "கிராமம்/வார்டு - Village/Ward :",
        "subdivision_town_label": "துணைப்பிரிவு/நகரம் - Subdivision/Town :",
        "district_label": "மாவட்டம்/District :",
        "card_title_local": "ஆயுஷ்மான் அட்டை",
        "coverage_amount_local": "₹ 5 லட்சம் வரை",
        "treatment_text_local": "இலவச சிகிச்சை",
        "scheme_footer_local": "ஆயுஷ்மான் பாரத் பிரதமர் மக்கள் ஆரோக்கிய திட்டம்",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "சுகாதார வரம், ஆயுஷ்மான்",
        "app_download_local": "செயலியைப் பதிவிறக்கவும்",
        "contact_label_local": "தொடர்பு கொள்ளவும்",
        "log_on_label_local": "உள்நுழைக",
        "point1_local": "குடும்பத்திற்கு ஆண்டுக்கு ரூ. 5 லட்சம் வரை இலவச மருத்துவ சிகிச்சை.",
        "point2_local": "மருத்துவமனைகளில் எந்தக் கட்டணமும் செலுத்த தேவையில்லை.",
        "point3_local": "கட்டணமில்லா எண் 14555 ஐத் தொடர்பு கொள்ளவும்."
    },
    "karnataka": {
        "lang_code": "kn",
        "lang_name": "Kannada",
        "state_local": "ಕರ್ನಾಟಕ",
        "state_en": "KARNATAKA",
        "state_label": "ರಾಜ್ಯ:",
        "name_label": "ಹೆಸರು / NAME",
        "yob_label": "ಹುಟ್ಟಿದ ವರ್ಷ / YOB :",
        "gender_label": "ಲಿಂಗ / GENDER :",
        "village_ward_label": "ಗ್ರಾಮ/ವಾರ್ಡ್ - Village/Ward :",
        "subdivision_town_label": "ಉಪವಿಭಾಗ/ಪಟ್ಟಣ - Subdivision/Town :",
        "district_label": "ಜಿಲ್ಲೆ/District :",
        "card_title_local": "ಆಯುಷ್ಮಾನ್ ಕಾರ್ಡ್",
        "coverage_amount_local": "₹ 5 ಲಕ್ಷದವರೆಗೆ",
        "treatment_text_local": "ಉಚಿತ ಚಿಕಿತ್ಸೆ",
        "scheme_footer_local": "ಆಯುಷ್ಮಾನ್ ಭಾರತ ಪ್ರಧಾನ ಮಂತ್ರಿ ಜನ ಆರೋಗ್ಯ ಯೋಜನೆ",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "ಆರೋಗ್ಯದ ವರ, ಆಯುಷ್ಮಾನ್",
        "app_download_local": "ಆ್ಯಪ್ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ",
        "contact_label_local": "ಸಂಪರ್ಕಿಸಿ",
        "log_on_label_local": "ಲಾಗಿನ್ ಮಾಡಿ",
        "point1_local": "ಪ್ರತಿ ಕುಟುಂಬಕ್ಕೆ ವಾರ್ಷಿಕ ರೂ. 5 ಲಕ್ಷದವರೆಗೆ ಉಚಿತ ಚಿಕಿತ್ಸೆ.",
        "point2_local": "ಆಸ್ಪತ್ರೆಗಳಲ್ಲಿ ಯಾವುದೇ ಹಣ ಪಾವತಿಸುವ ಅಗತ್ಯವಿಲ್ಲ.",
        "point3_local": "ಟೋಲ್ ಫ್ರೀ ಸಂಖ್ಯೆ 14555."
    },
    "west bengal": {
        "lang_code": "bn",
        "lang_name": "Bengali",
        "state_local": "পশ্চিমবঙ্গ",
        "state_en": "WEST BENGAL",
        "state_label": "রাজ্য:",
        "name_label": "নাম / NAME",
        "yob_label": "জন্মের বছর / YOB :",
        "gender_label": "লিঙ্গ / GENDER :",
        "village_ward_label": "গ্রাম/ওয়ার্ড - Village/Ward :",
        "subdivision_town_label": "মহকুমা/শহর - Subdivision/Town :",
        "district_label": "জেলা/District :",
        "card_title_local": "আয়ুষ্মান কার্ড",
        "coverage_amount_local": "₹ ৫ লাখ পর্যন্ত",
        "treatment_text_local": "বিনামূল্যে চিকিৎসা",
        "scheme_footer_local": "আয়ুষ্মান ভারত প্রধানমন্ত্রী জন আরোগ্য যোজনা",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "স্বাস্থ্যের বরদান, আয়ুষ্মান",
        "app_download_local": "অ্যাপ ডাউনলোড করুন",
        "contact_label_local": "যোগাযোগ করুন",
        "log_on_label_local": "লগ ইন করুন",
        "point1_local": "পরিবার প্রতি বছরে ₹ ৫ লাখ পর্যন্ত বিনামূল্যে চিকিৎসা।",
        "point2_local": "হাসপাতালে কোনো টাকা জমা দিতে হবে না।",
        "point3_local": "টোল ফ্রি নম্বর 14555।"
    },
    "tripura": {
        "lang_code": "bn",
        "lang_name": "Bengali",
        "state_local": "ত্রিপুরা",
        "state_en": "TRIPURA",
        "state_label": "রাজ্য:",
        "name_label": "নাম / NAME",
        "yob_label": "জন্মের বছর / YOB :",
        "gender_label": "লিঙ্গ / GENDER :",
        "village_ward_label": "গ্রাম/ওয়ার্ড - Village/Ward :",
        "subdivision_town_label": "মহকুমা/শহর - Subdivision/Town :",
        "district_label": "জেলা/District :",
        "card_title_local": "আয়ুষ্মান কার্ড",
        "coverage_amount_local": "₹ ৫ লাখ পর্যন্ত",
        "treatment_text_local": "বিনামূল্যে চিকিৎসা",
        "scheme_footer_local": "আয়ুষ্মান ভারত প্রধানমন্ত্রী জন আরোগ্য যোজনা",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "স্বাস্থ্যের বরদান, আয়ুষ্মান",
        "app_download_local": "অ্যাপ ডাউনলোড করুন",
        "contact_label_local": "যোগাযোগ করুন",
        "log_on_label_local": "লগ ইন করুন",
        "point1_local": "পরিবার প্রতি বছরে ₹ ৫ লাখ পর্যন্ত বিনামূল্যে চিকিৎসা।",
        "point2_local": "হাসপাতালে কোনো টাকা জমা দিতে হবে না।",
        "point3_local": "টোল ফ্রি নম্বর 14555।"
    },
    "odisha": {
        "lang_code": "or",
        "lang_name": "Odia",
        "state_local": "ଓଡ଼ିଶା",
        "state_en": "ODISHA",
        "state_label": "ରାଜ୍ୟ:",
        "name_label": "ନାମ / NAME",
        "yob_label": "ଜନ୍ମ ବର୍ଷ / YOB :",
        "gender_label": "ଲିଙ୍ଗ / GENDER :",
        "village_ward_label": "ଗ୍ରାମ/ୱାର୍ଡ - Village/Ward :",
        "subdivision_town_label": "ଉପ-ବିଭାଗ/ସହର - Subdivision/Town :",
        "district_label": "ଜିଲ୍ଲା/District :",
        "card_title_local": "ଆୟୁଷ୍ମାନ କାର୍ଡ",
        "coverage_amount_local": "₹ ୫ ଲକ୍ଷ ପର୍ଯ୍ୟନ୍ତ",
        "treatment_text_local": "ମାଗଣା ଚିକିତ୍ସା",
        "scheme_footer_local": "ଆୟୁଷ୍ମାନ ଭାରତ ପ୍ରଧାନମନ୍ତ୍ରୀ ଜନ ଆରୋଗ୍ୟ ଯୋଜନା",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "ସ୍ୱାସ୍ଥ୍ୟର ବରଦାନ, ଆୟୁଷ୍ମାନ",
        "app_download_local": "ଆପ୍ ଡାଉନଲୋଡ୍ କରନ୍ତୁ",
        "contact_label_local": "ଯୋଗାଯୋଗ କରନ୍ତୁ",
        "log_on_label_local": "ଲଗ୍ ଇନ୍ କରନ୍ତୁ",
        "point1_local": "ପ୍ରତି ପରିବାର ବାର୍ଷିକ ₹ ୫ ଲକ୍ଷ ପର୍ଯ୍ୟନ୍ତ ମାଗଣା ଚିକିତ୍ସା।",
        "point2_local": "ଡାକ୍ତରଖାନାରେ କୌଣସି ଶୁଳ୍କ ଦେବାକୁ ପଡିବ ନାହିଁ।",
        "point3_local": "ଟୋଲ୍ ଫ୍ରି ନମ୍ବର 14555।"
    },
    "punjab": {
        "lang_code": "pa",
        "lang_name": "Punjabi",
        "state_local": "ਪੰਜਾਬ",
        "state_en": "PUNJAB",
        "state_label": "ਰਾਜ:",
        "name_label": "ਨਾਮ / NAME",
        "yob_label": "ਜਨਮ ਸਾਲ / YOB :",
        "gender_label": "ਲਿੰਗ / GENDER :",
        "village_ward_label": "ਪਿੰਡ/ਵਾਰਡ - Village/Ward :",
        "subdivision_town_label": "ਸਬ-ਡਵੀਜ਼ਨ/ਕਸਬਾ - Subdivision/Town :",
        "district_label": "ਜ਼ਿਲ੍ਹਾ/District :",
        "card_title_local": "ਆਯੁਸ਼ਮਾਨ ਕਾਰਡ",
        "coverage_amount_local": "₹ 5 ਲੱਖ ਤੱਕ",
        "treatment_text_local": "ਮੁਫ਼ਤ ਇਲਾਜ",
        "scheme_footer_local": "ਆਯੁਸ਼ਮਾਨ ਭਾਰਤ ਪ੍ਰਧਾਨ ਮੰਤਰੀ ਜਨ ਅਰੋਗਿਆ ਯੋਜਨਾ",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "ਸਿਹਤ ਦਾ ਵਰਦਾਨ, ਆਯੁਸ਼ਮਾਨ",
        "app_download_local": "ਐਪ ਡਾਊਨਲੋਡ ਕਰੋ",
        "contact_label_local": "ਸੰਪਰਕ ਕਰੋ",
        "log_on_label_local": "ਲਾਗ ਇਨ ਕਰੋ",
        "point1_local": "ਪ੍ਰਤੀ ਪਰਿਵਾਰ ਸਾਲਾਨਾ ₹ 5 ਲੱਖ ਤੱਕ ਮੁਫਤ ਇਲਾਜ।",
        "point2_local": "ਹਸਪਤਾਲ ਵਿੱਚ ਕੋਈ ਪੈਸਾ ਨਹੀਂ ਦੇਣਾ ਪਵੇਗਾ।",
        "point3_local": "ਟੋਲ ਫ੍ਰੀ ਨੰਬਰ 14555।"
    },
    "kerala": {
        "lang_code": "ml",
        "lang_name": "Malayalam",
        "state_local": "കേരളം",
        "state_en": "KERALA",
        "state_label": "സംസ്ഥാനം:",
        "name_label": "പേര് / NAME",
        "yob_label": "ജനന വർഷം / YOB :",
        "gender_label": "ലിംഗഭേദം / GENDER :",
        "village_ward_label": "ഗ്രാമം/വാർഡ് - Village/Ward :",
        "subdivision_town_label": "സബ് ഡിവിഷൻ/പട്ടണം - Subdivision/Town :",
        "district_label": "ജില്ല/District :",
        "card_title_local": "ആയുഷ്മാൻ കാർഡ്",
        "coverage_amount_local": "₹ 5 ലക്ഷം വരെ",
        "treatment_text_local": "സൗജന്യ ചികിത്സ",
        "scheme_footer_local": "ആയുഷ്മാൻ ഭാരത് പ്രധാനമന്ത്രി ജൻ ആരോഗ്യ യോജന",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "ആരോഗ്യ വരം, ആയുഷ്മാൻ",
        "app_download_local": "ആപ്പ് ഡൗൺലോഡ് ചെയ്യുക",
        "contact_label_local": "ബന്ധപ്പെടുക",
        "log_on_label_local": "ലോഗിൻ ചെയ്യുക",
        "point1_local": "ഒരു കുടുംബത്തിന് പ്രതിവർഷം ₹ 5 ലക്ഷം വരെ സൗജന്യ ചികിത്സ.",
        "point2_local": "ആശുപത്രികളിൽ പണം നൽകേണ്ടതില്ല.",
        "point3_local": "ടോൾ ഫ്രീ നമ്പർ 14555."
    },
    "assam": {
        "lang_code": "as",
        "lang_name": "Assamese",
        "state_local": "অসম",
        "state_en": "ASSAM",
        "state_label": "ৰাজ্য:",
        "name_label": "নাম / NAME",
        "yob_label": "জন্মৰ বছৰ / YOB :",
        "gender_label": "লিংগ / GENDER :",
        "village_ward_label": "গাঁও/ৱাৰ্ড - Village/Ward :",
        "subdivision_town_label": "মহকুমা/চহৰ - Subdivision/Town :",
        "district_label": "জিলা/District :",
        "card_title_local": "আয়ুষ্মান কাৰ্ড",
        "coverage_amount_local": "₹ ৫ লাখ পৰ্যন্ত",
        "treatment_text_local": "বিনামূলীয়া চিকিৎসা",
        "scheme_footer_local": "আয়ুষ্মান ভাৰত প্ৰধানমন্ত্ৰী জন আৰোগ্য যোজনা",
        "scheme_footer_en": "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA",
        "pmjay_label": "PM-JAY ID:",
        "ration_label": "Ration/Other ID:",
        "back_header_local": "স্বাস্থ্যৰ বৰদান, আয়ুষ্মান",
        "app_download_local": "এপ ডাউনল'ড কৰক",
        "contact_label_local": "যোগাযোগ কৰক",
        "log_on_label_local": "লগ ইন কৰক",
        "point1_local": "প্ৰতি পৰিয়াল বাৰ্ষিক ₹ ৫ লাখলৈকে বিনামূলীয়া চিকিৎসা।",
        "point2_local": "চিকিৎসালয়ত কোনো ধন জমা দিব নালাগে।",
        "point3_local": "টোল ফ্ৰী নম্বৰ 14555।"
    }
}

# Comprehensive District / City to State Mapping for All Indian States
DISTRICT_STATE_MAP: Dict[str, str] = {
    # Gujarat (All 33 districts + major cities/talukas)
    "surat": "gujarat", "ahmedabad": "gujarat", "vadodara": "gujarat", "baroda": "gujarat",
    "rajkot": "gujarat", "bhavnagar": "gujarat", "jamnagar": "gujarat", "junagadh": "gujarat",
    "gandhinagar": "gujarat", "anand": "gujarat", "navsari": "gujarat", "morbi": "gujarat",
    "bharuch": "gujarat", "porbandar": "gujarat", "surendranagar": "gujarat", "mehsana": "gujarat",
    "kutch": "gujarat", "kachchh": "gujarat", "bhuj": "gujarat", "gandhidham": "gujarat",
    "valsad": "gujarat", "vapi": "gujarat", "amreli": "gujarat", "banaskantha": "gujarat",
    "palanpur": "gujarat", "patan": "gujarat", "panchmahal": "gujarat", "godhra": "gujarat",
    "dahod": "gujarat", "sabarkantha": "gujarat", "himatnagar": "gujarat", "himmatnagar": "gujarat",
    "aravalli": "gujarat", "modasa": "gujarat", "botad": "gujarat", "chhotaudepur": "gujarat",
    "chhota udepur": "gujarat", "chhota udaipur": "gujarat", "devbhumi dwarka": "gujarat",
    "devbhoomi dwarka": "gujarat", "dwarka": "gujarat", "khambhalia": "gujarat",
    "gir somnath": "gujarat", "veraval": "gujarat", "kheda": "gujarat", "nadiad": "gujarat",
    "mahisagar": "gujarat", "lunawada": "gujarat", "narmada": "gujarat", "rajpipla": "gujarat",
    "tapi": "gujarat", "vyara": "gujarat", "dang": "gujarat", "ahwa": "gujarat",
    "ankleshwar": "gujarat", "bardoli": "gujarat", "deesa": "gujarat", "kalol": "gujarat",
    "gondal": "gujarat", "jetpur": "gujarat", "palitana": "gujarat", "khambhat": "gujarat",
    "dhoraji": "gujarat", "keshod": "gujarat", "wadhwan": "gujarat", "savarkundla": "gujarat",
    "mandvi": "gujarat", "halol": "gujarat", "bilimora": "gujarat", "unjha": "gujarat",
    "kadi": "gujarat", "visnagar": "gujarat", "siddhpur": "gujarat", "idar": "gujarat",
    "dhrangadhra": "gujarat",

    # Maharashtra (All 36 districts + major cities)
    "mumbai": "maharashtra", "pune": "maharashtra", "nagpur": "maharashtra", "thane": "maharashtra",
    "nashik": "maharashtra", "nasik": "maharashtra", "aurangabad": "maharashtra",
    "chhatrapati sambhajinagar": "maharashtra", "solapur": "maharashtra", "amravati": "maharashtra",
    "kolhapur": "maharashtra", "dhule": "maharashtra", "jalgaon": "maharashtra", "nanded": "maharashtra",
    "sangli": "maharashtra", "satara": "maharashtra", "ahmednagar": "maharashtra",
    "ahilyanagar": "maharashtra", "akola": "maharashtra", "latur": "maharashtra",
    "chandrapur": "maharashtra", "parbhani": "maharashtra", "jalna": "maharashtra",
    "raigad": "maharashtra", "ratnagiri": "maharashtra", "sindhudurg": "maharashtra",
    "beed": "maharashtra", "osmanabad": "maharashtra", "dharashiv": "maharashtra",
    "wardha": "maharashtra", "bhandara": "maharashtra", "gondia": "maharashtra",
    "gadchiroli": "maharashtra", "yavatmal": "maharashtra", "washim": "maharashtra",
    "hingoli": "maharashtra", "palghar": "maharashtra", "nandurbar": "maharashtra",
    "kalyan": "maharashtra", "dombivli": "maharashtra", "navi mumbai": "maharashtra",
    "panvel": "maharashtra", "mira-bhayandar": "maharashtra", "bhiwandi": "maharashtra",
    "ulhasnagar": "maharashtra", "malegaon": "maharashtra", "vasai": "maharashtra",
    "virar": "maharashtra", "ichalkaranji": "maharashtra", "bhusawal": "maharashtra",
    "baramati": "maharashtra", "shirdi": "maharashtra",

    # Karnataka
    "bengaluru": "karnataka", "bangalore": "karnataka", "mysuru": "karnataka", "mysore": "karnataka",
    "hubballi": "karnataka", "hubli": "karnataka", "dharwad": "karnataka", "mangaluru": "karnataka",
    "mangalore": "karnataka", "belagavi": "karnataka", "belgaum": "karnataka",
    "kalaburagi": "karnataka", "gulbarga": "karnataka", "davanagere": "karnataka",
    "ballari": "karnataka", "bellary": "karnataka", "vijayapura": "karnataka", "bijapur": "karnataka",
    "shivamogga": "karnataka", "shimoga": "karnataka", "tumakuru": "karnataka", "tumkur": "karnataka",
    "raichur": "karnataka", "bidar": "karnataka", "hassan": "karnataka", "mandya": "karnataka",
    "udupi": "karnataka", "kolar": "karnataka", "chikmagalur": "karnataka", "karwar": "karnataka",
    "ramanagara": "karnataka", "bagalkot": "karnataka", "gadag": "karnataka", "yadgir": "karnataka",
    "chamarajanagar": "karnataka", "koppal": "karnataka", "chikkaballapur": "karnataka",
    "kodagu": "karnataka", "madikeri": "karnataka", "haveri": "karnataka",

    # Tamil Nadu
    "chennai": "tamil nadu", "coimbatore": "tamil nadu", "madurai": "tamil nadu",
    "tiruchirappalli": "tamil nadu", "trichy": "tamil nadu", "salem": "tamil nadu",
    "tirunelveli": "tamil nadu", "tiruppur": "tamil nadu", "vellore": "tamil nadu",
    "erode": "tamil nadu", "thoothukudi": "tamil nadu", "tuticorin": "tamil nadu",
    "dindigul": "tamil nadu", "thanjavur": "tamil nadu", "ranipet": "tamil nadu",
    "sivakasi": "tamil nadu", "karur": "tamil nadu", "ooty": "tamil nadu",
    "udhagamandalam": "tamil nadu", "hosur": "tamil nadu", "nagercoil": "tamil nadu",
    "kanchipuram": "tamil nadu", "tiruvannamalai": "tamil nadu", "kumbakonam": "tamil nadu",
    "cuddalore": "tamil nadu", "kanyakumari": "tamil nadu", "namakkal": "tamil nadu",
    "pudukkottai": "tamil nadu", "nagapattinam": "tamil nadu", "ramanathapuram": "tamil nadu",
    "theni": "tamil nadu", "dharmapuri": "tamil nadu", "krishnagiri": "tamil nadu",
    "tiruvallur": "tamil nadu", "tirupathur": "tamil nadu", "chengalpattu": "tamil nadu",
    "kallakurichi": "tamil nadu", "tenkasi": "tamil nadu",

    # Telangana
    "hyderabad": "telangana", "warangal": "telangana", "nizamabad": "telangana",
    "karimnagar": "telangana", "ramagundam": "telangana", "khammam": "telangana",
    "mahbubnagar": "telangana", "nalgonda": "telangana", "adilabad": "telangana",
    "suryapet": "telangana", "miryalaguda": "telangana", "siddipet": "telangana",
    "jagtial": "telangana", "nirmal": "telangana", "kamareddy": "telangana",
    "kothagudem": "telangana", "mancherial": "telangana", "wanaparthy": "telangana",
    "nagarkurnool": "telangana", "sangareddy": "telangana", "medak": "telangana",
    "vikarabad": "telangana", "jangaon": "telangana", "secunderabad": "telangana",

    # Andhra Pradesh
    "visakhapatnam": "andhra pradesh", "vizag": "andhra pradesh", "vijayawada": "andhra pradesh",
    "guntur": "andhra pradesh", "nellore": "andhra pradesh", "kurnool": "andhra pradesh",
    "rajahmundry": "andhra pradesh", "tirupati": "andhra pradesh", "kakinada": "andhra pradesh",
    "kadapa": "andhra pradesh", "anantapur": "andhra pradesh", "vizianagaram": "andhra pradesh",
    "eluru": "andhra pradesh", "ongole": "andhra pradesh", "nandyal": "andhra pradesh",
    "machilipatnam": "andhra pradesh", "adoni": "andhra pradesh", "tenali": "andhra pradesh",
    "proddatur": "andhra pradesh", "chittoor": "andhra pradesh", "hindupur": "andhra pradesh",
    "bhimavaram": "andhra pradesh", "madanapalle": "andhra pradesh", "srikakulam": "andhra pradesh",

    # West Bengal
    "kolkata": "west bengal", "calcutta": "west bengal", "howrah": "west bengal",
    "durgapur": "west bengal", "asansol": "west bengal", "siliguri": "west bengal",
    "bardhaman": "west bengal", "burdwan": "west bengal", "malda": "west bengal",
    "baharampur": "west bengal", "berhampore": "west bengal", "habra": "west bengal",
    "kharagpur": "west bengal", "shantipur": "west bengal", "haldia": "west bengal",
    "raiganj": "west bengal", "krishnanagar": "west bengal", "nabadwip": "west bengal",
    "midnapore": "west bengal", "medinipur": "west bengal", "jalpaiguri": "west bengal",
    "balurghat": "west bengal", "bankura": "west bengal", "darjeeling": "west bengal",
    "purulia": "west bengal", "cooch behar": "west bengal", "alipurduar": "west bengal",

    # Odisha
    "bhubaneswar": "odisha", "cuttack": "odisha", "rourkela": "odisha", "berhampur": "odisha",
    "sambalpur": "odisha", "puri": "odisha", "balasore": "odisha", "bhadrak": "odisha",
    "baripada": "odisha", "jharsuguda": "odisha", "jeypore": "odisha", "bargarh": "odisha",
    "rayagada": "odisha", "bolangir": "odisha", "balangir": "odisha", "dhenkanal": "odisha",
    "angul": "odisha", "kendujhar": "odisha", "keonjhar": "odisha", "paradip": "odisha", "koraput": "odisha",

    # Punjab
    "ludhiana": "punjab", "amritsar": "punjab", "jalandhar": "punjab", "patiala": "punjab",
    "bathinda": "punjab", "mohali": "punjab", "sas nagar": "punjab", "hoshiarpur": "punjab",
    "batala": "punjab", "pathankot": "punjab", "moga": "punjab", "abohar": "punjab",
    "malerkotla": "punjab", "khanna": "punjab", "muktsar": "punjab", "barnala": "punjab",
    "firozpur": "punjab", "phagwara": "punjab", "kapurthala": "punjab", "rajpura": "punjab",
    "sangrur": "punjab", "fazilka": "punjab", "gurdaspur": "punjab",

    # Kerala
    "thiruvananthapuram": "kerala", "trivandrum": "kerala", "kochi": "kerala", "cochin": "kerala",
    "kozhikode": "kerala", "calicut": "kerala", "kollam": "kerala", "quilon": "kerala",
    "thrissur": "kerala", "kannur": "kerala", "alappuzha": "kerala", "alleppey": "kerala",
    "kottayam": "kerala", "palakkad": "kerala", "malappuram": "kerala", "kasaragod": "kerala",
    "wayanad": "kerala", "idukki": "kerala", "pathanamthitta": "kerala", "ernakulam": "kerala",

    # Assam
    "guwahati": "assam", "silchar": "assam", "dibrugarh": "assam", "jorhat": "assam",
    "nagaon": "assam", "tinsukia": "assam", "tezpur": "assam", "bongaigaon": "assam",
    "dhubri": "assam", "diphu": "assam", "karimganj": "assam", "sivasagar": "assam",

    # Uttar Pradesh
    "lucknow": "uttar pradesh", "kanpur": "uttar pradesh", "varanasi": "uttar pradesh",
    "agra": "uttar pradesh", "prayagraj": "uttar pradesh", "allahabad": "uttar pradesh",
    "ghaziabad": "uttar pradesh", "noida": "uttar pradesh", "meerut": "uttar pradesh",
    "bareilly": "uttar pradesh", "aligarh": "uttar pradesh", "moradabad": "uttar pradesh",
    "saharanpur": "uttar pradesh", "gorakhpur": "uttar pradesh", "ayodhya": "uttar pradesh",
    "jhansi": "uttar pradesh", "muzaffarnagar": "uttar pradesh", "mathura": "uttar pradesh",

    # Madhya Pradesh
    "bhopal": "madhya pradesh", "indore": "madhya pradesh", "jabalpur": "madhya pradesh",
    "gwalior": "madhya pradesh", "ujjain": "madhya pradesh", "sagar": "madhya pradesh",
    "rewa": "madhya pradesh", "satna": "madhya pradesh", "ratlam": "madhya pradesh",

    # Rajasthan
    "jaipur": "rajasthan", "jodhpur": "rajasthan", "kota": "rajasthan", "bikaner": "rajasthan",
    "ajmer": "rajasthan", "udaipur": "rajasthan", "bhilwara": "rajasthan", "alwar": "rajasthan",
    "sikar": "rajasthan", "bharatpur": "rajasthan", "pali": "rajasthan", "sri ganganagar": "rajasthan",

    # Bihar
    "patna": "bihar", "gaya": "bihar", "bhagalpur": "bihar", "muzaffarpur": "bihar",
    "purnia": "bihar", "darbhanga": "bihar", "bihar sharif": "bihar", "arrah": "bihar",
    "begusarai": "bihar", "katihar": "bihar",

    # Haryana
    "gurugram": "haryana", "gurgaon": "haryana", "faridabad": "haryana", "panipat": "haryana",
    "ambala": "haryana", "yamunanagar": "haryana", "rohtak": "haryana", "hisar": "haryana",
    "karnal": "haryana", "sonipat": "haryana",

    # Delhi
    "delhi": "delhi", "new delhi": "delhi"
}


@dataclass
class AyushmanData:
    source: str = "pdf"
    extraction_confidence: str = "high"
    name: str = ""
    yob: str = ""
    gender: str = ""
    pmjay_id: str = ""
    mobile: str = ""
    village_ward: str = ""
    subdivision_town: str = ""
    district: str = ""
    state: str = ""
    state_local: str = ""
    abha_number: str = ""
    ration_other_id: str = ""
    
    # State & Local Language Titles
    language_code: str = "hi"
    language_name: str = "Hindi"
    card_title_local: str = "आयुष्मान कार्ड"
    coverage_amount_local: str = "₹ ५ लाख तक"
    treatment_text_local: str = "मुफ्त उपचार"
    scheme_footer_local: str = "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना"
    scheme_footer_en: str = "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA"
    back_header_local: str = "स्वास्थ्य का वरदान, आयुष्मान"
    point1_local: str = ""
    point2_local: str = ""
    point3_local: str = ""
    app_download_local: str = "ऐप डाउनलोड करें"
    contact_label_local: str = "संपर्क करें"
    log_on_label_local: str = "लॉग ऑन करें"

    # Local Demographic Field Labels
    name_label: str = "नाम / NAME"
    yob_label: str = "जन्म वर्ष / YOB :"
    gender_label: str = "लिंग / GENDER :"
    village_ward_label: str = "गाँव/वार्ड - Village/Ward :"
    subdivision_town_label: str = "उपखंड/कस्बा - Subdivision/Town :"
    district_label: str = "ज़िला/District :"
    state_label: str = "राज्य:"
    pmjay_label: str = "PM-JAY ID:"
    ration_label: str = "Ration/Other ID:"

    # Images
    photo_png_base64: Optional[str] = None
    qr_base64: Optional[str] = None
    
    # Trace & Diagnostics
    errors: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)

    def to_json_safe_dict(self) -> dict:
        return asdict(self)


def _safe(fn: Any, *args: Any, default: Any = None, label: str = "", trace: Optional[list] = None, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        msg = f"{label or getattr(fn, '__name__', 'func')} failed: {type(e).__name__}: {e}"
        logger.warning(msg)
        if trace is not None:
            trace.append(msg)
        return default


def extract_ayushman_photo(doc: fitz.Document, trace: Optional[list] = None) -> Optional[str]:
    """
    Extracts the beneficiary portrait photo from the Ayushman PDF.
    Accurately discriminates between beneficiary photo, QR code, and full-card background templates.
    """
    try:
        if len(doc) == 0:
            return None

        candidates = []
        for page_idx in range(min(len(doc), 2)):
            page = doc[page_idx]
            images = _safe(page.get_images, full=True, default=[], label=f"ayushman_get_images_p{page_idx}", trace=trace) or []
            for img in (images if isinstance(images, list) else []):
                xref = img[0]
                base_image = _safe(doc.extract_image, xref, default=None, label="extract_image", trace=trace)
                if not base_image or not isinstance(base_image, dict):
                    continue
                img_bytes = base_image.get("image")
                if not img_bytes or not isinstance(img_bytes, bytes):
                    continue

                try:
                    pil_img = Image.open(io.BytesIO(img_bytes))
                    pil_img = ImageOps.exif_transpose(pil_img)
                    w, h = pil_img.size
                    if w < 50 or h < 50:
                        continue
                    area = w * h
                    if area < 3000:
                        continue
                    aspect = w / h if h else 0

                    # 1. Exclude full card background templates (CR80 card aspect ~1.55, large area)
                    # Card backgrounds are full-size high-res canvas (e.g. 1356x875, 677x436)
                    if area > 180000 or (w >= 500 and h >= 300) or (1.40 <= aspect <= 1.70 and area >= 90000):
                        continue

                    # 2. Exclude QR code images
                    is_qr = False
                    try:
                        qr_dec = zbar_decode(pil_img)
                        if qr_dec:
                            is_qr = True
                    except Exception:
                        pass

                    if is_qr:
                        continue

                    # 3. Score candidate
                    # Standard portrait photo: aspect between 0.55 and 0.95
                    score = 0
                    if 0.55 <= aspect <= 0.95:
                        score = 100
                    elif 1.15 <= aspect <= 1.50:  # 4:3 webcam photo (e.g. 300x225)
                        score = 70
                    elif 0.95 < aspect < 1.15:    # 1:1 square crop
                        score = 40
                    else:
                        score = 20

                    candidates.append((score, area, img_bytes))
                except Exception:
                    continue

        # Sort: highest score first, then largest area among same score
        candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
        if candidates:
            best_bytes = candidates[0][2]
            pil_best = Image.open(io.BytesIO(best_bytes))
            pil_best = ImageOps.exif_transpose(pil_best).convert("RGB")
            buf = io.BytesIO()
            pil_best.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        if trace is not None:
            trace.append(f"extract_ayushman_photo error: {e}")
    return None


def generate_fallback_qr(payload: str) -> Optional[str]:
    """Generates a sharp standard QR code when embedded QR is not available."""
    if not qrcode:
        return None
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        logger.warning(f"Fallback QR generation failed: {e}")
        return None


def is_valid_ayushman_value(val: Optional[str]) -> bool:
    """Checks if a string has actual information and is not a dash/NA placeholder."""
    if not val:
        return False
    v = str(val).strip()
    if not v:
        return False
    if v.upper() in [
        "NA", "N/A", "NOT AVAILABLE", "NOT_AVAILABLE", "NOTAVAILABLE",
        "NONE", "NULL", "UNDEFINED", "NIL", "N.A.", "N.A",
        "-", "–", "—", "―", "−", "--", "---", "----", "...",
        ":", "::", "SUBDIVISION/", "TOWN/", "VILLAGE/", "WARD/"
    ]:
        return False
    if re.fullmatch(r'[\s\-–—―−:\.\,/\\_\|\?\*#]+', v):
        return False
    return True


def parse_pmjay_qr_text(qr_raw_text: str) -> Dict[str, str]:
    """
    Universal parser for all known PM-JAY QR code payload variants.
    """
    lines = [l.strip() for l in qr_raw_text.splitlines() if l.strip()]
    res = {}
    if not lines:
        return res

    # 1. PM-JAY ID from first token
    first_tok = re.sub(r'[:\-]', '', lines[0]).strip()
    if re.match(r'^[A-Z0-9]{8,12}$', first_tok):
        res['pmjay_id'] = first_tok

    # 2. Extract deterministic pattern fields
    for l in lines:
        if re.match(r'^(19\d\d|20\d\d)$', l):
            res['yob'] = l
        elif re.match(r'^\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$', l):
            res['abha_number'] = l
        elif l.upper() in ['F', 'FEMALE', 'महिला', 'સ્ત્રી']:
            res['gender'] = 'FEMALE'
        elif l.upper() in ['M', 'MALE', 'पुरुष']:
            res['gender'] = 'MALE'
        elif re.match(r'^[6-9]\d{9}$', l):
            res['mobile'] = l
        elif re.match(r'^\d{4,28}$', l) and not re.match(r'^(19\d\d|20\d\d)$', l) and not re.match(r'^[6-9]\d{9}$', l):
            existing = res.get('ration_other_id', '')
            if len(l) >= 10:
                res['ration_other_id'] = l
            elif not existing:
                res['ration_other_id'] = l

    # 3. Positional State / Name / District resolution
    known_states = ['GUJARAT', 'MAHARASHTRA', 'UTTAR PRADESH', 'MADHYA PRADESH', 'BIHAR', 'RAJASTHAN', 'DELHI', 'HARYANA', 'JHARKHAND', 'CHHATTISGARH', 'UTTARAKHAND', 'HIMACHAL PRADESH', 'TELANGANA', 'ANDHRA PRADESH', 'TAMIL NADU', 'KARNATAKA', 'WEST BENGAL', 'ODISHA', 'PUNJAB', 'KERALA', 'ASSAM', 'GOA', 'TRIPURA', 'JAMMU AND KASHMIR', 'LADAKH', 'CHANDIGARH', 'PUDUCHERRY']
    for idx, l in enumerate(lines):
        l_u = l.upper()
        if l_u in known_states:
            res['state'] = l.title()
            
            # Name: preceding non-ID, non-NA line
            for p in range(idx - 1, -1, -1):
                prev_line = lines[p].strip()
                if is_valid_ayushman_value(prev_line) and not re.match(r'^[A-Z0-9]{8,12}:?$', prev_line) and not re.match(r'^\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$', prev_line):
                    if re.match(r'^[A-Za-z\s\.\']{3,50}$', prev_line):
                        res['name'] = prev_line.title()
                        break
            
            # District: line immediately after state
            if idx + 1 < len(lines):
                dist_cand = lines[idx + 1].strip()
                if is_valid_ayushman_value(dist_cand) and not dist_cand.isdigit():
                    res['district'] = dist_cand.title()
            
            # Village / Ward: line after district
            if idx + 2 < len(lines):
                vil_cand = lines[idx + 2].strip()
                if is_valid_ayushman_value(vil_cand) and not vil_cand.isdigit() and len(vil_cand) > 1:
                    res['village_ward'] = vil_cand.title()
            
            # Subdivision / Town: line after village
            if idx + 3 < len(lines):
                sub_cand = lines[idx + 3].strip()
                if is_valid_ayushman_value(sub_cand) and not sub_cand.isdigit() and len(sub_cand) > 1:
                    res['subdivision_town'] = sub_cand.title()
            break

    return res


def extract_ayushman_data(pdf_path: str, password: Optional[str] = None) -> AyushmanData:
    """Main extraction powerhouse for Ayushman / PM-JAY 2-page PDFs."""
    data = AyushmanData()
    trace: list[str] = []
    doc = None

    try:
        doc = fitz.open(pdf_path)
        if doc.needs_pass:
            if not password:
                data.source = "failed"
                data.errors.append("PDF is password protected. Please enter the password.")
                return data
            if not doc.authenticate(password):
                data.source = "failed"
                data.errors.append("Incorrect PDF password. Please enter the correct password.")
                return data

        # 1. Extract Photo
        photo_b64 = extract_ayushman_photo(doc, trace=trace)
        if photo_b64:
            data.photo_png_base64 = photo_b64
            trace.append("Beneficiary photo successfully extracted from Page 1.")

        # 2. Scan Rendered Pages for Demographic QR Code
        qr_raw_data = ""
        for page_idx in range(min(len(doc), 2)):
            page = doc[page_idx]
            pix = page.get_pixmap(dpi=300)
            pil_page = Image.open(io.BytesIO(pix.tobytes("png")))
            decs = zbar_decode(pil_page)
            if decs:
                # Find demographic QR (exclude app store download links)
                demo_decs = [d for d in decs if not d.data.decode("utf-8", errors="ignore").startswith("http")]
                target_dec = demo_decs[0] if demo_decs else decs[0]
                
                t_str = target_dec.data.decode("utf-8", errors="ignore")
                if not t_str.startswith("http"):
                    qr_raw_data = t_str

                # Crop original QR code directly from page render
                rect = target_dec.rect
                pad = 8
                x0 = max(0, rect.left - pad)
                y0 = max(0, rect.top - pad)
                x1 = min(pil_page.width, rect.left + rect.width + pad)
                y1 = min(pil_page.height, rect.top + rect.height + pad)
                
                qr_cropped = pil_page.crop((x0, y0, x1, y1))
                buf = io.BytesIO()
                qr_cropped.save(buf, format="PNG")
                data.qr_base64 = base64.b64encode(buf.getvalue()).decode("ascii")
                trace.append(f"QR code and demographic payload successfully decoded from Page {page_idx+1}.")
                if qr_raw_data:
                    break

        # If QR payload was found, populate fields from it
        if qr_raw_data:
            qr_dict = parse_pmjay_qr_text(qr_raw_data)
            if qr_dict.get("pmjay_id"):
                data.pmjay_id = qr_dict["pmjay_id"]
            if qr_dict.get("name"):
                data.name = qr_dict["name"]
            if qr_dict.get("yob"):
                data.yob = qr_dict["yob"]
            if qr_dict.get("gender"):
                data.gender = qr_dict["gender"]
            if qr_dict.get("state"):
                data.state = qr_dict["state"]
            if qr_dict.get("district"):
                data.district = qr_dict["district"]
            if qr_dict.get("subdivision_town"):
                data.subdivision_town = qr_dict["subdivision_town"]
            if qr_dict.get("village_ward"):
                data.village_ward = qr_dict["village_ward"]
            if qr_dict.get("mobile"):
                data.mobile = qr_dict["mobile"]
            if qr_dict.get("ration_other_id"):
                data.ration_other_id = qr_dict["ration_other_id"]
            if qr_dict.get("abha_number"):
                data.abha_number = qr_dict["abha_number"]

        # 3. Extract Text from Pages (supplement missing fields)
        page1_text = doc[0].get_text() if len(doc) > 0 else ""
        page2_text = doc[1].get_text() if len(doc) > 1 else ""
        full_text = page1_text + "\n" + page2_text
        lines = [l.strip() for l in page1_text.splitlines() if l.strip()]

        clean_lines = [
            l for l in lines 
            if not any(kw in l.upper() for kw in ["NATIONAL", "HEALTH", "AUTHORITY", "AYUSHMAN", "CARD", "PRADHAN", "MANTRI", "JAN", "AROGYA", "YOJANA", "GOVERNMENT", "INDIA", "सत्यमेव", "CARD GENERATED"])
        ]

        if not data.name:
            for idx, line in enumerate(lines):
                if re.match(r'^(?:NAME|Name|नाव|નામ|नाम|নাম|పేరు|பெயர்|ਨਾਮ|ಹೆಸರು|പേര്)\s*[:/]?$', line, re.IGNORECASE) and idx + 1 < len(lines):
                    next_line = lines[idx + 1]
                    if re.match(r'^[A-Za-z\s\.\']{3,50}$', next_line) and not any(kw in next_line.upper() for kw in ["YOB", "GENDER", "MOBILE", "DISTRICT", "STATE", "SURAT", "RAJKOT", "AHMEDABAD", "VADODARA"]):
                        data.name = next_line.strip().title()
                        break
            
            if not data.name and clean_lines:
                for cl in clean_lines:
                    if re.match(r'^[A-Za-z\s\.\']{4,50}$', cl) and not cl.isdigit():
                        if cl.upper() not in ["SURAT", "RAJKOT", "AHMEDABAD", "VADODARA", "GUJARAT", "MAHARASHTRA", "NOT AVAILABLE", "NA"]:
                            data.name = cl.strip().title()
                            break

        if not data.yob:
            m_yob = re.search(r'(?:YOB|DOB|Year of Birth|જન્મ વર્ષ|जन्म वर्ष)\s*[:/]?\s*(\d{4})', page1_text)
            if m_yob:
                data.yob = m_yob.group(1).strip()
            else:
                m_year = re.search(r'\b(19\d{2}|20\d{2})\b', page1_text)
                if m_year:
                    data.yob = m_year.group(1)

        if not data.gender:
            m_gender = re.search(r'(?:GENDER|Gender|જાતિ|लिंग)\s*[:/]?\s*(MALE|FEMALE|TRANSGENDER|Male|Female|पुरुष|महिला|\bF\b|\bM\b)', page1_text, re.IGNORECASE)
            if m_gender:
                g_str = m_gender.group(1).strip().upper()
                data.gender = "FEMALE" if (g_str in ["F", "FEMALE", "महिला"]) else "MALE"
            elif re.search(r'\bF\b', page1_text) or "FEMALE" in page1_text.upper():
                data.gender = "FEMALE"
            elif re.search(r'\bM\b', page1_text) or "MALE" in page1_text.upper():
                data.gender = "MALE"

        if not data.pmjay_id:
            name_words = set(data.name.upper().split()) if data.name else set()
            m_pmjay = re.search(r'(?:PM-?JAY\s*ID|PMJAY\s*ID|ID)\s*[:/]?\s*([A-Z0-9]{8,12})', page1_text, re.IGNORECASE)
            if m_pmjay:
                cand_id = m_pmjay.group(1).strip().upper()
                if cand_id not in name_words:
                    data.pmjay_id = cand_id

            if not data.pmjay_id:
                tokens = re.findall(r'\b([A-Z0-9]{8,12})\b', page1_text)
                for tok in tokens:
                    tok_u = tok.upper()
                    if tok_u != data.yob and tok_u not in name_words and any(c.isdigit() for c in tok_u) and any(c.isalpha() for c in tok_u):
                        if not any(kw in tok_u for kw in ["AYUSHMAN", "PRADHAN", "GUJARAT", "NATIONAL", "AUTHORITY"]):
                            data.pmjay_id = tok_u
                            break

        if not data.mobile:
            m_mob = re.search(r'(?:Mobile|Mob|Phone|મોબાઈલ|मोबाइल)\s*[:/]?\s*([6-9]\d{9})', full_text, re.IGNORECASE)
            if m_mob:
                cand_mob = m_mob.group(1).strip()
                if is_valid_ayushman_value(cand_mob):
                    data.mobile = cand_mob

        if not data.village_ward:
            m_vw = re.search(r'(?:^|\n)\s*(?:Village/Ward|Village|गाव/वार्ड|गाँव/वार्ड|ગામ/વોર્ડ|गाव|गाँव|ગામ|വാർഡ്|গ্রাম|గ్రామం|கிராமம்)\s*[:\-]\s*([^\n\r]+?)(?=\r?\n|$|Subdivision|Town|District)', page1_text, re.IGNORECASE)
            if m_vw:
                cand_vw = m_vw.group(1).split('\n')[0].strip()
                if is_valid_ayushman_value(cand_vw):
                    if not any(cand_vw.upper().startswith(kw) for kw in ["SUBDIVISION", "TOWN", "DISTRICT", "STATE"]):
                        data.village_ward = cand_vw

        if not data.subdivision_town:
            m_st = re.search(r'(?:^|\n)\s*(?:Subdivision/Town|Subdivision|Town|तालुका/शहर|उपखंड/कस्बा|तहसील/शहर|तालुका|તાલુકો/શહેર|તાલુકા/શહેર|মহকুমা|సబ్ డివిజన్)\s*[:\-]\s*([^\n\r]+?)(?=\r?\n|$|District|જિલ્લો|જિલ્લા)', page1_text, re.IGNORECASE)
            if m_st:
                cand_st = m_st.group(1).split('\n')[0].strip()
                if is_valid_ayushman_value(cand_st):
                    if not any(cand_st.upper().startswith(kw) for kw in ["DISTRICT", "STATE", "VILLAGE"]):
                        data.subdivision_town = cand_st

        if not data.district:
            m_dist = re.search(r'(?:^|\n)\s*(?:District|जिल्हा|ज़िला|जिला|જિલ્લો|જિલ્લા|জেলা|జిల్లా|மாவட்டம்|ਜ਼ਿਲ੍ਹਾ|ಜಿಲ್ಲೆ|ജില്ല)\s*[:/\-]\s*([A-Za-z\s]+?)(?=\r?\n|$|State|રાજ્ય|Mobile|PM-JAY)', page1_text, re.IGNORECASE)
            if m_dist:
                cand_dist = m_dist.group(1).split('\n')[0].strip().title()
                if is_valid_ayushman_value(cand_dist):
                    data.district = cand_dist

        if not data.state:
            m_state = re.search(r'(?:^|\n)\s*(?:State|राज्य|રાજ્ય|రాష్ట్రం|மாநிலம்|রাজ্য|ਰਾਜ|ರಾಜ್ಯ|സംസ്ഥാനം)\s*[:/\-]\s*([A-Za-z\s]+?)(?=\r?\n|$|Mobile|PM-JAY|ABHA)', page1_text, re.IGNORECASE)
            if m_state:
                cand_state = m_state.group(1).split('\n')[0].strip().title()
                if is_valid_ayushman_value(cand_state):
                    data.state = cand_state

        if not data.abha_number:
            m_abha = re.search(r'(?:ABHA\s*(?:No|Number)?|આભા)\s*[:/]?\s*(\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})', full_text, re.IGNORECASE)
            if m_abha:
                cand_abha = m_abha.group(1).strip()
                if is_valid_ayushman_value(cand_abha):
                    data.abha_number = cand_abha
            else:
                m_raw_abha = re.search(r'\b(\d{2}-\d{4}-\d{4}-\d{4})\b', full_text)
                if m_raw_abha:
                    data.abha_number = m_raw_abha.group(1).strip()

        if not data.ration_other_id:
            m_ration = re.search(r'(?:Ration/Other\s*ID|Ration\s*ID|રાશન)\s*[:/]?\s*([A-Z0-9\-/]+)', full_text, re.IGNORECASE)
            if m_ration:
                cand_ration = m_ration.group(1).strip()
                if is_valid_ayushman_value(cand_ration):
                    data.ration_other_id = cand_ration

        # 3b. Positional / Unassigned Line Extraction for Label-less PDFs (JasperReports format etc.)
        # In Gujarat and other JasperReports cards, demographic values are overlaid as clean lines without field labels.
        if not (data.village_ward and data.subdivision_town and data.district):
            known_tokens = set()
            if data.name:
                known_tokens.add(data.name.upper())
                for part in data.name.upper().split():
                    known_tokens.add(part)
            if data.yob:
                known_tokens.add(data.yob)
            if data.gender:
                known_tokens.add(data.gender.upper())
                known_tokens.add("M")
                known_tokens.add("F")
            if data.pmjay_id:
                known_tokens.add(data.pmjay_id.upper())
            if data.abha_number:
                known_tokens.add(data.abha_number)
                known_tokens.add(re.sub(r'[\s\-]', '', data.abha_number))
            if data.mobile:
                known_tokens.add(data.mobile)
            if data.ration_other_id:
                known_tokens.add(data.ration_other_id.upper())

            unassigned_lines: list[str] = []
            for l in lines:
                l_s = l.strip()
                if not l_s:
                    continue
                l_u = l_s.upper()
                if l_u in known_tokens or any(tok == l_u for tok in known_tokens):
                    continue
                if any(kw in l_u for kw in [
                    "CARD GENERATED", "GENERATED ON", "PAGE 1", "PAGE 2",
                    "NATIONAL HEALTH AUTHORITY", "AYUSHMAN BHARAT", "PRADHAN MANTRI",
                    "JAN AROGYA", "GOVERNMENT OF INDIA", "GOVT OF INDIA", "ITEXT", "JASPERREPORTS"
                ]):
                    continue
                if re.match(r'^(?:NAME|YOB|DOB|GENDER|SEX|MALE|FEMALE|MOBILE|PM-?JAY|ABHA|ID|STATE|DISTRICT)\b', l_u):
                    continue
                unassigned_lines.append(l_s)

            # 1. State line detection in unassigned lines
            for u in list(unassigned_lines):
                u_clean = u.strip().lower()
                if u_clean in STATE_LANGUAGE_MAP and u_clean != "default_hindi":
                    if not data.state:
                        data.state = u.strip().title()
                    unassigned_lines.remove(u)
                    break

            # 2. Village / Ward line detection
            if not data.village_ward:
                for u in list(unassigned_lines):
                    u_u = u.upper()
                    if any(kw in u_u for kw in [
                        "WARD", "VILLAGE", "GAON", "GRAM", "M CORP", "MUNICIPAL",
                        "NAGAR", "COLONY", "SECTOR", "BLOCK", "FLAT", "HOUSE",
                        "STREET", "ROAD", "NO.", "(M CORP.)", "RURAL", "URBAN"
                    ]):
                        data.village_ward = u.strip()
                        unassigned_lines.remove(u)
                        break

            # 3. District / Subdivision resolution using DISTRICT_STATE_MAP
            for u in list(unassigned_lines):
                u_clean = re.sub(r'[^a-zA-Z\s]', '', u).strip().lower()
                if u_clean in DISTRICT_STATE_MAP:
                    mapped_state = DISTRICT_STATE_MAP[u_clean].title()
                    if not data.district:
                        data.district = u.strip().title()
                        if not data.state:
                            data.state = mapped_state
                        unassigned_lines.remove(u)
                    elif not data.subdivision_town:
                        data.subdivision_town = u.strip().title()
                        if not data.state:
                            data.state = mapped_state
                        unassigned_lines.remove(u)

            # 4. Fill remaining missing address fields from leftover unassigned lines
            if unassigned_lines:
                if not data.village_ward:
                    data.village_ward = unassigned_lines.pop(0).strip()
                elif not data.subdivision_town:
                    data.subdivision_town = unassigned_lines.pop(0).strip().title()
                elif not data.district:
                    data.district = unassigned_lines.pop(0).strip().title()

            # 5. Clean & cross-fill subdivision / district
            if not data.subdivision_town and data.district:
                data.subdivision_town = data.district
            elif not data.district and data.subdivision_town:
                data.district = data.subdivision_town

        # 4. State & Local Language Scheme Mapping
        detected_lang = None
        state_key = (data.state or "").lower().strip()
        
        if state_key in STATE_LANGUAGE_MAP and state_key != "default_hindi":
            detected_lang = STATE_LANGUAGE_MAP[state_key]

        # Resolution Layer A: Check district in DISTRICT_STATE_MAP
        if not detected_lang and data.district:
            d_clean = re.sub(r'[^a-zA-Z\s]', '', data.district).strip().lower()
            if d_clean in DISTRICT_STATE_MAP:
                s_name = DISTRICT_STATE_MAP[d_clean]
                if s_name in STATE_LANGUAGE_MAP:
                    detected_lang = STATE_LANGUAGE_MAP[s_name]
                    data.state = s_name.title()

        # Resolution Layer B: Check subdivision_town in DISTRICT_STATE_MAP
        if not detected_lang and data.subdivision_town:
            st_clean = re.sub(r'[^a-zA-Z\s]', '', data.subdivision_town).strip().lower()
            if st_clean in DISTRICT_STATE_MAP:
                s_name = DISTRICT_STATE_MAP[st_clean]
                if s_name in STATE_LANGUAGE_MAP:
                    detected_lang = STATE_LANGUAGE_MAP[s_name]
                    data.state = s_name.title()

        # Resolution Layer C: Check village_ward for city keywords
        if not detected_lang and data.village_ward:
            vw_lower = data.village_ward.lower()
            for city_key, s_name in DISTRICT_STATE_MAP.items():
                if len(city_key) >= 4 and city_key in vw_lower:
                    if s_name in STATE_LANGUAGE_MAP:
                        detected_lang = STATE_LANGUAGE_MAP[s_name]
                        data.state = s_name.title()
                        break

        # Resolution Layer D: Check full text for state names
        if not detected_lang:
            text_lower = full_text.lower()
            for s_key in STATE_LANGUAGE_MAP:
                if s_key != "default_hindi" and s_key in text_lower:
                    detected_lang = STATE_LANGUAGE_MAP[s_key]
                    data.state = s_key.title()
                    break

        # Resolution Layer E: Check full text for any city in DISTRICT_STATE_MAP
        if not detected_lang:
            text_lower = full_text.lower()
            for city_key, s_name in DISTRICT_STATE_MAP.items():
                if len(city_key) >= 4 and re.search(r'\b' + re.escape(city_key) + r'\b', text_lower):
                    if s_name in STATE_LANGUAGE_MAP:
                        detected_lang = STATE_LANGUAGE_MAP[s_name]
                        data.state = s_name.title()
                        break

        # Resolution Layer F: State helplines & scheme branding
        if not detected_lang:
            if any(kw in full_text for kw in ["1800 233 1022", "18002331022", "MUKHYAMANTRI AMRUTUM", "AMRUTUM", "MAA YOJANA"]):
                detected_lang = STATE_LANGUAGE_MAP["gujarat"]
                data.state = "Gujarat"
            elif any(kw in full_text for kw in ["MJPJAY", "MAHATMA JYOTIRAO PHULE", "महाराष्ट्र", "मुंबई", "धुळे", "पुणे", "नासिक"]):
                detected_lang = STATE_LANGUAGE_MAP["maharashtra"]
                data.state = "Maharashtra"

        # Resolution Layer G: Unicode script detection
        if not detected_lang:
            if re.search(r'[\u0A80-\u0AFF]', full_text):
                detected_lang = STATE_LANGUAGE_MAP["gujarat"]
                data.state = "Gujarat"
            elif re.search(r'[\u0C00-\u0C7F]', full_text):
                detected_lang = STATE_LANGUAGE_MAP["telangana"]
                data.state = "Telangana"
            elif re.search(r'[\u0B80-\u0BFF]', full_text):
                detected_lang = STATE_LANGUAGE_MAP["tamil nadu"]
                data.state = "Tamil Nadu"
            elif re.search(r'[\u0C80-\u0CFF]', full_text):
                detected_lang = STATE_LANGUAGE_MAP["karnataka"]
                data.state = "Karnataka"
            elif re.search(r'[\u0980-\u09FF]', full_text):
                detected_lang = STATE_LANGUAGE_MAP["west bengal"]
                data.state = "West Bengal"
            elif re.search(r'[\u0B00-\u0B7F]', full_text):
                detected_lang = STATE_LANGUAGE_MAP["odisha"]
                data.state = "Odisha"
            elif re.search(r'[\u0A00-\u0A7F]', full_text):
                detected_lang = STATE_LANGUAGE_MAP["punjab"]
                data.state = "Punjab"
            elif re.search(r'[\u0D00-\u0D7F]', full_text):
                detected_lang = STATE_LANGUAGE_MAP["kerala"]
                data.state = "Kerala"
            elif re.search(r'[\u0900-\u097F]', full_text):
                if any(kw in full_text for kw in ["महाराष्ट्र", "मुंबई", "धुळे", "पुणे", "नासिक", "MJPJAY", "ज्योतिराव", "गाव", "जिल्हा", "तालुका", "नाव"]):
                    detected_lang = STATE_LANGUAGE_MAP["maharashtra"]
                    data.state = "Maharashtra"
                else:
                    detected_lang = STATE_LANGUAGE_MAP["default_hindi"]
                    data.state = "Uttar Pradesh"

        # Resolution Layer H: Name heuristics
        if not detected_lang:
            if any(kw in data.name.upper() for kw in ["BHAI", "BEN", "PATEL", "SHAH", "SOLANKI", "PARMAR", "JADAV", "RATHOD", "CHAUHAN", "MAKWANA", "SURAT", "RAJKOT"]):
                detected_lang = STATE_LANGUAGE_MAP["gujarat"]
                data.state = "Gujarat"

        if not detected_lang:
            detected_lang = STATE_LANGUAGE_MAP["default_hindi"]
            if not data.state:
                data.state = "India"

        # Apply mapped values
        data.language_code = detected_lang["lang_code"]
        data.language_name = detected_lang["lang_name"]
        data.state_local = detected_lang.get("state_local", data.state)
        data.card_title_local = detected_lang["card_title_local"]
        data.coverage_amount_local = detected_lang["coverage_amount_local"]
        data.treatment_text_local = detected_lang["treatment_text_local"]
        data.scheme_footer_local = detected_lang["scheme_footer_local"]
        data.scheme_footer_en = detected_lang.get("scheme_footer_en", "AYUSHMAN BHARAT PRADHAN MANTRI JAN AROGYA YOJANA")
        data.back_header_local = detected_lang["back_header_local"]
        data.app_download_local = detected_lang["app_download_local"]
        data.contact_label_local = detected_lang["contact_label_local"]
        data.log_on_label_local = detected_lang["log_on_label_local"]
        data.point1_local = detected_lang.get("point1_local", "")
        data.point2_local = detected_lang.get("point2_local", "")
        data.point3_local = detected_lang.get("point3_local", "")

        # Local Demographic Field Labels
        data.name_label = detected_lang.get("name_label", "नाम / NAME")
        data.yob_label = detected_lang.get("yob_label", "जन्म वर्ष / YOB :")
        data.gender_label = detected_lang.get("gender_label", "लिंग / GENDER :")
        data.village_ward_label = detected_lang.get("village_ward_label", "गाँव/वार्ड - Village/Ward :")
        data.subdivision_town_label = detected_lang.get("subdivision_town_label", "उपखंड/कस्बा - Subdivision/Town :")
        data.district_label = detected_lang.get("district_label", "ज़िला/District :")
        data.state_label = detected_lang.get("state_label", "राज्य:")
        data.pmjay_label = detected_lang.get("pmjay_label", "PM-JAY ID:")
        data.ration_label = detected_lang.get("ration_label", "Ration/Other ID:")

        # Fallback QR code generation if needed
        if not data.qr_base64:
            payload = qr_raw_data if qr_raw_data else f"PMJAY-{data.pmjay_id or 'AYUSHMAN'}|NAME:{data.name}|YOB:{data.yob}|GENDER:{data.gender}|STATE:{data.state}"
            data.qr_base64 = generate_fallback_qr(payload)
            if data.qr_base64:
                trace.append("Crisp QR code generated for PM-JAY payload.")

        data.trace = trace
        return data

    except Exception as e:
        logger.error(f"Ayushman extraction fatal error: {e}")
        data.source = "failed"
        data.errors.append(str(e))
        data.trace = trace
        return data
    finally:
        if doc:
            try:
                doc.close()
            except Exception:
                pass

