import os
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import session, redirect, url_for, flash, current_app
from functools import wraps
from PIL import Image
from config import Config
from datetime import datetime # Added for the copyright year in the email footer

# --- Decorators for Role-Based Access ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        account_type = session.get('account_type')
        current_app.logger.info(f"Admin check: account_type in session is '{account_type}'")
        if account_type != 'admin':
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for('core.profile'))
        return f(*args, **kwargs)
    return decorated_function

def president_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth.login'))
        account_type = session.get('account_type')
        if account_type not in ('admin', 'president'):
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for('core.profile'))
        return f(*args, **kwargs)
    return decorated_function

# --- Helper to check user roles (for templates) ---
def inject_user_roles():
    is_admin = False
    is_president = False
    if 'account_type' in session:
        if session['account_type'] == 'admin':
            is_admin = True
            is_president = True
        elif session['account_type'] == 'president':
            is_president = True
    return dict(is_admin=is_admin, is_president=is_president)


# --- Helper Function to Check PNG Transparency ---
def check_transparency(file_stream):
    """
    Checks if a PNG image stream has at least one non-opaque pixel.
    """
    try:
        img = Image.open(file_stream)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        alpha = img.getchannel('A')
        unique_alphas = set(alpha.getdata())
        if len(unique_alphas) > 1:
            return True 
        if len(unique_alphas) == 1 and 255 not in unique_alphas:
            return True 
        return False
    except Exception as e:
        print(f"Error checking transparency: {e}")
        return False

# --- Helper Function to Send Email Notifications (SMTP + Professional Design) ---
def send_status_email(to_email, subject, body):
    """
    Sends an email notification using the configured SMTP server with a professional HTML template.
    """
    try:
        # Validate required SMTP configuration
        if not Config.SMTP_EMAIL or not Config.SMTP_PASSWORD:
            raise ValueError("SMTP_EMAIL and SMTP_PASSWORD environment variables must be set.")
        
        # 'alternative' allows sending both HTML and Plain Text
        msg = MIMEMultipart('alternative')
        # Set the sender name explicitly to 'CCS SBO' followed by the email in brackets
        msg['From'] = f"CCS SBO <{Config.SENDER_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject

        # --- DESIGN LOGIC ---
        # Determine color scheme and icon based on subject keywords
        # Default is Blue (#2563EB) matching the sample design
        header_color = "#2563EB" 
        status_icon = "🔔"
        
        if "Disapproved" in subject:
            header_color = "#DC2626" # Red for disapproval
            status_icon = "⚠️"
        elif "Approved" in subject:
            header_color = "#16A34A" # Green for approval
            status_icon = "✅"

        # Try to generate a link back to the portal login page
        try:
            portal_link = url_for('auth.login', _external=True)
        except:
            portal_link = "#"

        # Format body content: Convert newlines to breaks for HTML
        formatted_body = body.replace("\n", "<br>")

        # URL for the logo (Using the specific LSPU URL from your sample)
        logo_url = "https://lnbjifvircxceupkcpnl.supabase.co/storage/v1/object/public/pictures/lspu.png"

        # Professional HTML Template (Matching the provided Verify Email design)
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
        <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>{subject}</title>
            <style>
                /* Reset styles */
                body {{ margin: 0; padding: 0; width: 100%; -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
                table, td {{ border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
                img {{ border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; -ms-interpolation-mode: bicubic; }}
                
                /* Dark Mode Support */
                @media (prefers-color-scheme: dark) {{
                    .body-bg {{ background-color: #1a1a1a !important; }}
                    .container-bg {{ background-color: #2d2d2d !important; }}
                    .text-content {{ color: #e0e0e0 !important; }}
                    .text-secondary {{ color: #b0b0b0 !important; }}
                    .border-color {{ border-color: #444444 !important; }}
                }}
            </style>
        </head>
        <body class="body-bg" style="margin:0; padding:0; background-color:#f4f6f8; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">

            <div style="display:none; font-size:1px; color:#f4f6f8; line-height:1px; max-height:0px; max-width:0px; opacity:0; overflow:hidden;">
                {subject} - Notification from CCS-SBO.
            </div>

            <table width="100%" border="0" cellspacing="0" cellpadding="0" role="presentation">
                <tr>
                    <td align="center" style="padding: 40px 15px;">
                        
                        <table width="100%" class="container-bg" style="max-width:600px; background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 8px 30px rgba(0,0,0,0.08);" cellspacing="0" cellpadding="0" role="presentation">

                            <tr>
                                <!-- Dynamic Accent Color Bar -->
                                <td style="background-color:{header_color}; height: 8px;"></td>
                            </tr>

                            <tr>
                                <td align="center" style="padding: 40px 40px 20px 40px;">
                                    <img src="{logo_url}" alt="LSPU CCS-SBO Logo" width="100" style="display:block; width:100px; height:auto;" />
                                </td>
                            </tr>

                            <tr>
                                <td align="center" style="padding: 0 40px;">
                                    <h1 class="text-content" style="margin: 0 0 20px 0; font-size:24px; color:#1f2937; font-weight:700; font-family:'Segoe UI', sans-serif;">
                                        {status_icon} {subject}
                                    </h1>
                                    <div class="text-secondary" style="margin: 0 0 24px 0; font-size:16px; color:#4b5563; line-height:1.6; text-align: left;">
                                        {formatted_body}
                                    </div>
                                </td>
                            </tr>

                            <tr>
                                <td align="center" style="padding-bottom: 30px;">
                                    <table border="0" cellspacing="0" cellpadding="0" role="presentation">
                                        <tr>
                                            <td align="center" style="border-radius: 6px;" bgcolor="{header_color}">
                                                <a href="{portal_link}" target="_blank" style="display: inline-block; padding: 16px 36px; font-family:'Segoe UI', sans-serif; font-size: 16px; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; letter-spacing: 0.5px;">
                                                    Login to Portal
                                                </a>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>

                            <tr>
                                <td style="padding: 0 40px;">
                                    <div class="border-color" style="height: 1px; background-color: #e5e7eb; line-height: 1px;">&nbsp;</div>
                                </td>
                            </tr>

                            <tr>
                                <td align="center" class="container-bg" style="background-color:#f9fafb; padding: 20px 40px; border-top: 1px solid #e5e7eb;">
                                    <p class="text-secondary" style="margin: 0; font-size:12px; color:#9ca3af; line-height:1.5;">
                                        This is an automated notification from the CCS Student Body Organization System.<br>Please do not reply to this email.
                                    </p>
                                    <p class="text-secondary" style="margin: 10px 0 0 0; font-size:12px; color:#9ca3af; font-weight: 600;">
                                        © {datetime.now().year} CCS-SBO Management System
                                    </p>
                                </td>
                            </tr>

                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        # Attach parts: Text first, then HTML (clients usually display the last supported part)
        part1 = MIMEText(body, 'plain')
        part2 = MIMEText(html_template, 'html')

        msg.attach(part1)
        msg.attach(part2)

        # Connect to server
        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls() # Secure the connection
        server.login(Config.SMTP_EMAIL, Config.SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(Config.SENDER_EMAIL, to_email, text)
        server.quit()
        print(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False