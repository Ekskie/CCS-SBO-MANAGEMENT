import os
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import supabase, supabase_admin
from config import Config
from utils import check_transparency
import re

auth_bp = Blueprint('auth', __name__,
                    template_folder='../templates/client',
                    static_folder='../static')

@auth_bp.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('core.profile'))
    return render_template('./index.html')

@auth_bp.route('/about')
def about():
    return render_template('./about.html')

@auth_bp.route('/team')
def team():
    return render_template('./team.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')

        if not student_id or not password:
            flash('Student ID and password are required.', category="error")
            return render_template('login.html')

        try:
            profile_response = supabase.table("profiles").select("*").eq("student_id", student_id).single().execute()

            if not profile_response.data:
                flash("Invalid Student ID or password.", category="error")
                return render_template('login.html')

            profile = profile_response.data
            email = profile['email']

            auth_response = supabase.auth.sign_in_with_password({
                'email': email,
                'password': password,
            })

            if auth_response.user:
                if not auth_response.user.email_confirmed_at:
                    flash('Please verify your email address before logging in.')
                    return render_template('login.html')
                    
                session['user_id'] = auth_response.user.id
                session['email'] = email
                session['student_id'] = student_id
                session['full_name'] = profile.get('first_name') + ' ' + profile.get('last_name')

                session['account_type'] = profile.get('account_type')
                session['program'] = profile.get('program')
                session['year_level'] = profile.get('year_level')
                session['section'] = profile.get('section')
                session['major'] = profile.get('major')
                
                if profile.get('account_type') == 'admin':
                    return redirect(url_for('admin.admin_dashboard'))
                elif profile.get('account_type') == 'president':
                    return redirect(url_for('president.president_dashboard'))
                else:
                    return redirect(url_for('core.profile'))
            else:
                flash('Invalid Student ID or password.', category="error")
                
        except Exception as e:
            print(f"Login error: {e}")
            flash(f"Invalid Student ID or password.", category="error")

    return render_template('login.html')


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not email:
            flash("Email is required.")
            return render_template("register.html")
            
        if not password or not confirm_password:
            flash("Password and confirmation are required.")
            return render_template("register.html")
            
        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("register.html")

        first_name = request.form.get("first_name")
        middle_name = request.form.get("middle_name")
        suffix_name = request.form.get("suffix_name")
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
            return render_template("register.html")
            
        if not picture_file or not picture_file.filename:
            flash("1x1 Picture is required.")
            return render_template("register.html")
        
        picture_bytes = picture_file.read()
        
        if len(picture_bytes) > Config.MAX_FILE_SIZE:
            flash(f"Picture file size must be less than {Config.MAX_FILE_SIZE // 1024 // 1024}MB.")
            return render_template("register.html")

        if not signature_file or not signature_file.filename:
            flash("Signature is required.")
            return render_template("register.html")
        
        signature_bytes = signature_file.read()

        if len(signature_bytes) > Config.MAX_FILE_SIZE:
            flash(f"Signature file size must be less than {Config.MAX_FILE_SIZE // 1024 // 1024}MB.")
            return render_template("register.html")

        if not signature_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            flash("Signature must be a valid PNG file.")
            return render_template("register.html")

        signature_stream = io.BytesIO(signature_bytes)
        if not check_transparency(signature_stream):
            flash("Signature PNG must have a transparent background.")
            return render_template("register.html")
            
        if year_level in ("3rd Year", "4th Year"):
            if program in ("BSIT", "BSCS"):
                if not major:
                    flash(f"Major is required for 3rd and 4th year {program} students.")
                    return render_template("register.html")
            else:
                 major = None
        else:
            major = None
            
        try:
            # Step 1: Check if student ID already exists
            existing_student = supabase.table("profiles").select("student_id").eq("student_id", student_id).execute()
            if existing_student.data:
                flash("This Student ID is already registered.", category="error")
                return render_template("register.html")
            
            # --- NEW CHECK: Check if Email already exists ---
            existing_email = supabase.table("profiles").select("email").eq("email", email).execute()
            if existing_email.data:
                flash("This Email Address is already registered.")
                return render_template("register.html")
            # ------------------------------------------------

            # Step 2: Create Auth User
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "email_redirect_to": url_for('auth.auth_callback', _external=True)
                }
            })

            user_id = None
            if auth_response.user:
                user_id = auth_response.user.id
                
                # Step 3: Upload files
                try:
                    pic_ext = os.path.splitext(picture_file.filename)[1]
                    pic_file_name = f"{student_id}_picture{pic_ext}"
                    supabase.storage.from_("pictures").upload(
                        pic_file_name, 
                        picture_bytes, 
                        {"content-type": picture_file.mimetype, "upsert": "true"}
                    )
                    picture_url = supabase.storage.from_("pictures").get_public_url(pic_file_name)

                    sig_ext = os.path.splitext(signature_file.filename)[1]
                    sig_file_name = f"{student_id}_signature{sig_ext}"
                    supabase.storage.from_("signatures").upload(
                        sig_file_name, 
                        signature_bytes, 
                        {"content-type": signature_file.mimetype, "upsert": "true"}
                    )
                    signature_url = supabase.storage.from_("signatures").get_public_url(sig_file_name)
                    
                except Exception as upload_error:
                    supabase_admin.auth.admin.delete_user(user_id)
                    flash(f"File upload failed: {str(upload_error)}. Please try registering again.")
                    return render_template("register.html")

                # Step 4: Create Profile
                profile_data = {
                    "id": user_id,
                    "email": email,
                    "student_id": student_id,
                    "first_name": first_name,
                    "middle_name": middle_name,
                    "suffix_name": suffix_name,
                    "last_name": last_name,
                    "program": program,
                    "semester": semester,
                    "year_level": year_level,
                    "section": section,
                    "major": major,
                    "picture_url": picture_url,
                    "signature_url": signature_url,
                    "account_type": "student",
                    "picture_status": "pending",
                    "signature_status": "pending",
                    "picture_disapproval_reason": None,
                    "signature_disapproval_reason": None
                }
                
                insert_response = supabase.table("profiles").insert(profile_data).execute()

                if not (insert_response.data and len(insert_response.data) > 0):
                    supabase_admin.auth.admin.delete_user(user_id)
                    supabase.storage.from_("pictures").remove([pic_file_name])
                    supabase.storage.from_("signatures").remove([sig_file_name])
                    flash(f"Auth user created, but profile creation failed. Please try again.")
                    return render_template("register.html")

                flash("Registration initiated. Please check your email to verify your account.")
                return render_template("register.html", category="success")
            
            else:
                flash("Registration failed. User might already exist or another error occurred.")
                return render_template("register.html", category="error")

        except Exception as e:
            if "User already exists" in str(e):
                flash("This email is already registered. Please try logging in or reset your password.")
            else:
                flash(f"Error during registration: {str(e)}")
            return render_template("register.html", category="error" )

    return render_template("register.html")

