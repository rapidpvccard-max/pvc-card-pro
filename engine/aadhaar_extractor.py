"""
aadhaar_extractor.py  (v3 -- hardened, "never crash" powerhouse edition)
---------------------------------------------------------------------
Deterministic, AI-free extraction of Aadhaar demographic data -- Name,
DOB, Gender, Address, Photo -- from an e-Aadhaar PDF's QR code and text
layer.

DESIGN PRINCIPLES FOR THIS VERSION:
  1. NEVER raise an unhandled exception from the public entry points
     (extract_aadhaar_data, extract_local_language_fields). Every stage
     is wrapped so a single bad PDF can't take down the caller -- you
     always get back a structured result with a clear status/confidence,
     never a crash.
  2. Prefer STRUCTURED CONFIDENCE SCORES (0-100) over binary success/fail
     flags wherever a judgment call is involved, so the caller (route.ts)
     can decide its own threshold for trusting the data vs falling back.
  3. Local-name/address block selection uses SCORING, not "take the first
     matching block" -- this avoids the "Enrolment No. header line got
     picked as the name" class of bug, and generalizes better to PDFs
     we haven't seen yet.
  4. Corruption detection is broad and pattern-based (control chars,
     mis-mapped Latin letters, floating matras, excessive fragmentation)
     -- checked independently on every candidate block, not just the
     final chosen one, so scoring can also prefer non-corrupted candidates.

Dependencies:
    pip install pymupdf pyzbar pillow pdfplumber
    system: libzbar0, and libopenjp2 for JPEG2000 photo decoding
        apt install libzbar0 libopenjp2-7
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import re
import zlib
from dataclasses import dataclass, asdict, field
from typing import Optional, Any, Callable, TypeVar, List, Dict, Union

import fitz  # PyMuPDF
from PIL import Image
from pyzbar.pyzbar import decode as zbar_decode

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

logger = logging.getLogger("aadhaar_extractor")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------------

@dataclass
class AadhaarData:
    source: str = "unknown"          # "qr" | "text_layer" | "failed"
    version: str = ""
    full_name: str = ""
    dob: str = ""
    gender: str = ""
    care_of: str = ""
    district: str = ""
    landmark: str = ""
    house: str = ""
    location: str = ""
    pincode: str = ""
    post_office: str = ""
    state: str = ""
    sub_district: str = ""
    vtc: str = ""
    masked_number: str = ""
    reference_id: str = ""
    local_full_name: str = ""
    local_address: str = ""
    local_script: str = ""
    local_confidence: int = 0        # 0-100, see extract_local_language_fields
    photo_bytes: Optional[bytes] = None      # JPEG2000 raw bytes
    photo_png_bytes: Optional[bytes] = None  # converted to PNG for easy use
    extraction_confidence: str = "low"
    errors: list = field(default_factory=list)
    trace: list = field(default_factory=list)  # step-by-step diagnostic log

    def to_json_safe_dict(self) -> dict:
        d = asdict(self)
        import base64
        if d.get("photo_bytes"):
            d["photo_jp2_base64"] = base64.b64encode(d["photo_bytes"]).decode("ascii")
        if d.get("photo_png_bytes"):
            d["photo_png_base64"] = base64.b64encode(d["photo_png_bytes"]).decode("ascii")
        d.pop("photo_bytes", None)
        d.pop("photo_png_bytes", None)
        return d


def _safe(fn: Any, *args: Any, default: Any = None, label: str = "", trace: Optional[list] = None, **kwargs: Any) -> Any:
    """Run fn(*args, **kwargs), catching ANY exception and returning
    `default` instead of propagating. Every risky operation in this
    module should be routed through this so a single bad PDF/malformed
    field never crashes the whole extraction."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        msg = f"{label or getattr(fn, '__name__', 'func')} failed: {type(e).__name__}: {e}"
        logger.warning(msg)
        if trace is not None:
            trace.append(msg)
        return default


# ---------------------------------------------------------------------------
# Step 0: extract the person's portrait photo directly from the PDF
# (This is the LARGE, proper photo embedded in the PDF — not the tiny
#  JPEG2000 face crop inside the QR code)
# ---------------------------------------------------------------------------

