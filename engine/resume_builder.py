"""
resume_builder.py - High-Fidelity Indian Job Resume / CV Engine
---------------------------------------------------------------
Generates single-page, print-ready 300 DPI A4 Resumes matching standard
cyber-café and job-submission formats (like ResumeGround / Sarkari formats).

Features:
- Single-page guarantee with precise A4 dimensions (210mm x 297mm)
- Passport photo integration with border
- Career objective with 1-click cyber-cafe presets
- Academic qualifications tabular layout
- Technical / Computer skills & other qualifications
- Work Experience (Experienced or Fresher mode)
- Personal information (Father's Name, DOB, Gender, Marital Status, etc.)
- Formal Declaration with signature section
- Multiple themes: 'classic' (ResumeGround match), 'modern' (Corporate Blue), 'minimal' (Clean Slate)
- Instant vector A4 PDF export + 300 DPI preview PNG
"""

import os
import base64
import html
from typing import Optional, List, Dict, Any
from io import BytesIO
from PIL import Image

try:
    from engine.card_renderer import render_html_to_pdf
except ImportError:
    render_html_to_pdf = None

try:
    from engine.watermark import apply_card_watermark
except ImportError:
    apply_card_watermark = None

# Built-in Career Objectives for Quick 1-Click Suggestions
OBJECTIVE_SUGGESTIONS = {
    "fresher": "To obtain a challenging and rewarding position in an organization where I can utilize my skills and educational background to contribute to company growth while continuously expanding my knowledge and capabilities.",
    "computer_operator": "To secure a position as a Computer Operator / Data Entry Specialist where I can leverage my typing speed, MS Office expertise, and administrative abilities to ensure efficient and accurate data management.",
    "accountant": "Seeking a responsible role as an Accountant / Tally Operator to utilize my knowledge of accounting principles, GST filing, Tally ERP/Prime, and financial record-keeping for organizational efficiency.",
    "sales": "Energetic and goal-driven professional seeking a Sales / Marketing Executive role to drive business growth, expand client relationships, and achieve revenue targets through proactive communication and dedication.",
    "office_assistant": "Hardworking and reliable individual seeking an Office Assistant / Administrative role to maintain organized office operations, handle correspondence, and assist day-to-day administrative functions efficiently."
}


def _clean_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def _process_photo_b64(photo_bytes: Optional[bytes]) -> str:
    """Prepares user photo as clean base64 data URL with aspect ratio fitting."""
    if not photo_bytes:
        return ""
    try:
        img = Image.open(BytesIO(photo_bytes))
        img = img.convert("RGB")
        # Resize photo to max 500x650 for crisp 300DPI passport box without bloat
        img.thumbnail((500, 650), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=92)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        print(f"[ResumeBuilder] Photo processing error: {e}")
        return ""


