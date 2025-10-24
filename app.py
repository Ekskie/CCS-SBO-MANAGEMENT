import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from collections import defaultdict
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import string
from functools import wraps
from datetime import datetime
import io              # Import for in-memory stream
from PIL import Image  # Import Pillow

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Supabase Configuration ---
SUPABASE_URL = "https://lnbjifvircxceupkcpnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxuYmppZnZpcmN4Y2V1cGtjcG5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAxMDQwMTQsImV4cCI6MjA3NTY4MDAxNH0._43eZLux5YGYyeSB3ztctYszDAK05rkhNxJGV0Is_5w"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Admin Configuration ---
# !!! IMPORTANT: Add your registered admin email here !!!
ADMIN_EMAILS = {"admin@example.com", "dennrick.agustin@lspu.edu.ph"}

# --- File Size Limit ---
MAX_FILE_SIZE = 5 * 1024 * 1024 # 5 MB

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

# --- Admin Decorator ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'email' not in session or session['email'] not in ADMIN_EMAILS:
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for('profile'))
        return f(*args, **kwargs)
    return decorated_function

# --- Helper to check if user is admin (for templates) ---
@app.context_processor
def inject_user_is_admin():
    is_admin = False
    if 'email' in session and session['email'] in ADMIN_EMAILS:
        is_admin = True
    return dict(is_admin=is_admin)