@auth_bp.route("/auth_callback")
def auth_callback():
    return redirect(url_for('auth.login', registered='success'))

@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash("Please enter your email address.")
            return render_template('forgot_password.html')
            
        try:
            profile_res = supabase.table("profiles").select("email").eq("email", email).execute()
            if not profile_res.data:
                flash("No account is registered with that email address.")
                return render_template('forgot_password.html')

            session['reset_email'] = email
            session['email_just_sent'] = True

            supabase.auth.reset_password_for_email(
                email,
                { "redirect_to": url_for("auth.login", _external=True) }
            )
            
            return redirect(url_for('auth.check_email'))
            
        except Exception as e:
            flash(f"An error occurred: {str(e)}")
            return render_template('forgot_password.html')
            
    return render_template('forgot_password.html')

@auth_bp.route('/check_email', methods=['GET', 'POST'])
def check_email():
    email = session.get('reset_email')
    auto_start = session.pop('email_just_sent', False) 
    
    if not email:
        flash("Session expired. Please try resetting your password again.")
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        try:
            supabase.auth.reset_password_for_email(
                email,
                { "redirect_to": url_for("auth.login", _external=True) }
            )
            flash('Email resent successfully! Please check your inbox.')
            auto_start = True 
            
        except Exception as e:
            flash(f"Error resending email: {str(e)}")

    return render_template('check_email.html', email=email, auto_start=auto_start)

@auth_bp.route('/resend_verification', methods=['POST'])
def resend_verification():
    email = request.form.get('email')
    
    if not email:
        flash("Email is required.", category="error")
        return redirect(url_for('auth.register'))

    # 1. Check if the user actually exists in the 'profiles' table first
    #    (This prevents spamming random emails)
    try:
        profile_res = supabase.table("profiles").select("email").eq("email", email).single().execute()
        
        if not profile_res.data:
            flash("No account found with this email. Please register first.", category="error")
            return redirect(url_for('auth.register'))

        # 2. Use Supabase to resend the confirmation email
        #    Note: Supabase's `resend` method handles checking if the user is already verified.
        #    If verified, it might not send, or will send a "password reset" style email depending on config.
        #    For unverified users, it sends the signup confirmation link again.
        response = supabase.auth.resend({
            "type": "signup",
            "email": email,
            "options": {
                "email_redirect_to": url_for('auth.auth_callback', _external=True)
            }
        })
        
        # Supabase Python client doesn't always throw on rate limit, but check response if needed.
        # Generally, if no exception, it worked.
        
        flash("If an unverified account exists, a new verification email has been sent.", category="success")

    except Exception as e:
        # Handle specific Supabase errors if possible (e.g., rate limits)
        print(f"Resend verification error: {e}")
        if "rate limit" in str(e).lower():
             flash("Please wait a moment before requesting another email.", category="error")
        elif "Email not found" in str(e): 
             # Should be caught by the profile check above, but as a fallback:
             flash("No account found with this email.", category="error")
        else:
             flash(f"Error sending email: {str(e)}", category="error")

    return redirect(url_for('auth.register'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    supabase.auth.sign_out()
    flash('You have been logged out.')
    return redirect(url_for('auth.login'))