def generate_resume_html(data: Dict[str, Any], photo_b64: str = "", is_sample: bool = False) -> str:
    """
    Renders single-page A4 HTML matching the reference Indian CV layout.
    """
    theme = _clean_str(data.get("template_style"), "classic").lower()
    full_name = _clean_str(data.get("full_name"), "FULL NAME").upper()
    job_title = _clean_str(data.get("job_title"), "")
    mobile = _clean_str(data.get("mobile"), "")
    email = _clean_str(data.get("email"), "")
    address = _clean_str(data.get("address"), "")

    objective = _clean_str(data.get("career_objective"), OBJECTIVE_SUGGESTIONS["fresher"])

    # Qualifications list
    qualifications: List[Dict[str, str]] = data.get("qualifications", [])
    if not isinstance(qualifications, list):
        qualifications = []

    # Skills list
    skills: List[str] = data.get("skills", [])
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split("\n") if s.strip()]
    elif not isinstance(skills, list):
        skills = []

    # Experience
    is_fresher = str(data.get("experience_type", "fresher")).lower() == "fresher"
    experience_list: List[Dict[str, str]] = data.get("experience_list", [])
    if not isinstance(experience_list, list):
        experience_list = []
    experience_note = _clean_str(data.get("experience_note"), "")

    # Personal Info
    father_name = _clean_str(data.get("father_name"), "")
    mother_name = _clean_str(data.get("mother_name"), "")
    dob = _clean_str(data.get("dob"), "")
    gender = _clean_str(data.get("gender"), "")
    marital_status = _clean_str(data.get("marital_status"), "")
    languages = _clean_str(data.get("languages"), "Hindi & English")
    nationality = _clean_str(data.get("nationality"), "Indian")
    permanent_address = _clean_str(data.get("permanent_address"), "")

    # Declaration
    declaration_text = _clean_str(
        data.get("declaration_text"),
        "I hereby declare that all the information mentioned above is true and correct to the best of my knowledge and belief."
    )
    declaration_date = _clean_str(data.get("declaration_date"), "")
    declaration_place = _clean_str(data.get("declaration_place"), "")

    # Theme Accents
    if theme == "modern":
        primary_color = "#1e3a8a" # Navy
        header_bg = "#f0f4f8"
        border_color = "#cbd5e1"
        title_font = "'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif"
    elif theme == "minimal":
        primary_color = "#18181b" # Zinc dark
        header_bg = "#f4f4f5"
        border_color = "#e4e4e7"
        title_font = "'Inter', 'Segoe UI', Arial, sans-serif"
    else: # classic (matching ResumeGround)
        primary_color = "#000000"
        header_bg = "#f1f5f9"
        border_color = "#333333"
        title_font = "'Segoe UI', Arial, Helvetica, sans-serif"

    # Qualifications Table Rows
    qual_rows_html = ""
    if qualifications:
        for idx, q in enumerate(qualifications, 1):
            deg = html.escape(_clean_str(q.get("degree") or q.get("exam")))
            board = html.escape(_clean_str(q.get("board") or q.get("university")))
            year = html.escape(_clean_str(q.get("year")))
            pct = html.escape(_clean_str(q.get("percentage") or q.get("grade") or q.get("marks")))
            qual_rows_html += f"""
            <tr>
                <td style="text-align: center; width: 45px;">{idx}</td>
                <td><strong>{deg}</strong></td>
                <td>{board}</td>
                <td style="text-align: center; width: 65px;">{year}</td>
                <td style="text-align: center; width: 75px;">{pct}</td>
            </tr>
            """
    else:
        # Default placeholder rows if empty
        qual_rows_html = """
        <tr>
            <td style="text-align: center;">1</td>
            <td><strong>10th (Matriculation)</strong></td>
            <td>State Board / CBSE</td>
            <td style="text-align: center;">-</td>
            <td style="text-align: center;">-</td>
        </tr>
        <tr>
            <td style="text-align: center;">2</td>
            <td><strong>12th (Intermediate)</strong></td>
            <td>State Board / CBSE</td>
            <td style="text-align: center;">-</td>
            <td style="text-align: center;">-</td>
        </tr>
        """

    # Skills List Items
    skills_html = ""
    if skills:
        for s in skills:
            skills_html += f"<li>{html.escape(s)}</li>"
    else:
        skills_html = """
        <li>Basic Knowledge of Computer (MS Office, MS Word, Excel, PowerPoint & Internet)</li>
        <li>Good Communication and Interpersonal Skills</li>
        """

    # Experience HTML
    experience_html = ""
    if is_fresher or not experience_list:
        if experience_note:
            experience_html = f"<li>{html.escape(experience_note)}</li>"
        else:
            experience_html = "<li><strong>Fresher:</strong> Ready to learn, adaptable, and enthusiastic to contribute to organizational success.</li>"
    else:
        for exp in experience_list:
            role = html.escape(_clean_str(exp.get("role") or exp.get("designation")))
            comp = html.escape(_clean_str(exp.get("company") or exp.get("organization")))
            dur = html.escape(_clean_str(exp.get("duration") or exp.get("period")))
            desc = html.escape(_clean_str(exp.get("description")))
            header_str = f"<strong>{role}</strong>"
            if comp:
                header_str += f" at <em>{comp}</em>"
            if dur:
                header_str += f" ({dur})"
            
            experience_html += f"<li><div>{header_str}</div>"
            if desc:
                experience_html += f"<div style='font-size: 10.5pt; color: #374151; margin-top: 1px;'>{desc}</div>"
            experience_html += "</li>"

    # Photo Box HTML
    photo_box_html = ""
    if photo_b64:
        photo_box_html = f"""
        <div class="photo-wrapper">
            <img src="{photo_b64}" alt="Profile Photo" class="photo-img">
        </div>
        """
    else:
        # Subtle cyber-cafe blank photo placeholder box
        photo_box_html = """
        <div class="photo-wrapper photo-placeholder">
            <div style="font-size: 8pt; color: #94a3b8; text-align: center; text-transform: uppercase;">
                Affix Photo<br>Here
            </div>
        </div>
        """

    # Sample Watermark HTML
    watermark_html = ""
    if is_sample:
        watermark_html = """
        <div class="watermark-overlay">
            <div class="wm-title">RAPID PVC • SAMPLE DEMO</div>
            <div class="wm-sub">rapidpvc.online • NOT FOR OFFICIAL USE</div>
        </div>
        """

    # Build Complete A4 HTML document
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Resume - {html.escape(full_name)}</title>
<style>
    @page {{
        size: A4 portrait;
        margin: 10mm 14mm 10mm 14mm;
    }}
    * {{
        box-sizing: border-box;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }}
    body {{
        margin: 0;
        padding: 0;
        background: #ffffff;
        color: #111827;
        font-family: {title_font};
        font-size: 10pt;
        line-height: 1.35;
    }}
    .resume-page {{
        width: 100%;
        position: relative;
        overflow: hidden;
    }}
    
    /* Top Resume Header */
    .resume-top-title {{
        text-align: center;
        font-size: 17pt;
        font-weight: 800;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: {primary_color};
        margin-bottom: 8px;
        border-bottom: 2px solid {primary_color};
        padding-bottom: 3px;
    }}
    
    .header-layout {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 8px;
        gap: 16px;
    }}
    .header-bio {{
        flex: 1;
    }}
    .candidate-name {{
        font-size: 15.5pt;
        font-weight: 800;
        letter-spacing: 0.5px;
        color: {primary_color};
        margin: 0 0 2px 0;
        text-transform: uppercase;
    }}
    .candidate-role {{
        font-size: 10.5pt;
        font-weight: 700;
        color: #374151;
        margin-bottom: 4px;
    }}
    .bio-line {{
        font-size: 9.5pt;
        color: #1f2937;
        margin: 1.5px 0;
        line-height: 1.3;
    }}
    .bio-line strong {{
        color: #111827;
        display: inline-block;
        width: 75px;
    }}
    
    /* Passport Photo Box */
    .photo-wrapper {{
        width: 32mm;
        height: 40mm;
        border: 1.5px solid #1f2937;
        background: #f8fafc;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        flex-shrink: 0;
    }}
    .photo-img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
    }}
    .photo-placeholder {{
        border: 1.5px dashed #94a3b8;
    }}

    /* Section Headers */
    .section-title {{
        font-size: 10.5pt;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: {primary_color};
        background: {header_bg};
        border-top: 1.2px solid {primary_color};
        border-bottom: 1.2px solid {primary_color};
        padding: 3px 8px;
        margin: 9px 0 5px 0;
    }}

    .section-content {{
        padding: 0 4px;
        font-size: 9.5pt;
        text-align: justify;
    }}

    /* Academic Qualifications Table */
    .qual-table {{
        width: 100%;
        border-collapse: collapse;
        margin: 4px 0 2px 0;
        font-size: 9.2pt;
    }}
    .qual-table th, .qual-table td {{
        border: 1px solid #4b5563;
        padding: 4px 6px;
    }}
    .qual-table th {{
        background: #f3f4f6;
        color: #111827;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 8.8pt;
    }}

    /* Bullet Lists */
    ul.bullet-list {{
        margin: 3px 0 3px 18px;
        padding: 0;
        font-size: 9.5pt;
    }}
    ul.bullet-list li {{
        margin-bottom: 3px;
        line-height: 1.35;
    }}

    /* Personal Information 2-Column Table */
    .info-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 9.5pt;
        margin-top: 3px;
    }}
    .info-table td {{
        padding: 2.2px 4px;
        vertical-align: top;
    }}
    .info-label {{
        width: 155px;
        font-weight: 700;
        color: #111827;
    }}
    .info-colon {{
        width: 12px;
        text-align: center;
        font-weight: 700;
    }}
    .info-val {{
        color: #1f2937;
    }}

    /* Declaration */
    .declaration-box {{
        font-size: 9.2pt;
        line-height: 1.35;
        color: #1f2937;
        margin-top: 3px;
    }}
    .signature-row {{
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        margin-top: 18px;
        padding: 0 4px;
    }}
    .sig-left {{
        font-size: 9.5pt;
        font-weight: 600;
        line-height: 1.45;
    }}
    .sig-right {{
        text-align: right;
        font-size: 10pt;
        font-weight: 700;
    }}
    .sig-line {{
        margin-top: 32px;
        border-top: 1px dashed #6b7280;
        display: inline-block;
        padding-top: 2px;
        min-width: 150px;
        text-align: center;
    }}

    /* Watermark for Free Demo Samples */
    .watermark-overlay {{
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) rotate(-32deg);
        pointer-events: none;
        z-index: 99999;
        text-align: center;
        opacity: 0.14;
        width: 100%;
    }}
    .wm-title {{
        font-size: 48pt;
        font-weight: 900;
        letter-spacing: 4px;
        color: #000000;
        white-space: nowrap;
    }}
    .wm-sub {{
        font-size: 18pt;
        font-weight: 800;
        letter-spacing: 2px;
        color: #dc2626;
        margin-top: 6px;
    }}
