import os
from dotenv import load_dotenv

load_dotenv() # Load .env file for local development

class Config:
    # --- THIS IS THE FIX ---
    # Read the static key from environment variables.
    # os.urandom(24) MUST NOT be used here.
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