def extract_portrait_photo_from_pdf(pdf_path: str, password: Optional[str] = None,
                                     trace: Optional[list] = None) -> Optional[bytes]:
    """Scan the PDF for a portrait-orientation embedded image (the actual
    person photo, not the QR code).  Returns PNG bytes of the best candidate,
    or None if nothing suitable is found."""
    try:
        doc = fitz.open(pdf_path)
        try:
            if doc.needs_pass:
                if not password:
                    return None
                if not doc.authenticate(password):
                    return None

            best_img_bytes = None
            best_area = 0

            for page_num in range(min(len(doc), 3)):  # scan first 3 pages max
                page = doc[page_num]
                images = _safe(page.get_images, full=True, default=[],
                               label=f"portrait_get_images(page {page_num})", trace=trace) or []
                for img in (images if isinstance(images, list) else []):
                    xref = img[0]
                    base_image = _safe(doc.extract_image, xref, default=None,
                                       label="portrait_extract_image", trace=trace)
                    if not base_image or not isinstance(base_image, dict):
                        continue
                    img_bytes = base_image.get("image")
                    if not img_bytes:
                        continue

                    def _classify_portrait():
                        pil_img = Image.open(io.BytesIO(img_bytes))
                        w, h = pil_img.size
                        aspect = w / h if h else 0
                        return w, h, aspect, pil_img.mode

                    dims = _safe(_classify_portrait, default=None,
                                 label="classify portrait", trace=trace)
                    if dims is None:
                        continue
                    w, h, aspect, mode = dims

                    # Portrait photo criteria:
                    # - NOT square (aspect < 0.85 — taller than wide)
                    # - Minimum size (at least 60px wide, 60px tall)
                    # - Not tiny icon (at least 3600 px²)
                    # - Not too large (max 1500px in any dimension — logos etc.)
                    area = w * h
                    if (aspect < 0.85 and          # portrait orientation
                            w >= 60 and h >= 60 and  # minimum size
                            area >= 3600 and          # not a tiny icon
                            w <= 1500 and h <= 1500): # not a background/page image
                        if area > best_area:
                            best_area = area
                            best_img_bytes = img_bytes

            if best_img_bytes is None:
                if trace is not None:
                    trace.append("No portrait photo found directly in PDF.")
                return None

            # Convert to PNG
            def _to_png():
                pil_img = Image.open(io.BytesIO(best_img_bytes)).convert("RGB")
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                return buf.getvalue()

            png = _safe(_to_png, default=None, label="portrait_to_png", trace=trace)
            if trace is not None:
                if png:
                    trace.append(f"Portrait photo extracted from PDF (area={best_area}px²).")
                else:
                    trace.append("Portrait photo found but PNG conversion failed.")
            return png
        finally:
            doc.close()
    except Exception as e:
        if trace is not None:
            trace.append(f"Portrait photo extraction failed: {type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# Step 1: pull candidate QR images out of the PDF
# ---------------------------------------------------------------------------

def extract_candidate_qr_images(pdf_path: str, password: Optional[str] = None,
                                 trace: Optional[list] = None) -> list[bytes]:
    doc = fitz.open(pdf_path)
    try:
        if doc.needs_pass:
            if not password:
                raise ValueError("PDF is password protected. Supply the password.")
            if not doc.authenticate(password):
                raise ValueError("Incorrect PDF password.")

        strict_candidates = []
        loose_candidates = []

        # Scan ALL pages, not just the first two -- some documents put
        # the QR on a later page (e.g. a cover letter or extra page).
        for page_num in range(len(doc)):
            page = doc[page_num]
            images = _safe(page.get_images, full=True, default=[], label=f"get_images(page {page_num})", trace=trace) or []
            for img in (images if isinstance(images, list) else []):
                xref = img[0]
                base_image = _safe(doc.extract_image, xref, default=None, label="extract_image", trace=trace)
                if not base_image or not isinstance(base_image, dict):
                    continue
                img_bytes = base_image.get("image")
                if not img_bytes:
                    continue

                def _classify():
                    pil_img = Image.open(io.BytesIO(img_bytes))
                    w, h = pil_img.size
                    aspect = w / h if h else 0
                    return w, h, aspect

                dims = _safe(_classify, default=None, label="classify image", trace=trace)
                if dims is None:
                    continue
                w, h, aspect = dims

                # Strict: square-ish and reasonably sized -- almost
                # certainly a QR code.
                if 0.85 <= aspect <= 1.15 and w >= 80:
                    strict_candidates.append(img_bytes)
                # Loose: still plausibly square-ish, smaller or slightly
                # off-ratio -- used only if strict candidates all fail.
                elif 0.7 <= aspect <= 1.3 and w >= 40:
                    loose_candidates.append(img_bytes)

        candidates = strict_candidates + loose_candidates
        if trace is not None:
            trace.append(
                f"Found {len(strict_candidates)} strict + {len(loose_candidates)} "
                f"loose QR candidates across {len(doc)} page(s)."
            )
        return candidates
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Step 2: decode the QR image -> get the true underlying byte stream
# ---------------------------------------------------------------------------

def decode_qr_to_bytes(img_bytes: bytes, trace: Optional[list] = None) -> Optional[bytes]:
    """Returns the fully-reconstructed compressed byte stream, having
    already reversed the "numeric QR mode" decimal-string encoding."""
    pil_img = _safe(lambda: Image.open(io.BytesIO(img_bytes)).convert("L"),
                     default=None, label="open QR image", trace=trace)
    if pil_img is None:
        return None

    results = _safe(zbar_decode, pil_img, default=[], label="zbar_decode", trace=trace)
    if not results:
        return None

    payload = results[0].data

    # Case A: numeric-mode QR -- payload is an ASCII decimal digit string
    # representing one big integer, whose big-endian byte form is the real
    # compressed data. This is what real Aadhaar QR codes use.
    def _numeric_mode():
        digit_string = payload.decode("ascii")
        if not digit_string.isdigit():
            raise ValueError("not a numeric-mode payload")
        big_int = int(digit_string)
        byte_length = (big_int.bit_length() + 7) // 8
        return big_int.to_bytes(byte_length, byteorder="big")

    result = _safe(_numeric_mode, default=None, label="numeric-mode decode", trace=trace)
    if result is not None:
        return result

    # Case B: byte-mode QR -- zbar's C library re-maps raw bytes through a
    # Latin-1 -> UTF-8 detour for binary payloads. Reverse it.
    def _byte_mode_fix():
        return payload.decode("utf-8").encode("latin-1")

    result = _safe(_byte_mode_fix, default=None, label="byte-mode Latin-1 fix", trace=trace)
    if result is not None:
        return result

    # Case C: give up trying to "fix" it, use raw payload as-is.
    return payload


# ---------------------------------------------------------------------------
# Step 3: decompress
# ---------------------------------------------------------------------------

def decompress_payload(raw: bytes, trace: Optional[list] = None) -> bytes:
    for name, fn in [
        ("gzip", gzip.decompress),
        ("zlib", zlib.decompress),
        ("raw_deflate", lambda b: zlib.decompress(b, -zlib.MAX_WBITS)),
        ("zlib_skip_2byte_header", lambda b: zlib.decompress(b[2:])),
    ]:
        result = _safe(fn, raw, default=None, label=f"decompress via {name}", trace=None)
        if result is not None:
            if trace is not None:
                trace.append(f"Decompression succeeded via {name}.")
            return result
    if trace is not None:
        trace.append("All decompression methods failed; using raw bytes as-is.")
    return raw  # give up, return as-is


# ---------------------------------------------------------------------------
# Script detection helper (Unicode-range based, works for any Indic script)
# ---------------------------------------------------------------------------

SCRIPT_RANGES = [
    ("devanagari", 0x0900, 0x097F),
    ("gujarati", 0x0A80, 0x0AFF),
    ("bengali", 0x0980, 0x09FF),
    ("tamil", 0x0B80, 0x0BFF),
    ("telugu", 0x0C00, 0x0C7F),
    ("kannada", 0x0C80, 0x0CFF),
    ("malayalam", 0x0D00, 0x0D7F),
    ("oriya", 0x0B00, 0x0B7F),
    ("gurmukhi", 0x0A00, 0x0A7F),
]


def detect_script(text: str) -> str:
    for ch in text or "":
        code = ord(ch)
        for name, lo, hi in SCRIPT_RANGES:
            if lo <= code <= hi:
                return name
    return "latin"


def has_local_script(line: str) -> bool:
    return detect_script(line) != "latin"


# ---------------------------------------------------------------------------
# Corruption detection -- broad, pattern based, reusable per-candidate
# ---------------------------------------------------------------------------

# Multi-language "this is an admin label, not a name" signal words. Kept
# deliberately broad -- false positives here just mean we score a block
# lower, they don't hard-exclude it if nothing else is available.
NOISE_KEYWORDS = [
    # English & Hindi/Marathi
    "enrolment", "enrollment", "registration", "नामांकन", "पंजीकरण",
    "નોંધણી", "aadhaar no", "reference", "uid", "information", "माहिती",
    "unique identification", "authority of india", "government of india",
    "भारत सरकार", "भारतीय विशिष्ट ओळख", "प्राधिकरण", "माझे आधार, माझी ओळख",
    "मेरा आधार, मेरी पहचान", "help@uidai", "1947", "www.uidai",
    # Tamil
    "இந்திய தனித்துவ அடையாள ஆணையம்", "இந்திய அரசு", "ஆதார்", "தகவல்", "பதிவு எண்", "என் ஆதார், என் அடையாளம்",
    # Telugu
    "భారత విశిష్ట గుర్తింపు ప్రాధికార సంస్థ", "భారత ప్రభుత్వం", "ఆధార్", "సమాచారం", "నా ఆధార్, నా గుర్తింపు",
    # Kannada
    "ಭಾರತೀಯ ವಿಶಿಷ್ಟ ಗುರುತಿನ ಪ್ರಾಧಿಕಾರ", "ಭಾರತ ಸರ್ಕಾರ", "ಆಧಾರ್", "ಮಾಹಿತಿ", "ನನ್ನ ಆಧಾರ್, ನನ್ನ ಗುರುತು",
    # Malayalam
    "യുണീക് ഐഡന്റിഫിക്കേഷൻ അതോറിറ്റി ഓഫ് ഇന്ത്യ", "ഭാരത സർക്കാർ", "ആധാർ", "വിവരം", "എന്റെ ആധാർ, എന്റെ തിരിച്ചറിയൽ",
    # Bengali & Assamese
    "ভারতীয় অনন্য সনাক্তকরণ কর্তৃপক্ষ", "ভারত সরকার", "আধার", "তথ্য", "আমার আধার, আমার পরিচয়",
    "ভাৰতীয় বিশিষ্ট চিনাক্তকৰণ প্ৰাধিকৰণ", "ভাৰত চৰকাৰ", "আধাৰ", "মোৰ আধাৰ, মোৰ পৰিচয়",
    # Gujarati
    "ભારતીય વિશિષ્ટ ઓળખ પ્રાધિકરણ", "ભારત સરકાર", "આધાર", "માહિતી", "મારો આધાર, મારી ઓળખ",
    # Odia
    "ଭାରତୀୟ ବିଶିଷ୍ଟ ପରିଚୟ ପ୍ରାଧିକରଣ", "ଭାରତ ସରକାର", "ଆଧାର", "ସୂଚନା", "ମୋ ଆଧାର, ମୋ ପରିଚୟ",
    # Punjabi
    "ਭਾਰਤੀ ਵਿਲੱਖਣ ਪਛਾਣ ਅਥਾਰਟੀ", "ਭਾਰਤ ਸਰਕਾਰ", "ਆਧਾਰ", "ਜਾਣਕਾਰੀ", "ਮੇਰਾ ਆਧਾਰ, ਮੇਰੀ ਪਹਿਚਾਣ",
    # Urdu
    "منفرد شناختی اتھارٹی آف انڈیا", "حکومت ہند", "آدھار", "معلومات", "میرا آدھار، میری پہچان"
]

ADDRESS_KEYWORDS = [
    # Hindi / Marathi
    "पत्ता", "पता", "पोस्ट", "ता.", "ता ", "जि.", "जि ", "तहसील", "तालुका", "तालुक", "जिल्हा", "जिल्ला", "गाव", "गाँव", "पिन", "पिनकोड", "पिन कोड",
    # Gujarati
    "સરનામું", "મુકામ", "મુ.", "મુ ", "શેરી", "નગર", "જિલ્લો", "તાલુકો", "ગામ",
    # Tamil
    "முகவரி", "தெரு", "நகர்", "மாவட்டம்", "வட்டம்", "அஞ்சல்", "கிராமம்", "கதவு எண்", "பெறுநர்",
    # Telugu
    "చిరునామా", "విళాసం", "వీధి", "నగర్", "జిల్లా", "మండలం", "గ్రామం", "పోస్ట్", "ఇంటి నం", "స్వీకర్త",
    # Kannada
    "ವಿಳಾಸ", "ರಸ್ತೆ", "ಬಡಾವಣೆ", "ಜಿಲ್ಲೆ", "ತಾಲೂಕು", "ಅಂಚೆ", "ಗ್ರಾಮ", "ಮನೆ ನಂ", "ಸ್ವೀಕರ್ತೃ",
    # Malayalam
    "മേൽവിലാസം", "വിലാസം", "റോഡ്", "നഗർ", "ജില്ല", "താലൂക്ക്", "പോസ്റ്റ്", "ഗ്രാമം", "വീട്ടു നമ്പർ",
    # Bengali & Assamese
    "ঠিকানা", "ঠিকনা", "রাস্তা", "ৰাস্তা", "নগর", "নগৰ", "জেলা", "জিলা", "থানা", "ডাকঘর", "ডাকঘৰ", "গ্রাম", "গাঁও",
    # Odia
    "ଠିକଣା", "ରାସ୍ତା", "ନଗର", "ଜିଲ୍ଲା", "ଡାକଘର", "ଗ୍ରାମ",
    # Punjabi
    "ਪਤਾ", "ਗਲੀ", "ਨਗਰ", "ਜ਼ਿਲ੍ਹਾ", "ਤਹਿਸੀਲ", "ਡਾਕਖਾਨਾ", "ਪਿੰਡ",
    # Urdu
    "پتہ", "گلی", "محلہ", "ضلع", "تحصیل", "ڈاکخانہ", "مکان نمبر",
    # English tokens
    "at post", "at/po", "post:", "po:", "taluka:", "tal:", "dist:", "district:", "village:", "vtc:", "sub district:", "state:", "pin:", "pincode:",
    "road", "street", "lane", "nagar", "colony", "apartment", "flat", "house", "building", "sector", "block", "ward", "nivas", "soc"
]


def looks_like_admin_noise(text: str) -> bool:
    lower = (text or "").lower()
    if any(k in lower for k in NOISE_KEYWORDS):
        return True
    # enrolment-style numeric IDs: groups of digits separated by slashes
    if re.search(r"\d+\s*/\s*\d+\s*/\s*\d+", text or ""):
        return True
    return False


def looks_like_address(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    # 1. Matches address prefix across all 12 Indian languages
    if re.match(
        r'^(पत्ता|पता|સરનામું|મુકામ|મુ|முகவரி|చిరునామా|విళాసం|విళాస|ವಿಳಾಸ|മേൽവിലാസം|വിലാസം|ঠিকানা|ঠিকনা|ଠିକଣା|ਪਤਾ|پتہ|address|to|प्रति|பெறுநர்|స్వీకర్త|ಸ್ವೀಕರ್ತೃ)\s*[:\.\-]',
        text,
        re.IGNORECASE
    ):
        return True
    # 2. Universal Indian PIN Code rule (6 digits between 100000 and 999999)
    if re.search(r'\b[1-9][0-9]{5}\b', text):
        return True
    # 3. Matches multiple regional address tokens
    matches = sum(1 for kw in ADDRESS_KEYWORDS if kw in lower)
    if matches >= 2:
        return True
    if re.match(r'^(मु[\.\s]|at[\s\.\/]|c\/o|s\/o|w\/o|d\/o)', text, re.IGNORECASE):
        return True
    return False


def dedupe_repeated_matras(text: str) -> str:
    """Collapse a run of 2+ IDENTICAL consecutive vowel-sign/virama
    characters down to a single occurrence -- e.g. "રેસિડેન્સીી" becomes "રેસિડેન્સી".
    """
    if not text:
        return text
    return re.sub(r"([\u0ABE-\u0ACD\u093E-\u094D])\1+", r"\1", text)


def corruption_signals(text: str) -> list[str]:
    """Return a list of human-readable reasons this text looks corrupted."""
    if not text:
        return []
    reasons = []

    if re.search(r"[\u0080-\u009F]", text):
        reasons.append("contains C1 control character")

    if re.search(r"[\u0A80-\u0AFF\u0900-\u097F][a-zA-Z][\u0A80-\u0AFF\u0900-\u097F]", text):
        reasons.append("Latin letter wedged between Indic characters")

    if re.search(r"\s[\u0ABE-\u0ACD\u093E-\u094D]", text):
        reasons.append("floating/detached matra after whitespace")

    tokens = text.split()
    if len(tokens) >= 4:
        single_char_tokens = sum(1 for t in tokens if len(t) == 1)
        if single_char_tokens / len(tokens) > 0.4:
            reasons.append("excessive single-character fragments (broken font)")

    if "\ufffd" in text or "\N{REPLACEMENT CHARACTER}" in text:
        reasons.append("contains Unicode replacement character")

    return reasons


def is_corrupted(text: str) -> bool:
    return len(corruption_signals(text)) > 0


# ---------------------------------------------------------------------------
# Local-language extraction -- scored block selection
# ---------------------------------------------------------------------------

def _score_name_block(block: list[str]) -> float:
    """Higher score = more likely to actually be a person's name block."""
    text = " ".join(block).strip()
    if not text:
        return -1000.0

    # DISQUALIFY ADDRESSES IMMEDIATELY
    if looks_like_address(text):
        return -1000.0

    # DISQUALIFY ADMIN NOISE
    if looks_like_admin_noise(text):
        return -1000.0

    # DISQUALIFY DATES / DOB / GENDER / METADATA
    if re.search(r'\b(dob|birth|gender|male|female|जन्म|तारीख|तिथि|पुरुष|महिला|वय|age|आधार|aadhaar|information|माहिती|ओळख)\b', text, re.IGNORECASE):
        return -1000.0
    if re.search(r'\d{2}[/\-]\d{2}[/\-]\d{4}', text):
        return -1000.0
    if re.search(r'\d', text):
        return -500.0

    word_count = len(text.split())
    # Real Indian names are typically 2-4 words
    if 2 <= word_count <= 4:
        score = 50.0
    elif word_count == 1:
        score = 10.0
    else:
        return -500.0

    if 4 <= len(text) <= 35:
        score += 20.0
    else:
        score -= 20.0

    signals = corruption_signals(text)
    score -= 20.0 * len(signals)

    return score


def _score_address_block(block: list[str]) -> float:
    """Higher score = more likely to be the person's local language address."""
    text = " ".join(block).strip()
    if not text:
        return -1000.0

    if looks_like_admin_noise(text):
        return -1000.0

    score = 0.0
    if looks_like_address(text):
        score += 50.0

    # 6-digit Indian PIN code is a decisive address signal
    if re.search(r'\b[1-9][0-9]{5}\b', text):
        score += 50.0

    # Addresses typically have 4+ words
    word_count = len(text.split())
    if word_count >= 4:
        score += 30.0

    return score


def extract_local_language_fields(pdf_path: str, password: Optional[str] = None,
                                   english_name_hint: str = "") -> dict:
    trace: list = []
    result = {
        "local_full_name": "",
        "local_address": "",
        "local_script": "",
        "local_confidence": 0,
        "corruption_detected": False,
        "trace": trace,
    }

    def _get_text():
        doc = fitz.open(pdf_path)
        try:
            if doc.needs_pass:
                if not password:
                    raise ValueError("PDF is password protected. Supply the password.")
                if not doc.authenticate(password):
                    raise ValueError("Incorrect PDF password.")
            parts = []
            for i in range(len(doc)):
                parts.append(doc[i].get_text("text"))
            return "\n".join(parts)
        finally:
            doc.close()

    text = _safe(_get_text, default=None, label="PyMuPDF get_text", trace=trace)
    if text is None:
        trace.append("Could not read PDF text layer at all -- returning empty result.")
        return result

    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        trace.append("PDF text layer was empty.")
        return result

    # group contiguous local-script lines into candidate blocks
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if has_local_script(line):
            current.append(line)
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)

    trace.append(f"Found {len(blocks)} contiguous local-script block(s) across {len(lines)} text line(s).")

    if not blocks:
        trace.append("No local-script text found in PDF.")
        return result

    # 1. First, select the best address block
    scored_addrs = [(_score_address_block(b), b) for b in blocks]
    scored_addrs = [sa for sa in scored_addrs if sa[0] > 0]
    scored_addrs.sort(key=lambda x: x[0], reverse=True)
    best_address_block = scored_addrs[0][1] if scored_addrs else None

    # 2. Select the best name block (excluding the address block)
    name_candidates = [b for b in blocks if b is not best_address_block]
    scored_names = [(_score_name_block(b), b) for b in name_candidates]
    scored_names = [sn for sn in scored_names if sn[0] > 0]
    scored_names.sort(key=lambda x: x[0], reverse=True)
    best_name_block = scored_names[0][1] if scored_names else None

    name_text = ""
    if best_name_block:
        name_text = " ".join(best_name_block).strip()
        name_text = dedupe_repeated_matras(name_text)
        name_text = re.sub(r'^(name|नाम|नाव|ശ്രീ|பெயர்)\s*[:\-]\s*', '', name_text, flags=re.IGNORECASE).strip()

    address_text = ""
    if best_address_block:
        address_text = " ".join(best_address_block).strip()
        address_text = dedupe_repeated_matras(address_text)
        # Clean leading labels like "पत्ता:" or "पता:"
        address_text = re.sub(r'^(पत्ता|पता|सरनामु|મુકામ|മുഖவரி|చిరునామా|విళాస|ಮೇಲ್ವಿಲಾಸ|മേൽവിലാസം|ਪਤਾ|ଠିକଣା|ঠিকানা|address|to|प्रति)\s*[:\.\-]\s*', '', address_text, flags=re.IGNORECASE).strip()

    name_signals = corruption_signals(name_text) if name_text else []
    address_signals = corruption_signals(address_text) if address_text else []

    confidence = 80 if (name_text or address_text) else 0
    confidence -= 20 * len(name_signals)
    confidence -= 10 * len(address_signals)
    confidence = max(0, min(100, confidence))

    result["local_full_name"] = name_text
    result["local_address"] = address_text
    result["local_script"] = detect_script(name_text or address_text)
    result["local_confidence"] = confidence
    result["corruption_detected"] = bool(name_signals or address_signals)

    trace.append(f"Extracted local name: '{name_text}', local address: '{address_text[:40]}...' (confidence={confidence}).")
    return result


# ---------------------------------------------------------------------------
# Step 4: parse QR fields (validated against real Aadhaar samples)
# ---------------------------------------------------------------------------

FIELD_MAPPING = {
    0: "version",
    2: "reference_id",
    3: "full_name",
    4: "dob",
    5: "gender",
    6: "care_of",
    7: "district",
    8: "landmark",
    9: "house",
    10: "location",
    11: "pincode",
    12: "post_office",
    13: "state",
    14: "sub_district",
    15: "vtc",
    17: "masked_number",
}

TEXT_FIELD_COUNT = 19


def parse_qr_fields(decompressed: bytes, trace: Optional[list] = None) -> AadhaarData:
    data = AadhaarData(source="qr", extraction_confidence="high")
    parts = decompressed.split(b"\xff")

    if len(parts) <= TEXT_FIELD_COUNT:
        data.errors.append(
            f"Expected more than {TEXT_FIELD_COUNT} delimited parts, got {len(parts)}. "
            "This QR may use a different field layout."
        )
        data.extraction_confidence = "low"

    for idx, attr in FIELD_MAPPING.items():
        if idx < len(parts):
            def _decode_field():
                return parts[idx].decode("utf-8", errors="strict")
            val = _safe(_decode_field, default=None, trace=None)
            if val is None:
                val = _safe(lambda: parts[idx].decode("utf-8", errors="replace"), default="", trace=None)
                data.errors.append(f"field[{idx}] ({attr}) had a decode issue, used lossy fallback.")
            setattr(data, attr, val)

    if len(parts) > TEXT_FIELD_COUNT:
        photo_bytes = b"\xff" + b"\xff".join(parts[TEXT_FIELD_COUNT:])
        data.photo_bytes = photo_bytes

        def _decode_photo():
            img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        png = _safe(_decode_photo, default=None, label="decode JPEG2000 photo", trace=trace)
        if png is not None:
            data.photo_png_bytes = png
        else:
            data.errors.append(
                "Could not decode embedded JPEG2000 photo (needs libopenjp2 installed)."
            )

    return data


# ---------------------------------------------------------------------------
# Fallback: PDF text-layer parsing for basic fields (English)
# ---------------------------------------------------------------------------

LABEL_PATTERNS = {
    "dob": r"(?:DOB|Date of Birth)\s*[:\-]?\s*([0-9]{2}[/\-][0-9]{2}[/\-][0-9]{4})",
    "gender": r"\b(Male|Female|MALE|FEMALE|पुरुष|महिला)\b",
    "pincode": r"\b([1-9][0-9]{5})\b",
}


def extract_via_text_layer(pdf_path: str, password: Optional[str] = None) -> AadhaarData:
    data = AadhaarData(source="text_layer", extraction_confidence="fallback")

    if pdfplumber is None:
        data.errors.append("pdfplumber not installed; text-layer fallback unavailable.")
        return data

    def _get_text() -> str:
        if password:
            with pdfplumber.open(pdf_path, password=password) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages[:2])
        else:
            with pdfplumber.open(pdf_path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages[:2])

    full_text_val = _safe(_get_text, default="", label="pdfplumber extract_text", trace=data.errors)
    full_text: str = str(full_text_val) if full_text_val is not None else ""

    for field_name, pattern in LABEL_PATTERNS.items():
        def _find_match(p: str = pattern, text: str = full_text) -> Optional[re.Match]:
            return re.search(p, text, flags=re.IGNORECASE | re.MULTILINE)

        m = _safe(_find_match, default=None)
        if m:
            setattr(data, field_name, m.group(1).strip())
        else:
            data.errors.append(f"Could not locate field '{field_name}' via text-layer regex.")

    data.errors.append(
        "NOTE: name/address fields are unreliable via text-layer regex -- prefer the QR path."
    )
    return data


