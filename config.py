import os
from dotenv import load_dotenv

# Load variables from your .env file
load_dotenv()

# --- App Configuration ---
SECRET_KEY = os.urandom(24)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# --- Supabase Configuration ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Service key for admin actions

if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_SERVICE_KEY:
    raise ValueError("Error: SUPABASE_URL, SUPABASE_KEY, and SUPABASE_SERVICE_KEY must be set in your .env file.")