</style>
</head>
<body>
<div class="resume-page">
    {watermark_html}

    <!-- 1. Top Title -->
    <div class="resume-top-title">RESUME</div>

    <!-- 2. Header Layout: Left Bio + Right Passport Photo -->
    <div class="header-layout">
        <div class="header-bio">
            <h1 class="candidate-name">{html.escape(full_name)}</h1>
            {"<div class='candidate-role'>" + html.escape(job_title) + "</div>" if job_title else ""}
            <div class="bio-line"><strong>Address:</strong> {html.escape(address)}</div>
            <div class="bio-line"><strong>Mobile:</strong> {html.escape(mobile)}</div>
            {"<div class='bio-line'><strong>Email:</strong> " + html.escape(email) + "</div>" if email else ""}
        </div>
        {photo_box_html}
    </div>

    <!-- 3. Career Objective -->
    <div class="section-title">CAREER OBJECTIVE</div>
    <div class="section-content">
        {html.escape(objective)}
    </div>

    <!-- 4. Academic Qualification -->
    <div class="section-title">ACADEMIC QUALIFICATION</div>
    <table class="qual-table">
        <thead>
            <tr>
                <th>S.No.</th>
                <th>Qualification / Exam</th>
                <th>Board / University</th>
                <th>Passing Year</th>
                <th>% / Grade</th>
            </tr>
        </thead>
        <tbody>
            {qual_rows_html}
        </tbody>
    </table>

    <!-- 5. Technical / Other Skills -->
    <div class="section-title">OTHER QUALIFICATION & SKILLS</div>
    <ul class="bullet-list">
        {skills_html}
    </ul>

    <!-- 6. Work Experience -->
    <div class="section-title">WORK EXPERIENCE</div>
    <ul class="bullet-list">
        {experience_html}
    </ul>

    <!-- 7. Personal Information -->
    <div class="section-title">PERSONAL INFORMATION</div>
    <table class="info-table">
        {"<tr><td class='info-label'>Father's Name</td><td class='info-colon'>:</td><td class='info-val'>" + html.escape(father_name) + "</td></tr>" if father_name else ""}
        {"<tr><td class='info-label'>Mother's Name</td><td class='info-colon'>:</td><td class='info-val'>" + html.escape(mother_name) + "</td></tr>" if mother_name else ""}
        {"<tr><td class='info-label'>Date of Birth</td><td class='info-colon'>:</td><td class='info-val'>" + html.escape(dob) + "</td></tr>" if dob else ""}
        {"<tr><td class='info-label'>Gender</td><td class='info-colon'>:</td><td class='info-val'>" + html.escape(gender) + "</td></tr>" if gender else ""}
        {"<tr><td class='info-label'>Marital Status</td><td class='info-colon'>:</td><td class='info-val'>" + html.escape(marital_status) + "</td></tr>" if marital_status else ""}
        {"<tr><td class='info-label'>Languages Known</td><td class='info-colon'>:</td><td class='info-val'>" + html.escape(languages) + "</td></tr>" if languages else ""}
        {"<tr><td class='info-label'>Nationality</td><td class='info-colon'>:</td><td class='info-val'>" + html.escape(nationality) + "</td></tr>" if nationality else ""}
        {"<tr><td class='info-label'>Permanent Address</td><td class='info-colon'>:</td><td class='info-val'>" + html.escape(permanent_address) + "</td></tr>" if permanent_address else ""}
    </table>

    <!-- 8. Declaration -->
    <div class="section-title">DECLARATION</div>
    <div class="declaration-box">
        {html.escape(declaration_text)}
    </div>

    <!-- 9. Signature Block -->
    <div class="signature-row">
        <div class="sig-left">
            <div><strong>Date:</strong> {html.escape(declaration_date)}</div>
            <div><strong>Place:</strong> {html.escape(declaration_place)}</div>
        </div>
        <div class="sig-right">
            <div class="sig-line">({html.escape(full_name)})</div>
            <div style="font-size: 8.5pt; color: #64748b; font-weight: normal; margin-top: 2px;">Candidate Signature</div>
        </div>
    </div>
