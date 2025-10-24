from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY

# Client for general use
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Admin client for protected actions like deleting users
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
