import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from collections import defaultdict

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Supabase Configuration ---
SUPABASE_URL = "https://lnbjifvircxceupkcpnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxuYmppZnZpcmN4Y2V1cGtjcG5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjAxMDQwMTQsImV4cCI6MjA3NTY4MDAxNH0._43eZLux5YGYyeSB3ztctYszDAK05rkhNxJGV0Is_5w"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Directory Setup ---
# Create directory for generated files if it doesn't exist
GENERATED_PRINTS_DIR = 'generated_prints'
if not os.path.exists(GENERATED_PRINTS_DIR):
    os.makedirs(GENERATED_PRINTS_DIR)

# --- Main Routes ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # --- MODIFICATION: Login with student_id ---
        student_id = request.form.get('student_id')
        password = request.form.get('password')

        if not student_id or not password:
            flash('Student ID and password are required.')
            return render_template('client/login.html')

        try:
            # Step 1: Find the email associated with the student_id
            profile_response = supabase.table("profiles").select("email").eq("student_id", student_id).execute()

            if not profile_response.data:
                flash("Invalid Student ID or password.")
                return render_template('client/login.html')

            email = profile_response.data[0]['email']

            # Step 2: Authenticate using the found email and provided password
            auth_response = supabase.auth.sign_in_with_password({
                'email': email,
                'password': password,
            })

            # Check for error in response
            if auth_response.user:
                # Check if email is confirmed
                if not auth_response.user.email_confirmed_at:
                    flash('Please verify your email address before logging in.')
                    return render_template('client/login.html')
                    
                session['user_id'] = auth_response.user.id
                session['email'] = email # Store email in session
                session['student_id'] = student_id # Store student_id in session
                flash('Login successful!')
                return redirect(url_for('profile'))
            else:
                flash('Invalid Student ID or password.')
                
        except Exception as e:
            # Catch exceptions from the API call itself
            flash(f"Invalid Student ID or password.")

    # Render the new bootstrap login template
    return render_template('client/login.html')


# --- UPDATED "PASSWORD" REGISTRATION ROUTE ---
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

        # Get other form data
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
            
        if not signature_file or not signature_file.filename:
            flash("Signature is required.")
            return render_template("client/register.html")
            
        try:
            # Step 1: Create the auth user in Supabase
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    # Tell Supabase where to redirect *after* email click
                    "email_redirect_to": url_for('auth_callback', _external=True)
                }
            })

            user_id = None
            if auth_response.user:
                user_id = auth_response.user.id
                
                # --- This logic was broken and in the wrong place ---
                try:
                    # Upload Picture
                    pic_ext = os.path.splitext(picture_file.filename)[1]
                    pic_file_name = f"{student_id}_picture{pic_ext}"
                    picture_bytes = picture_file.read()
                    supabase.storage.from_("pictures").upload(
                        pic_file_name, 
                        picture_bytes, 
                        {"content-type": picture_file.mimetype, "upsert": "true"}
                    )
                    picture_url = supabase.storage.from_("pictures").get_public_url(pic_file_name)

                    # Upload Signature
                    sig_ext = os.path.splitext(signature_file.filename)[1]
                    sig_file_name = f"{student_id}_signature{sig_ext}"
                    signature_bytes = signature_file.read()
                    supabase.storage.from_("signatures").upload(
                        sig_file_name, 
                        signature_bytes, 
                        {"content-type": signature_file.mimetype, "upsert": "true"}
                    )
                    signature_url = supabase.storage.from_("signatures").get_public_url(sig_file_name)
                    
                except Exception as upload_error:
                    # This is tricky. Auth user is created but files failed.
                    # A robust solution would delete the auth user here (requires admin key)
                    flash(f"User created, but file upload failed: {str(upload_error)}")
                    return render_template("client/register.html")

                # --- End File Uploads ---

                profile_data = {
                    "id": user_id,  # Link to the auth user
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
                    "picture_url": picture_url,       # Add picture URL
                    "signature_url": signature_url  # Add signature URL
                }
                
                insert_response = supabase.table("profiles").insert(profile_data).execute()

                if not (insert_response.data and len(insert_response.data) > 0):
                    flash(f"Auth user created, but profile creation failed. Please contact admin.")
                    return render_template("client/register.html")

                # --- STEP 1 SUCCESS ---
                # Show this message on the register page and wait for email click
                flash("Registration initiated. Please check your email to verify your account.")
                return render_template("client/register.html")
            
            else:
                # This 'else' was missing, causing the broken try/except
                flash("Registration failed. User might already exist or another error occurred.")
                return render_template("client/register.html")

        except Exception as e:
            if "User already exists" in str(e):
                flash("This email is already registered. Please try logging in or reset your password.")
            else:
                flash(f"Error during registration: {str(e)}")
            return render_template("client/register.html")

    # For GET request
    return render_template("/client/register.html")


# --- NEW ROUTE FOR STEP 2 ---
# This route is hit *after* the user clicks the verification link in their email.
@app.route("/auth_callback")
def auth_callback():
    # The user is now verified (Supabase handled this).
    # Redirect them to the login page with the 'registered' flag
    # This will trigger the success modal on login.html
    return redirect(url_for('login', registered='success'))