# --- Main Routes ---

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return render_template('client/login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')

        if not student_id or not password:
            flash('Student ID and password are required.')
            return render_template('client/login.html')

        try:
            profile_response = supabase.table("profiles").select("email").eq("student_id", student_id).execute()

            if not profile_response.data:
                flash("Invalid Student ID or password.")
                return render_template('client/login.html')

            email = profile_response.data[0]['email']

            auth_response = supabase.auth.sign_in_with_password({
                'email': email,
                'password': password,
            })

            if auth_response.user:
                if not auth_response.user.email_confirmed_at:
                    flash('Please verify your email address before logging in.')
                    return render_template('client/login.html')
                    
                session['user_id'] = auth_response.user.id
                session['email'] = email
                session['student_id'] = student_id
                
                if email in ADMIN_EMAILS:
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('profile'))
            else:
                flash('Invalid Student ID or password.')
                
        except Exception as e:
            flash(f"Invalid Student ID or password.")

    return render_template('client/login.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not email:
            flash("Email is required.")
            return render_template("client/register.html")
            
        if not password or not confirm_password:
            flash("Password and confirmation are required.")
            return render_template("client/register.html")
            
        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("client/register.html")

        first_name = request.form.get("first_name")
        middle_name = request.form.get("middle_name")
        last_name = request.form.get("last_name")
        student_id = request.form.get("student_id")
        program = request.form.get("program")
        semester = request.form.get("semester")
        year_level = request.form.get("year_level")
        section = request.form.get("section")
        major = request.form.get("major")
        
        picture_file = request.files.get('picture')
        signature_file = request.files.get('signature')

        if not all([first_name, last_name, student_id, program, semester, year_level, section]):
            flash("Please fill out all required fields.")
            return render_template("client/register.html")
            
        if not picture_file or not picture_file.filename:
            flash("1x1 Picture is required.")
            return render_template("client/register.html")
        # Read picture bytes early for validation
        picture_bytes = picture_file.read()
        
        # --- New File Size Validation ---
        if len(picture_bytes) > MAX_FILE_SIZE:
            flash(f"Picture file size must be less than {MAX_FILE_SIZE // 1024 // 1024}MB.")
            return render_template("client/register.html")

        if not signature_file or not signature_file.filename:
            flash("Signature is required.")
            return render_template("client/register.html")
        # Read signature bytes early for validation
        signature_bytes = signature_file.read()

        # --- New File Size Validation ---
        if len(signature_bytes) > MAX_FILE_SIZE:
            flash(f"Signature file size must be less than {MAX_FILE_SIZE // 1024 // 1024}MB.")
            return render_template("client/register.html")

        # --- New Signature Validation Logic ---
        # 1. Check if it's a real PNG
        if not signature_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            flash("Signature must be a valid PNG file.")
            return render_template("client/register.html")

        # 2. Check for transparency
        signature_stream = io.BytesIO(signature_bytes)
        if not check_transparency(signature_stream):
            flash("Signature PNG must have a transparent background.")
            return render_template("client/register.html")
        # --- End of New Validation Logic ---
            
        # --- Major Validation ---
        if year_level in ("3rd Year", "4th Year"):
            if not major:
                flash("Major is required for 3rd and 4th year students.")
                return render_template("client/register.html")
        else:
            major = None # Set major to None (NULL) for 1st/2nd year
            
        try:
            # Step 1: Check if student ID already exists
            existing_student = supabase.table("profiles").select("student_id").eq("student_id", student_id).execute()
            if existing_student.data:
                flash("This Student ID is already registered.")
                return render_template("client/register.html")
            
            # Step 2: Create Auth User
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "email_redirect_to": url_for('auth_callback', _external=True)
                }
            })

            user_id = None
            if auth_response.user:
                user_id = auth_response.user.id
                
                # Step 3: Upload files
                try:
                    pic_ext = os.path.splitext(picture_file.filename)[1]
                    pic_file_name = f"{student_id}_picture{pic_ext}"
                    # We already read the bytes, so just pass them
                    supabase.storage.from_("pictures").upload(
                        pic_file_name, 
                        picture_bytes, 
                        {"content-type": picture_file.mimetype, "upsert": "true"}
                    )
                    picture_url = supabase.storage.from_("pictures").get_public_url(pic_file_name)

                    sig_ext = os.path.splitext(signature_file.filename)[1]
                    sig_file_name = f"{student_id}_signature{sig_ext}"
                    # We already read the bytes, so just pass them
                    supabase.storage.from_("signatures").upload(
                        sig_file_name, 
                        signature_bytes, 
                        {"content-type": signature_file.mimetype, "upsert": "true"}
                    )
                    signature_url = supabase.storage.from_("signatures").get_public_url(sig_file_name)
                    
                except Exception as upload_error:
                    # If upload fails, we must delete the auth user to let them try again
                    supabase.auth.admin.delete_user(user_id)
                    flash(f"File upload failed: {str(upload_error)}. Please try registering again.")
                    return render_template("client/register.html")

                # Step 4: Create Profile
                profile_data = {
                    "id": user_id,
                    "email": email,
                    "student_id": student_id,
                    "first_name": first_name,
                    "middle_name": middle_name,
                    "last_name": last_name,
                    "program": program,
                    "semester": semester,
                    "year_level": year_level,
                    "section": section,
                    "major": major,
                    "picture_url": picture_url,
                    "signature_url": signature_url
                }
                
                insert_response = supabase.table("profiles").insert(profile_data).execute()

                if not (insert_response.data and len(insert_response.data) > 0):
                    # If profile insert fails, delete auth user and files
                    supabase.auth.admin.delete_user(user_id)
                    supabase.storage.from_("pictures").remove([pic_file_name])
                    supabase.storage.from_("signatures").remove([sig_file_name])
                    flash(f"Auth user created, but profile creation failed. Please try again.")
                    return render_template("client/register.html")

                flash("Registration initiated. Please check your email to verify your account.")
                return render_template("client/register.html")
            
            else:
                flash("Registration failed. User might already exist or another error occurred.")
                return render_template("client/register.html")

        except Exception as e:
            if "User already exists" in str(e):
                flash("This email is already registered. Please try logging in or reset your password.")
            else:
                flash(f"Error during registration: {str(e)}")
            return render_template("client/register.html")

    return render_template("/client/register.html")

@app.route("/auth_callback")
def auth_callback():
    # This is the page the user lands on after clicking the verification link
    # It redirects them to the login page with a success flag
    return redirect(url_for('login', registered='success'))

# --- NEW: Forgot Password Routes ---

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash("Please enter your email address.")
            return render_template('client/forgot_password.html')
            
        try:
            # Check if email exists in profiles (user-friendly feedback)
            profile_res = supabase.table("profiles").select("email").eq("email", email).execute()
            if not profile_res.data:
                flash("No account is registered with that email address.")
                return render_template('client/forgot_password.html')

            # --- THIS IS THE FIX ---
            # The 'redirect_to' argument is NOT used in the Python client.
            # This must be configured in your Supabase project's
            # Authentication > URL Configuration settings.
            supabase.auth.reset_password_for_email(email=email)
            # --- END OF FIX ---
            
            # Don't flash a message here, just send them to the confirmation page
            return redirect(url_for('check_email'))
            
        except Exception as e:
            flash(f"An error occurred: {str(e)}")
            return render_template('client/forgot_password.html')
            
    # GET request
    return render_template('client/forgot_password.html')

