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
        header_color = "#4F46E5" # Default Indigo/Blue
        status_icon = "🔔"
        
        if "Disapproved" in subject:
            header_color = "#DC2626" # Red
            status_icon = "⚠️"
        elif "Approved" in subject:
            header_color = "#16A34A" # Green
            status_icon = "✅"

        # Try to generate a link back to the portal login page
        try:
            portal_link = url_for('auth.login', _external=True)
        except:
            portal_link = "#"

        # Format body content: Convert newlines to breaks for HTML
        formatted_body = body.replace("\n", "<br>")

        # URL for the logo in the email header.
        # REPLACE THIS with the actual public URL of your logo (e.g. from Supabase Storage).
        # Since local files won't work in emails, you must use a public HTTP link.
        # Example: logo_url = "https://your-supabase-url.com/storage/v1/object/public/assets/logo.png"
        logo_url = "https://lnbjifvircxceupkcpnl.supabase.co/storage/v1/object/public/pictures/lspu.png" 

        # Professional HTML Template
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{subject}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f3f4f6; }}
                .email-wrapper {{ padding: 40px 10px; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
                
                /* HEADER STYLES */
                .header {{ background-color: {header_color}; color: #ffffff; padding: 30px 20px; text-align: center; }}
                .header img {{ max-height: 80px; margin-bottom: 15px; border-radius: 8px; background-color: white; padding: 5px; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; }}
                
                .content {{ padding: 35px 30px; color: #374151; line-height: 1.6; font-size: 16px; }}
                .status-badge {{ background-color: {header_color}15; color: {header_color}; padding: 8px 16px; border-radius: 50px; font-size: 14px; font-weight: bold; display: inline-block; margin-bottom: 20px; border: 1px solid {header_color}30; }}
                .footer {{ background-color: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #9ca3af; border-top: 1px solid #e5e7eb; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: {header_color}; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-weight: 600; margin-top: 25px; transition: opacity 0.2s; }}
                .button:hover {{ opacity: 0.9; }}
                a {{ color: {header_color}; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="container">
                    <div class="header">
                        <!-- Logo Image: Requires a public URL -->
                        <img src="{logo_url}" alt="CCS SBO Logo">
                        <h1>CCS SBO Management</h1>
                    </div>
                    <div class="content">
                        <div style="text-align: center;">
                            <span class="status-badge">{status_icon} {subject}</span>
                        </div>
                        
                        <p>{formatted_body}</p>
                        
                        <div style="text-align: center;">
                            <a href="{portal_link}" class="button">Login to Portal</a>
                        </div>
                    </div>
                    <div class="footer">
                        <p>This is an automated notification from the CCS Student Body Organization System.</p>
                        <p>&copy; {datetime.now().year} CCS SBO. All rights reserved.</p>
                    </div>
                </div>
            </div>
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