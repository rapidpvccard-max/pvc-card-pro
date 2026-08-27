import json
import re
from datetime import datetime, date


def _calculate_age_from_dob(dob_str: str) -> int:
    """
    Calculate age in years from a DOB string.
    Supports formats: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, YYYY/MM/DD
    Returns -1 if parsing fails.
    """
    if not dob_str:
        return -1
    dob_str = dob_str.strip()
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d", "%d %m %Y"]
    for fmt in formats:
        try:
            dob = datetime.strptime(dob_str, fmt).date()
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age
        except ValueError:
            continue
    return -1


def map_aadhaar_data(engine_data: dict) -> dict:
    """
    Maps the raw output of extract_aadhaar_data to a canonical structure for the PVC Card Generator.
    """
    def get_str(key: str) -> str:
        val = engine_data.get(key)
        return str(val).strip() if val else ""
        
    def has_field(key: str) -> bool:
        return bool(engine_data.get(key))

    # Basic fields
    full_name = get_str("full_name")
    dob = get_str("dob")
    gender = get_str("gender")
    
    # Address assembly — matches original Aadhaar PDF line-break pattern exactly:
    #
    #   Line 1: care_of, house, landmark, vtc, location, post_office, sub_district, district
    #   Line 2: state - pincode
    #
    # This is the SAME two-line structure used by UIDAI on the physical Aadhaar card.

    # Line 1: all locality/area details
    line1_parts = []
    for part in ["care_of", "house", "landmark", "vtc", "location", "post_office", "sub_district", "district"]:
        val = get_str(part)
        if val:
            line1_parts.append(val)

    # Line 2: state - pincode (exactly like original PDF: "Gujarat - 394210")
    line2_parts = []
    state_val = get_str("state")
    pin_val = get_str("pincode")
    if state_val and pin_val:
        line2_parts.append(f"{state_val} - {pin_val}")
    elif state_val:
        line2_parts.append(state_val)
    elif pin_val:
        line2_parts.append(pin_val)

    line1 = ", ".join(line1_parts)
    line2 = ", ".join(line2_parts)

    # full_html: HTML version with <br> for exact 2-line format matching original Aadhaar PDF.
    # Works for ALL states and ALL languages — UIDAI QR fields are nationally standardized.
    # Empty fields are gracefully skipped, so cards with fewer fields still render correctly.
    if line1 and line2:
        full_address_html = f"{line1},<br>{line2}"
    elif line1:
        full_address_html = line1
    elif line2:
        full_address_html = line2
    else:
        full_address_html = ""

    # full_plain: plain text version (for fallback/logging)
    full_address = ", ".join(filter(None, [line1, line2]))
    
    # Local language fields
    local_name = get_str("local_full_name")
    local_address = get_str("local_address")
    local_script = get_str("local_script")
    
    # Strip duplicate leading address prefix (e.g., 'સરનામું :', 'पता :')
    if local_address:
        local_address = re.sub(r'^(સરનામું|पता|पत्ता|ঠিকানা|முகவரி|చిరునామా|విళాస|ವಿಳಾಸ|മേൽവിലാസം|ਪਤਾ|ଠିକଣା|ঠিকনা|پتہ|Address)\s*[:\-]?\s*', '', local_address, flags=re.IGNORECASE).strip()

    # If local_name is identical to full_name (e.g. English name on both lines), clear local_name
    if local_name.lower().strip() == full_name.lower().strip():
        local_name = ""
    
    # Map script code to canonical language name
    SCRIPT_MAP = {
        "devanagari": ("hi", "Hindi"),
        "gujarati":   ("gu", "Gujarati"),
        "bengali":    ("bn", "Bengali"),
        "tamil":      ("ta", "Tamil"),
        "telugu":     ("te", "Telugu"),
        "kannada":    ("kn", "Kannada"),
        "malayalam":  ("ml", "Malayalam"),
        "oriya":      ("or", "Odia"),
        "gurmukhi":   ("pa", "Punjabi"),
        "urdu":       ("ur", "Urdu"),
        "assamese":   ("as", "Assamese"),
    }

    if not local_script or local_script == "latin":
        # Try detecting script from local text if available
        sample_text = f"{local_name} {local_address}"
        for ch in sample_text:
            code = ord(ch)
            if 0x0A80 <= code <= 0x0AFF:
                local_script = "gujarati"; break
            elif 0x0900 <= code <= 0x097F:
                local_script = "devanagari"; break
            elif 0x0980 <= code <= 0x09FF:
                local_script = "bengali"; break
            elif 0x0B80 <= code <= 0x0BFF:
                local_script = "tamil"; break
            elif 0x0C00 <= code <= 0x0C7F:
                local_script = "telugu"; break
            elif 0x0C80 <= code <= 0x0CFF:
                local_script = "kannada"; break
            elif 0x0D00 <= code <= 0x0D7F:
                local_script = "malayalam"; break
            elif 0x0B00 <= code <= 0x0B7F:
                local_script = "oriya"; break
            elif 0x0A00 <= code <= 0x0A7F:
                local_script = "gurmukhi"; break

    lang_entry = SCRIPT_MAP.get(local_script.lower() if local_script else "", ("hi", "Hindi"))
    language_code = lang_entry[0]
    language_name = lang_entry[1]

    # Aadhaar number / VID / mobile — prefer FULL numbers from PDF text over masked QR field
    aadhaar_number = get_str("masked_number")  # may be "XXXX XXXX 4112" — partial
    vid_number = get_str("reference_id")
    mobile_number = ""

    pdf_path = engine_data.get("__pdf_path__", "")
    pdf_password = engine_data.get("__pdf_password__", None)

    def _scan_pdf_text():
        try:
            import fitz
            doc = fitz.open(pdf_path)
            if doc.needs_pass and pdf_password:
                doc.authenticate(pdf_password)
            parts = [page.get_text("text") for page in doc[:3]]
            doc.close()
            return "\n".join(parts)
        except Exception:
            return ""

    if pdf_path:
        pdf_text = _scan_pdf_text()
        if pdf_text:
            # --- VID: label-anchored 16-digit ---
            m = re.search(
                r'VID\s*[:\-]?\s*(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})',
                pdf_text, re.IGNORECASE
            )
            if m:
                raw = re.sub(r'[\s\-]', '', m.group(1))
                vid_number = f"{raw[0:4]} {raw[4:8]} {raw[8:12]} {raw[12:16]}"

            # --- Aadhaar: label-anchored 12-digit ---
            m = re.search(
                r'(?:Aadhaar|Aadhar|UIDAI|आधार)\s*(?:No|Number|नंबर|Card)?\s*[:\.\-]?\s*(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})',
                pdf_text, re.IGNORECASE
            )
            if m:
                raw = re.sub(r'[\s\-]', '', m.group(1))
                aadhaar_number = f"{raw[0:4]} {raw[4:8]} {raw[8:12]}"
            else:
                # Fallback: spaced 12-digit NOT immediately followed by more space+digits (i.e. not VID)
                m = re.search(r'\b(\d{4}\s\d{4}\s\d{4})(?!\s\d{4})\b', pdf_text)
                if m:
                    aadhaar_number = m.group(1)

            # --- Mobile: label-anchored 10-digit ---
            m = re.search(
                r'(?:Mobile|Mob|Cell|Phone|Ph)\s*[.:\-]?\s*([6-9]\d{9})\b',
                pdf_text, re.IGNORECASE
            )
            if m:
                mobile_number = m.group(1)


    # --- Baal Aadhaar detection ---
    age = _calculate_age_from_dob(dob)
    is_baal_aadhaar = (age >= 0 and age < 5)

    return {
        "success": True,
        "document_type": "aadhaar",
        "language": {
            "name": language_name,
            "code": language_code
        },
        "is_baal_aadhaar": is_baal_aadhaar,
        "person": {
            "name": full_name,
            "name_local": local_name,
            "dob": dob,
            "gender": gender,
            "gender_local": "",
            "age": age
        },
        "contact": {
            "mobile": mobile_number
        },
        "identity": {
            "aadhaar_number": aadhaar_number,
            "enrolment_number": vid_number
        },
        "address": {
            "full": full_address,           # plain text (comma separated, no HTML)
            "full_html": full_address_html,  # HTML with <br> for exact line breaks matching original Aadhaar PDF
            "local": local_address
        },
        "photo": {
            "available": has_field("photo_jp2_base64") or has_field("photo_png_base64"),
            "base64": engine_data.get("photo_png_base64") or engine_data.get("photo_jp2_base64") or ""
        },
        "qr": {
            "available": engine_data.get("source") == "qr",
            "base64": engine_data.get("qr_base64") or ""
        },
        "metadata": {
            "source": get_str("source"),
            "extraction_confidence": get_str("extraction_confidence")
        }
    }