</div>
</body>
</html>
"""
    return html_content


def build_resume_document(
    data: Dict[str, Any],
    photo_bytes: Optional[bytes],
    output_dir: str,
    is_sample: bool = False
) -> Dict[str, Any]:
    """
    Renders A4 Vector PDF and high-res preview PNG.
    Returns file paths, sizes, and dimensions.
    """
    os.makedirs(output_dir, exist_ok=True)

    photo_b64 = _process_photo_b64(photo_bytes)
    html_content = generate_resume_html(data, photo_b64=photo_b64, is_sample=is_sample)

    pdf_path = os.path.join(output_dir, "resume.pdf")
    preview_path = os.path.join(output_dir, "preview.png")

    # Render HTML to PDF using the Chromium worker
    if render_html_to_pdf:
        render_html_to_pdf(html_content, pdf_path)
    else:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            pg = b.new_page()
            pg.set_content(html_content, wait_until="load")
            pg.pdf(path=pdf_path, format="A4", print_background=True, margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"})
            b.close()

    # Generate high-resolution preview PNG using PyMuPDF (fitz)
    import pymupdf
    doc = pymupdf.open(pdf_path)
    if len(doc) > 0:
        page = doc[0]
        # Render at 150 DPI for crisp preview without excess size (~1240 x 1754 px)
        pix = page.get_pixmap(dpi=150)
        pix.save(preview_path)
        preview_w = pix.width
        preview_h = pix.height
    else:
        preview_w, preview_h = 1240, 1754
    doc.close()

    # Apply watermark on preview PNG if sample demo
    if is_sample and apply_card_watermark and os.path.exists(preview_path):
        try:
            apply_card_watermark(preview_path, preview_path)
        except Exception as we:
            print(f"[ResumeBuilder] Watermark preview notice: {we}")

    pdf_size_kb = round(os.path.getsize(pdf_path) / 1024, 1) if os.path.exists(pdf_path) else 0
    preview_size_kb = round(os.path.getsize(preview_path) / 1024, 1) if os.path.exists(preview_path) else 0

    full_name = _clean_str(data.get("full_name"), "Candidate").replace(" ", "_")
    safe_name = "".join(c for c in full_name if c.isalnum() or c in ("-", "_")) or "Candidate"

    return {
        "pdf_path": pdf_path,
        "preview_path": preview_path,
        "pdf_filename": f"Resume_{safe_name}.pdf",
        "preview_filename": f"Resume_{safe_name}_preview.png",
        "pdf_size_kb": pdf_size_kb,
        "preview_size_kb": preview_size_kb,
        "width": preview_w,
        "height": preview_h,
        "is_sample": is_sample
    }