# ---------------------------------------------------------------------------
# Orchestration -- the "powerhouse" entry point. NEVER raises.
# ---------------------------------------------------------------------------

def extract_aadhaar_data(pdf_path: str, password: Optional[str] = None) -> AadhaarData:
    """Top-level entry point. Guaranteed to return an AadhaarData object,
    never raise -- worst case you get back source='failed' with populated
    `errors` and `trace` explaining exactly what was tried and why it
    didn't work, which is itself valuable for debugging without ever
    crashing the calling process."""
    trace: list = []
    qr_error = "No QR candidates found."
    result: Optional[AadhaarData] = None

    # Step 0: Upfront validation of password protection & correctness
    try:
        doc = fitz.open(pdf_path)
        try:
            if doc.needs_pass:
                if not password:
                    return AadhaarData(
                        source="failed",
                        extraction_confidence="low",
                        errors=["PDF is password protected. Please enter the password."],
                        trace=["PDF requires password but none was provided."]
                    )
                if not doc.authenticate(password):
                    return AadhaarData(
                        source="failed",
                        extraction_confidence="low",
                        errors=["Incorrect PDF password. Please enter the correct password."],
                        trace=["PDF authentication failed with provided password."]
                    )
        finally:
            doc.close()
    except Exception as e:
        return AadhaarData(
            source="failed",
            extraction_confidence="low",
            errors=[f"Could not open PDF: {type(e).__name__}: {e}"],
            trace=[f"fitz.open failed: {e}"]
        )

    try:
        candidates = extract_candidate_qr_images(pdf_path, password=password, trace=trace)
        for i, img_bytes in enumerate(candidates):
            raw = decode_qr_to_bytes(img_bytes, trace=trace)
            if not raw:
                continue
            decompressed = decompress_payload(raw, trace=trace)
            parsed = parse_qr_fields(decompressed, trace=trace)
            if parsed.full_name and len(parsed.full_name) > 1 and not looks_like_admin_noise(parsed.full_name):
                trace.append(f"QR candidate #{i} produced a usable name -- using it.")
                result = parsed
                break
            qr_error = f"QR candidate #{i} decoded but field parsing produced no usable name."
    except Exception as e:
        # Should be unreachable given _safe() wrapping inside, but this
        # outer guard exists so a truly unexpected error (e.g. a bug in
        # this very function) still can't propagate to the caller.
        qr_error = f"Unexpected error during QR extraction: {type(e).__name__}: {e}"
        logger.exception("Unexpected error during QR extraction")

    if result is None:
        trace.append(f"QR path did not produce usable data ({qr_error}); trying text-layer fallback.")
        try:
            result = extract_via_text_layer(pdf_path, password=password)
        except Exception as e:
            result = AadhaarData(
                source="failed",
                extraction_confidence="low",
                errors=[f"QR path failed: {qr_error}", f"Text-layer path failed: {type(e).__name__}: {e}"],
            )
        else:
            result.errors.append(f"QR path failed: {qr_error}")

    if result is None or (not result.full_name and not result.dob and not result.masked_number):
        if result is None:
            result = AadhaarData(
                source="failed",
                extraction_confidence="low",
                errors=[f"QR path failed: {qr_error}", "No usable data extracted."],
            )
        else:
            result.source = "failed"
            result.errors.append("No demographic details could be extracted from this PDF.")
        result.trace = trace
        return result

    # Enrich with local-language name/address -- best-effort, never fatal.
    try:
        local = extract_local_language_fields(
            pdf_path, password=password, english_name_hint=result.full_name
        )
        result.local_full_name = local["local_full_name"]
        result.local_address = local["local_address"]
        result.local_script = local["local_script"]
        result.local_confidence = local["local_confidence"]
        trace.extend(local.get("trace", []))
    except Exception as e:
        result.errors.append(f"Local-language extraction failed: {type(e).__name__}: {e}")
        logger.exception("Local-language extraction failed")

    # Prefer the high-quality portrait photo embedded directly in the PDF
    # over the tiny JPEG2000 face crop stored inside the QR code.
    portrait_png = extract_portrait_photo_from_pdf(pdf_path, password=password, trace=trace)
    if portrait_png is not None:
        result.photo_png_bytes = portrait_png
        result.photo_bytes = None  # clear the low-quality QR photo
        trace.append("Using portrait photo from PDF (overrides QR-embedded photo).")
    elif result.photo_png_bytes is None:
        trace.append("No portrait photo in PDF and no QR-embedded photo decoded.")

    result.trace = trace
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python aadhaar_extractor.py <path_to_pdf> [password]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    pwd = sys.argv[2] if len(sys.argv) > 2 else None

    result = extract_aadhaar_data(pdf_path, password=pwd)
    out = result.to_json_safe_dict()
    print(json.dumps(out, ensure_ascii=False, indent=2))