def map_ayushman_data(engine_data: dict) -> dict:
    """
    Maps the raw output of extract_ayushman_data to a canonical structure for the Ayushman PVC Card Generator.
    Ensures missing or dash/line/placeholder fields are cleanly set to "" so templates can default to "Not Available".
    """
    def get_str(key: str) -> str:
        val = engine_data.get(key)
        if not val:
            return ""
        val_str = str(val).strip()
        if val_str.upper() in [
            "NA", "N/A", "NOT AVAILABLE", "NOT_AVAILABLE", "NOTAVAILABLE",
            "NONE", "NULL", "UNDEFINED", "NIL", "N.A.", "N.A",
            "-", "–", "—", "―", "−", "--", "---", "----", "...",
            ":", "::", "SUBDIVISION/", "TOWN/", "VILLAGE/", "WARD/"
        ]:
            return ""
        if re.fullmatch(r'[\s\-–—―−:\.\,/\\_\|\?\*#]+', val_str):
            return ""
        return val_str

    return {
        "success": True,
        "document_type": "ayushman",
        "language": {
            "name": get_str("language_name") or "English",
            "code": get_str("language_code") or "en"
        },
        "person": {
            "name": get_str("name"),
            "yob": get_str("yob"),
            "gender": get_str("gender"),
            "village_ward": get_str("village_ward"),
            "subdivision_town": get_str("subdivision_town"),
            "district": get_str("district"),
            "state": get_str("state"),
            "state_local": get_str("state_local")
        },
        "contact": {
            "mobile": get_str("mobile")
        },
        "identity": {
            "pmjay_id": get_str("pmjay_id"),
            "abha_number": get_str("abha_number"),
            "ration_other_id": get_str("ration_other_id")
        },
        "scheme": {
            "card_title_local": get_str("card_title_local") or "આયુષ્માન કાર્ડ",
            "coverage_amount_local": get_str("coverage_amount_local") or "₹ ૫ લાખ સુધીની",
            "treatment_text_local": get_str("treatment_text_local") or "મફત સારવાર",
            "scheme_footer_local": get_str("scheme_footer_local") or "આયુષ્માન ભારત પ્રધાનમંત્રી જન આરોગ્ય યોજના",
            "back_header_local": get_str("back_header_local") or "સ્વાસ્થ્યનું વરદાન, આયુષ્માન",
            "point1_local": get_str("point1_local"),
            "point2_local": get_str("point2_local"),
            "point3_local": get_str("point3_local"),
            "app_download_local": get_str("app_download_local") or "એપ ડાઉનલોડ કરો",
            "contact_label_local": get_str("contact_label_local") or "સંપર્ક કરો",
            "log_on_label_local": get_str("log_on_label_local") or "લોગ ઓન કરો"
        },
        "photo": {
            "available": bool(engine_data.get("photo_png_base64")),
            "base64": engine_data.get("photo_png_base64") or ""
        },
        "qr": {
            "available": bool(engine_data.get("qr_base64")),
            "base64": engine_data.get("qr_base64") or ""
        },
        "metadata": {
            "source": get_str("source"),
            "extraction_confidence": get_str("extraction_confidence")
        }
    }

