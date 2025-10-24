import os
from supabase import create_client, Client
from config import Config # <-- Import the Config class

# --- THIS IS THE FIX ---
# Access the variables *from* the Config class
SUPABASE_URL = Config.SUPABASE_URL
SUPABASE_KEY = Config.SUPABASE_KEY
SUPABASE_SERVICE_KEY = Config.SUPABASE_SERVICE_KEY
# --- END OF FIX ---

# Client for general use
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# Admin client for protected actions like deleting users
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

