import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

def get_smtp_config():
    try:
        load_dotenv(override=True)
    except Exception:
        pass
    
    host = os.environ.get("SMTP_HOST", "").strip()
    port_str = os.environ.get("SMTP_PORT", "587").strip()
    port = int(port_str) if port_str.isdigit() else 587
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    from_email = os.environ.get("SMTP_FROM_EMAIL", "").strip() or user or "noreply@rapidpvc.com"
    from_name = os.environ.get("SMTP_FROM_NAME", "").strip() or "Rapid PVC Support"
    
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_email": from_email,
        "from_name": from_name,
        "is_configured": bool(host and user and password)
    }

def send_password_reset_email(to_email: str, user_name: str, reset_url: str) -> tuple[bool, str]:
    """
    Sends a professional password reset email.
    If SMTP credentials are not configured, prints the link to server console for testing.
    """
    config = get_smtp_config()
    display_name = user_name or "Valued Operator"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reset Your Password - Rapid PVC Pro</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background-color: #f1f5f9;
                margin: 0;
                padding: 30px 15px;
                color: #1e293b;
            }}
            .container {{
                max-width: 540px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
                border: 1px solid #e2e8f0;
            }}
            .header {{
                background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
                padding: 32px 24px;
                text-align: center;
            }}
            .header h1 {{
                color: #ffffff;
                margin: 0;
                font-size: 22px;
                font-weight: 800;
                letter-spacing: -0.5px;
            }}
            .header p {{
                color: #e0e7ff;
                margin: 6px 0 0 0;
                font-size: 13px;
                font-weight: 600;
            }}
            .content {{
                padding: 32px 28px;
            }}
            .greeting {{
                font-size: 16px;
                font-weight: 700;
                margin-bottom: 12px;
                color: #0f172a;
            }}
            .desc {{
                font-size: 14px;
                line-height: 1.6;
                color: #475569;
                margin-bottom: 24px;
            }}
            .btn-box {{
                text-align: center;
                margin: 30px 0;
            }}
            .btn {{
                background-color: #4f46e5;
                color: #ffffff !important;
                padding: 14px 32px;
                text-decoration: none;
                font-size: 15px;
                font-weight: 700;
                border-radius: 8px;
                display: inline-block;
                box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
            }}
            .warning {{
                background-color: #f8fafc;
                border-left: 4px solid #f59e0b;
                padding: 14px 16px;
                border-radius: 4px;
                margin-top: 24px;
            }}
            .warning p {{
                margin: 0;
                font-size: 12px;
                line-height: 1.5;
                color: #64748b;
            }}
            .footer {{
                background-color: #f8fafc;
                padding: 20px 24px;
                text-align: center;
                border-top: 1px solid #f1f5f9;
                font-size: 12px;
                color: #94a3b8;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Rapid PVC Card Pro</h1>
                <p>Security & Access Recovery</p>
            </div>
            <div class="content">
                <div class="greeting">Hello {display_name},</div>
                <div class="desc">
                    We received a request to reset the password for your Rapid PVC operator account associated with <strong>{to_email}</strong>.
                </div>
                <div class="btn-box">
                    <a href="{reset_url}" class="btn" target="_blank">Reset My Password &rarr;</a>
                </div>
                <div class="desc" style="font-size: 13px;">
                    This link is valid for <strong>15 minutes</strong> and can only be used once. If the button above doesn't work, copy and paste this URL into your browser:
                    <div style="margin-top: 8px; padding: 8px; background: #f1f5f9; border-radius: 6px; word-break: break-all; font-family: monospace; font-size: 11px; color: #475569;">
                        {reset_url}
                    </div>
                </div>
                <div class="warning">
                    <p><strong>Did not request this?</strong> If you did not make this request, you can safely ignore this email. Your password will remain unchanged.</p>
                </div>
            </div>
            <div class="footer">
                &copy; 2026 Rapid PVC Pro. All rights reserved. Secure Indian CSC Operator Tools.
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_text = f"""
Hello {display_name},

We received a request to reset your Rapid PVC account password ({to_email}).

Please click or open the link below to set a new password (valid for 15 minutes):
{reset_url}

If you did not request this, please ignore this email.

-- Rapid PVC Card Pro Team
"""

    if not config["is_configured"]:
        print(f"\n=======================================================")
        print(f" [EMAIL SERVICE - LOCAL TEST PREVIEW]")
        print(f" To: {to_email}")
        print(f" Reset URL: {reset_url}")
        print(f"=======================================================\n")
        return False, "SMTP not configured on server. Check server console for test reset link."
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset Your Password - Rapid PVC Card Pro"
        msg["From"] = f"{config['from_name']} <{config['from_email']}>"
        msg["To"] = to_email
        
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        
        server = smtplib.SMTP(config["host"], config["port"], timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config["user"], config["password"])
        server.sendmail(config["from_email"], [to_email], msg.as_string())
        server.quit()
        
        print(f"[Email Service] Password reset email successfully delivered to {to_email}")
        return True, "Password reset email sent successfully."
    except Exception as e:
        print(f"[Email Service Error] Failed to send email to {to_email}: {str(e)}")
        print(f"Fallback Reset URL: {reset_url}")
        return False, f"SMTP delivery failed: {str(e)}"

def send_contact_inquiry(sender_name: str, sender_email: str, category: str, message: str) -> tuple[bool, str]:
    """
    Sends or logs an inbound operator contact support inquiry.
    """
    config = get_smtp_config()
    admin_recipient = os.environ.get("ADMIN_EMAILS", "rapidpvccard@gmail.com").split(",")[0].strip() or "rapidpvccard@gmail.com"

    print(f"\n=======================================================")
    print(f" [INBOUND CONTACT INQUIRY]")
    print(f" From: {sender_name} <{sender_email}>")
    print(f" Category: {category}")
    print(f" Message: {message}")
    print(f" Admin Recipient: {admin_recipient}")
    print(f"=======================================================\n")

    if not config["is_configured"]:
        return True, "Inquiry recorded in server logs (SMTP not configured)."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Rapid PVC Support] {category} from {sender_name}"
        msg["From"] = f"{config['from_name']} <{config['from_email']}>"
        msg["To"] = admin_recipient
        msg["Reply-To"] = sender_email

        plain_text = f"Contact Inquiry Received:\nName: {sender_name}\nEmail: {sender_email}\nCategory: {category}\nMessage:\n{message}\n"
        html_content = f"""
        <div style="font-family: sans-serif; padding: 20px; color: #0f172a; max-width: 600px; border: 1px solid #e2e8f0; border-radius: 10px;">
            <h2 style="color: #2563eb; margin-top: 0;">New Support Ticket Received</h2>
            <p><strong>From:</strong> {sender_name} (&lt;{sender_email}&gt;)</p>
            <p><strong>Category:</strong> {category}</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 15px 0;">
            <p><strong>Message:</strong></p>
            <div style="background: #f8fafc; padding: 15px; border-radius: 8px; white-space: pre-wrap;">{message}</div>
        </div>
        """
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        server = smtplib.SMTP(config["host"], config["port"], timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config["user"], config["password"])
        server.sendmail(config["from_email"], [admin_recipient], msg.as_string())
        server.quit()
        return True, "Support email dispatched successfully to admin."
    except Exception as e:
        print(f"[Contact Email Error] Could not dispatch to admin: {str(e)}")
        return True, "Inquiry saved to server log."

