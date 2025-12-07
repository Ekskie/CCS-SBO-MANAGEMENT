import os
from dotenv import load_dotenv

load_dotenv() # Load .env file for local development

class Config:
    # Timezone Configuration
    TIMEZONE = 'Asia/Manila'  # Philippines timezone
    
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
    
    if not SECRET_KEY:
        raise ValueError("Error: FLASK_SECRET_KEY is not set. Please set it in your .env file or Vercel environment variables.")

    # Supabase keys
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    
    # File size
    MAX_FILE_SIZE = 5 * 1024 * 1024 # 5 MB

    if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_SERVICE_KEY:
        raise ValueError("Error: Supabase environment variables must be set.")
    # Other configurations can be added here
    # Add SMTP Settings
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp-relay.brevo.com") # Default Brevo host
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_EMAIL = os.getenv("SMTP_EMAIL") # Your Brevo Login Email
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") # Your Brevo Master Password or API Key
    SENDER_EMAIL = os.getenv("SENDER_EMAIL", "no-reply@yourdomain.com") # The 'From' address
