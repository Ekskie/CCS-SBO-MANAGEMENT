import io
from PIL import Image
from functools import wraps
from flask import flash, redirect, url_for, session

# --- Helper Function to Check PNG Transparency ---
def check_transparency(file_stream):
    """
    Checks if a PNG image stream has at least one non-opaque pixel.
    """
    try:
        # Open the image from the in-memory stream
        img = Image.open(file_stream)
        
        # We are only interested in RGBA (Red, Green, Blue, Alpha)
        # If it's not, convert it to check its alpha
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
            
        # Get the alpha channel
        alpha = img.getchannel('A')
        
        # Get all unique values in the alpha channel.
        # This is much faster than checking every pixel.
        unique_alphas = set(alpha.getdata())
        
        # Check for transparency:
        # 1. If there's more than one alpha value, it must have transparency.
        # 2. If there's only one value, it must be less than 255.
        if len(unique_alphas) > 1:
            return True # e.g., {255, 0}
        if len(unique_alphas) == 1 and 255 not in unique_alphas:
            return True # e.g., {0}
            
        # If we're here, it means the only value is 255 (fully opaque)
        return False
        
    except Exception as e:
        print(f"Error checking transparency: {e}")
        # Fail-safe: if image is invalid, reject it.
        return False

# --- Decorators for Role-Based Access ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            # Note: url_for now uses the Blueprint name 'auth.login'
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth.login'))
        if session.get('account_type') != 'admin':
            flash("You do not have permission to access this page.", "error")
            # Note: url_for now uses the Blueprint name 'core.profile'
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