@app.route('/check_email')
def check_email():
    # This is just a simple page to tell the user to check their email
    return render_template('client/check_email.html')


# --- Profile and Other Routes ---

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Please log in to view your profile.')
        return redirect(url_for('login'))

    try:
        user_id = session['user_id']
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        
        if response.data:
            user_profile = response.data[0]
            return render_template('client/profile.html', profile=user_profile)
        else:
            flash('Profile not found. Please contact admin.')
            # Log them out if their profile is gone
            session.clear()
            return redirect(url_for('login'))
    except Exception as e:
        flash(f"Error fetching profile: {str(e)}")
        return redirect(url_for('login'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        flash('Please log in to update your profile.')
        return redirect(url_for('login'))

    user_id = session['user_id']
    response = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if not response.data:
        flash('Profile not found.')
        return redirect(url_for('profile'))

    user = response.data[0]
    student_id = user.get('student_id') # Get existing student_id

    if not student_id:
        flash('Cannot update profile: Student ID is missing.')
        return redirect(url_for('profile'))

    year_level = request.form.get('year_level', user['year_level'])
    major = request.form.get('major', user['major'])

    # --- Major Validation ---
    if year_level in ("3rd Year", "4th Year"):
        if not major:
            flash("Major is required for 3rd and 4th year students.")
            return redirect(url_for('profile'))
    else:
        major = None # Set major to None (NULL) for 1st/2nd year

    update_data = {
        "first_name": request.form.get('first_name', user['first_name']),
        "middle_name": request.form.get('middle_name', user['middle_name']),
        "last_name": request.form.get('last_name', user['last_name']),
        "program": request.form.get('program', user['program']),
        "semester": request.form.get('semester', user['semester']),
        "year_level": year_level,
        "section": request.form.get('section', user['section']),
        "major": major,
        "picture_url": user.get('picture_url'),
        "signature_url": user.get('signature_url')
    }

    try:
        picture_file = request.files.get('picture')
        signature_file = request.files.get('signature')

        if picture_file and picture_file.filename:
            # Check size on update
            picture_bytes = picture_file.read()
            if len(picture_bytes) > MAX_FILE_SIZE:
                flash(f"Picture file size must be less than {MAX_FILE_SIZE // 1024 // 1024}MB.")
                return redirect(url_for('profile'))
                
            file_ext = os.path.splitext(picture_file.filename)[1]
            file_name = f"{student_id}_picture{file_ext}"
            supabase.storage.from_("pictures").upload(
                file_name, 
                picture_bytes, 
                {"content-type": picture_file.mimetype, "upsert": "true"}
            )
            public_url_response = supabase.storage.from_("pictures").get_public_url(file_name)
            update_data["picture_url"] = public_url_response

        if signature_file and signature_file.filename:
            # Check size on update
            signature_bytes = signature_file.read()
            if len(signature_bytes) > MAX_FILE_SIZE:
                flash(f"Signature file size must be less than {MAX_FILE_SIZE // 1024 // 1024}MB.")
                return redirect(url_for('profile'))

            # Check for PNG and transparency on update
            if not signature_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                flash("Signature must be a valid PNG file.")
                return redirect(url_for('profile'))
            signature_stream = io.BytesIO(signature_bytes)
            if not check_transparency(signature_stream):
                flash("Signature PNG must have a transparent background.")
                return redirect(url_for('profile'))
                
            file_ext = os.path.splitext(signature_file.filename)[1]
            file_name = f"{student_id}_signature{file_ext}"
            supabase.storage.from_("signatures").upload(
                file_name, 
                signature_bytes, 
                {"content-type": signature_file.mimetype, "upsert": "true"}
            )
            public_url_response = supabase.storage.from_("signatures").get_public_url(file_name)
            update_data["signature_url"] = public_url_response

        supabase.table("profiles").update(update_data).eq("id", user_id).execute()
        flash('Profile updated successfully.')

    except Exception as e:
        flash(f"Error updating profile: {str(e)}")

    return redirect(url_for('profile'))

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        flash('Please log in.')
        return redirect(url_for('login'))
    
    # This just renders the HTML fragment, which is loaded by profile.html's JS
    return render_template('client/settings.html')

@app.route('/logout')
def logout():
    session.clear()
    supabase.auth.sign_out()
    flash('You have been logged out.')
    return redirect(url_for('login'))


# --- Admin Section ---

@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    try:
        profiles_res = supabase.table("profiles").select("id", count='exact').execute()
        student_count = profiles_res.count
        
        programs_res = supabase.table("profiles").select("program").execute()
        program_count = len(set(p['program'] for p in programs_res.data if p.get('program')))
        
        return render_template('admin/dashboard.html', student_count=student_count, program_count=program_count)
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template('admin/dashboard.html', student_count=0, program_count=0)

@app.route('/admin/students')
@admin_required
def admin_students():
    try:
        search_name = request.args.get('search_name', '')
        filter_program = request.args.get('filter_program', '')
        filter_section = request.args.get('filter_section', '')

        # Base query
        query = supabase.table("profiles").select("*")

        # Apply filters
        if search_name:
            # This searches for the name in both first_name and last_name
            query = query.or_(f"first_name.ilike.%{search_name}%,last_name.ilike.%{search_name}%")
        if filter_program:
            query = query.eq('program', filter_program)
        if filter_section:
            query = query.eq('section', filter_section)

        # Execute query
        response = query.order("last_name", desc=False).execute()
        students = response.data

        # Get filter options for dropdowns
        programs_res = supabase.table("profiles").select("program").execute()
        sections_res = supabase.table("profiles").select("section").execute()
        
        programs = sorted(list(set(p['program'] for p in programs_res.data if p.get('program'))))
        sections = sorted(list(set(s['section'] for s in sections_res.data if s.get('section'))))

        return render_template(
            'admin/students.html', 
            students=students,
            programs=programs,
            sections=sections,
            search_name=search_name,
            filter_program=filter_program,
            filter_section=filter_section
        )
    except Exception as e:
        flash(f"Error fetching students: {str(e)}", "error")
        return render_template('admin/students.html', students=[], programs=[], sections=[])

@app.route('/admin/edit_student/<student_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_student(student_id):
    if request.method == 'POST':
        # Logic to UPDATE the student
        try:
            # Fetch the existing student profile to get student_id (for file naming)
            user_res = supabase.table("profiles").select("student_id").eq("id", student_id).single().execute()
            if not user_res.data:
                flash("Student profile not found.", "error")
                return redirect(url_for('admin_students'))
            
            student_num = user_res.data['student_id'] # The Student's ID number

            year_level = request.form.get('year_level')
            major = request.form.get('major')

            # --- Major Validation ---
            if year_level in ("3rd Year", "4th Year"):
                if not major:
                    flash("Major is required for 3rd and 4th year students.")
                    # We need to pass the student data back to the template on error
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('admin/edit_student.html', student=student_data)
            else:
                major = None # Set major to None (NULL) for 1st/2nd year

            update_data = {
                "first_name": request.form.get('first_name'),
                "middle_name": request.form.get('middle_name'),
                "last_name": request.form.get('last_name'),
                "program": request.form.get('program'),
                "semester": request.form.get('semester'),
                "year_level": year_level,
                "section": request.form.get('section'),
                "major": major,
            }

            # Handle file uploads (similar to update_profile)
            picture_file = request.files.get('picture')
            signature_file = request.files.get('signature')

            if picture_file and picture_file.filename:
                # Check size on update
                picture_bytes = picture_file.read()
                if len(picture_bytes) > MAX_FILE_SIZE:
                    flash(f"Picture file size must be less than {MAX_FILE_SIZE // 1024 // 1024}MB.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('admin/edit_student.html', student=student_data)
                    
                file_ext = os.path.splitext(picture_file.filename)[1]
                file_name = f"{student_num}_picture{file_ext}"
                supabase.storage.from_("pictures").upload(
                    file_name, picture_bytes, {"content-type": picture_file.mimetype, "upsert": "true"}
                )
                update_data["picture_url"] = supabase.storage.from_("pictures").get_public_url(file_name)

            if signature_file and signature_file.filename:
                # Check size on update
                signature_bytes = signature_file.read()
                if len(signature_bytes) > MAX_FILE_SIZE:
                    flash(f"Signature file size must be less than {MAX_FILE_SIZE // 1024 // 1024}MB.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('admin/edit_student.html', student=student_data)

                # Check for PNG and transparency on update
                if not signature_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                    flash("Signature must be a valid PNG file.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('admin/edit_student.html', student=student_data)
                signature_stream = io.BytesIO(signature_bytes)
                if not check_transparency(signature_stream):
                    flash("Signature PNG must have a transparent background.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('admin/edit_student.html', student=student_data)
                    
                file_ext = os.path.splitext(signature_file.filename)[1]
                file_name = f"{student_num}_signature{file_ext}"
                supabase.storage.from_("signatures").upload(
                    file_name, signature_bytes, {"content-type": signature_file.mimetype, "upsert": "true"}
                )
                update_data["signature_url"] = supabase.storage.from_("signatures").get_public_url(file_name)

            supabase.table("profiles").update(update_data).eq("id", student_id).execute()
            flash('Student profile updated successfully.')
            return redirect(url_for('admin_students'))

        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "error")
            return redirect(url_for('admin_edit_student', student_id=student_id))

    # GET request: Show the edit form
    try:
        response = supabase.table("profiles").select("*").eq("id", student_id).single().execute()
        if not response.data:
            flash("Student profile not found.", "error")
            return redirect(url_for('admin_students'))
        
        return render_template('admin/edit_student.html', student=response.data)
    except Exception as e:
        flash(f"Error fetching profile: {str(e)}", "error")
        return redirect(url_for('admin_students'))

@app.route('/admin/delete_student/<student_id>', methods=['POST'])
@admin_required
def admin_delete_student(student_id):
    try:
        # 1. Get profile data before deleting (for file names and auth ID)
        profile_res = supabase.table("profiles").select("id, student_id, picture_url, signature_url").eq("id", student_id).single().execute()
        
        if not profile_res.data:
            flash("Student not found.", "error")
            return redirect(url_for('admin_students'))
        
        profile = profile_res.data
        auth_user_id = profile['id'] # This is the auth.users.id

        # 2. Delete files from Storage
        try:
            if profile.get('picture_url'):
                pic_file_name = profile['picture_url'].split('/')[-1].split('?')[0] # Get filename from URL
                supabase.storage.from_("pictures").remove([pic_file_name])
            if profile.get('signature_url'):
                sig_file_name = profile['signature_url'].split('/')[-1].split('?')[0] # Get filename from URL
                supabase.storage.from_("signatures").remove([sig_file_name])
        except Exception as e:
            flash(f"Profile deleted, but failed to delete storage files: {str(e)}", "error")

        # 3. Delete from 'profiles' table (public schema)
        supabase.table("profiles").delete().eq("id", auth_user_id).execute()
        
        # 4. Delete from 'auth.users' (requires SERVICE_ROLE_KEY or admin privileges)
        # This uses the auth_user_id (which is the UUID)
        supabase.auth.admin.delete_user(auth_user_id)
        
        flash("Student deleted successfully (Auth, Profile, and Files).")
    except Exception as e:
        flash(f"Error deleting student: {str(e)}. You may need to manually delete the user from the Supabase Auth panel.", "error")
        
    return redirect(url_for('admin_students'))

@app.route('/admin/calendar')
@admin_required
def admin_calendar():
    # Placeholder for calendar functionality
    return render_template('admin/calendar.html')

@app.route('/admin/printing')
@admin_required
def admin_printing():
    try:
        # Get current filters from URL
        current_program = request.args.get('program', '')
        current_year = request.args.get('year_level', '')
        current_section = request.args.get('section', '')
        current_semester = request.args.get('semester', '')

        # Base query for filtering
        query = supabase.table("profiles").select("program, year_level, section, major, semester")

        # Apply filters
        if current_program:
            query = query.eq('program', current_program)
        if current_year:
            query = query.eq('year_level', current_year)
        if current_section:
            query = query.eq('section', current_section)
        if current_semester:
            query = query.eq('semester', current_semester)
            
        profiles = query.execute().data
        
        # Get all unique options for dropdowns (unfiltered)
        all_profiles_res = supabase.table("profiles").select("program, year_level, section, semester").execute()
        all_profiles_data = all_profiles_res.data
        
        all_programs = sorted(list(set(p['program'] for p in all_profiles_data if p.get('program'))))
        all_years = sorted(list(set(p['year_level'] for p in all_profiles_data if p.get('year_level'))), key=lambda x: x[0]) # Sort by '1st', '2nd'
        all_sections = sorted(list(set(p['section'] for p in all_profiles_data if p.get('section'))))
        all_semesters = sorted(list(set(p['semester'] for p in all_profiles_data if p.get('semester'))))

        # Build unique groups from the *filtered* profiles
        unique_groups = set()
        for profile in profiles:
            if not all([profile.get('program'), profile.get('year_level'), profile.get('section')]):
                continue 
            
            major_val = profile.get('major') or 'None' 
            semester_val = profile.get('semester') or 'N/A' # Get semester for the link
            
            key = (
                profile.get('program'), 
                profile.get('year_level'), 
                profile.get('section'),
                major_val,
                semester_val # Include semester in the key
            )
            unique_groups.add(key)
        
        sorted_groups = sorted(list(unique_groups))
        
        return render_template(
            'admin/printing.html', 
            groups=sorted_groups,
            all_programs=all_programs,
            all_years=all_years,
            all_sections=all_sections,
            all_semesters=all_semesters,
            current_program=current_program,
            current_year=current_year,
            current_section=current_section,
            current_semester=current_semester
        )
    except Exception as e:
        flash(f"Error fetching groups: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/print_preview')
@admin_required
def admin_print_preview():
    program = request.args.get('program')
    year_level = request.args.get('year_level')
    section = request.args.get('section')
    major = request.args.get('major') 
    semester = request.args.get('semester') # Get the semester

    # THIS IS THE CORRECTED CHECK
    if not all([program, year_level, section, major, semester]):
        flash("Error: Missing group information, including semester.", "error")
        return redirect(url_for('admin_printing'))

    try:
        query = supabase.table("profiles").select("*")
        query = query.eq("program", program)
        query = query.eq("year_level", year_level)
        query = query.eq("section", section)
        query = query.eq("semester", semester) # Filter by semester
        
        if major == 'None':
            query = query.is_("major", "null") # Check for NULL in database
        else:
            query = query.eq("major", major)

        # Remove the .order() from here
        response = query.execute()
        group_profiles = response.data

        if not group_profiles:
            flash(f"No profiles found for this group.", "error")
            return redirect(url_for('admin_printing'))

        members = []
        for p in group_profiles:
            full_name = f"{p.get('last_name', '')}, {p.get('first_name', '')} {p.get('middle_name', '')}".strip()
            # Construct the course string, handling the optional major
            course_parts = [p.get('program', ''), f"{p.get('year_level', '')}{p.get('section', '')}"]
            if p.get('major'):
                course_parts.append(p.get('major'))
            course = " - ".join(filter(None, course_parts)).strip() # "BSIT - 3rd YearA - NETAD"
            
            member = {
                'full_name': full_name,
                'student_id': p.get('student_id'),
                'course': course,
                'picture_url': p.get('picture_url'),
                'signature_url': p.get('signature_url')
            }
            members.append(member)
            
        # --- NEW SORTING LOGIC ---
        # Sort the list of dictionaries by the 'full_name' key
        # This guarantees correct alphabetical order (e.g., "Last, First")
        sorted_members = sorted(members, key=lambda m: m.get('full_name', ''))

        # --- Automation Logic ---
        # 1. Format Semester
        semester_display = f"{semester} Sem." # e.g., "1st Sem."
        
        # 2. Calculate Academic Year (e.g., AY 2025-2026)
        # We assume the academic year starts in August (month 8)
        today = datetime.now()
        current_year = today.year
        if today.month >= 8: # August to December
            academic_year = f"AY {current_year}-{current_year + 1}"
        else: # January to July
            academic_year = f"AY {current_year - 1}-{current_year}"
            
        # 3. Get Formatted Current Date
        generation_date = today.strftime("%B %d, %Y") # e.g., "October 24, 2025"

        return render_template(
            'print_template.html', 
            members=sorted_members, # Pass the new sorted list
            semester_display=semester_display,
            academic_year=academic_year,
            generation_date=generation_date
        )
    
    except Exception as e:
        flash(f"Error generating print preview: {str(e)}", "error")
        return redirect(url_for('admin_printing'))

# --- Run Application (Not used by Vercel) ---

if __name__ == '__main__':
    app.run(debug=True)