# --- Profile and Other Routes ---

@app.route('/profile')
def profile():
# ... (rest of the file is unchanged) ...
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
            # This case might happen if auth user exists but profile row was deleted
            flash('Profile not found. Please contact admin.')
            return render_template('client/profile.html', profile=None)
    except Exception as e:
        flash(f"Error fetching profile: {str(e)}")
        return redirect(url_for('login'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        flash('Please log in to update your profile.')
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Get current profile
    response = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if not response.data:
        flash('Profile not found.')
        return redirect(url_for('profile'))

    user = response.data[0]

    # Get form data, falling back to existing data
    update_data = {
        "first_name": request.form.get('first_name', user['first_name']),
        "middle_name": request.form.get('middle_name', user['middle_name']),
        "last_name": request.form.get('last_name', user['last_name']),
        "program": request.form.get('program', user['program']),
        "semester": request.form.get('semester', user['semester']),
        "year_level": request.form.get('year_level', user['year_level']),
        "section": request.form.get('section', user['section']),
        "major": request.form.get('major', user['major']),
        "picture_url": user.get('picture_url'),      # Default to existing
        "signature_url": user.get('signature_url')  # Default to existing
    }

    try:
        # Handle file uploads
        picture_file = request.files.get('picture')
        signature_file = request.files.get('signature')

        # Ensure student_id is present for file naming
        student_id = user.get('student_id')
        if not student_id:
            flash('Student ID is missing, cannot upload files.')
            return redirect(url_for('profile'))

        if picture_file and picture_file.filename:
            file_ext = os.path.splitext(picture_file.filename)[1]
            file_name = f"{student_id}_picture{file_ext}"
            picture_bytes = picture_file.read()
            
            supabase.storage.from_("pictures").upload(
                file_name, 
                picture_bytes, 
                {"content-type": picture_file.mimetype, "upsert": "true"}
            )
            public_url_response = supabase.storage.from_("pictures").get_public_url(file_name)
            update_data["picture_url"] = public_url_response

        if signature_file and signature_file.filename:
            file_ext = os.path.splitext(signature_file.filename)[1]
            file_name = f"{student_id}_signature{file_ext}"
            signature_bytes = signature_file.read()
            
            supabase.storage.from_("signatures").upload(
                file_name, 
                signature_bytes, 
                {"content-type": signature_file.mimetype, "upsert": "true"}
            )
            public_url_response = supabase.storage.from_("signatures").get_public_url(file_name)
            update_data["signature_url"] = public_url_response

        # Update profile table
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
    supabase.auth.sign_out() # Added this for proper server-side logout
    flash('You have been logged out.')
    return redirect(url_for('login'))

# --- Admin/Utility Route ---

@app.route('/generate_print_files')
def generate_print_files():
    # Optional: Secure this route
    # if 'user_id' not in session:
    #     flash('Access denied.')
    #     return redirect(url_for('login'))
    # TODO: Add admin role check

    try:
        # Fetch all profiles
        response = supabase.table("profiles").select("*").execute()
        profiles = response.data

        # Group by program, year_level, section
        groups = defaultdict(list)
        for profile in profiles:
            key = (profile.get('program', 'N/A'), profile.get('year_level', 'N/A'), profile.get('section', 'N/A'))
            groups[key].append(profile)

        generated_files = []

        for (program, year_level, section), group_profiles in groups.items():
            # Prepare members list
            members = []
            for p in group_profiles:
                full_name = f"{p.get('last_name', '')}, {p.get('first_name', '')} {p.get('middle_name', '')}".strip()
                course = f"{p.get('program', '')} - {p.get('year_level', '')}{p.get('section', '')} {p.get('major', '') or ''}".strip()
                member = {
                    'full_name': full_name,
                    'student_id': p.get('student_id'),
                    'course': course,
                    'picture_url': p.get('picture_url'),
                    'signature_url': p.get('signature_url')
                }
                members.append(member)

            # Split into chunks of 8
            chunk_size = 8
            for i in range(0, len(members), chunk_size):
                chunk = members[i:i + chunk_size]

                # Render template
                html_content = render_template('print_template.html', members=chunk)

                # File name
                page_num = (i // chunk_size) + 1
                safe_program = "".join(c if c.isalnum() else "_" for c in program)
                safe_year = "".join(c if c.isalnum() else "_" for c in str(year_level))
                safe_section = "".join(c if c.isalnum() else "_" for c in section)
                
                file_name = f"{safe_program}_{safe_year}_{safe_section}_{page_num}.html"
                file_path = os.path.join(GENERATED_PRINTS_DIR, file_name)

                # Write to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                generated_files.append(file_name)
        
        if not generated_files:
            return "No profiles found to generate files."

        return f"Generated files in '{GENERATED_PRINTS_DIR}' directory: {', '.join(generated_files)}"

    except Exception as e:
        return f"Error generating print files: {str(e)}"

# --- Run Application ---

if __name__ == '__main__':
    app.run(debug=True)

