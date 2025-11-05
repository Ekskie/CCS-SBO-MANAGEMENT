import os
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import supabase
from utils import login_required, check_transparency
from config import Config # <-- Import Config class

core_bp = Blueprint('core', __name__,
                    template_folder='../templates/client')

@core_bp.route('/profile')
@login_required
def profile():
    try:
        user_id = session['user_id']
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        
        if response.data:
            user_profile = response.data[0]
            return render_template('profile.html', profile=user_profile)
        else:
            flash('Profile not found. Please contact admin.')
            # Log them out if their profile is gone
            session.clear()
            return redirect(url_for('auth.login'))
    except Exception as e:
        flash(f"Error fetching profile: {str(e)}")
        return redirect(url_for('auth.login'))

@core_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user_id = session['user_id']
    response = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if not response.data:
        flash('Profile not found.')
        return redirect(url_for('core.profile'))

    user = response.data[0]
    student_id = user.get('student_id') # Get existing student_id

    if not student_id:
        flash('Cannot update profile: Student ID is missing.')
        return redirect(url_for('core.profile'))

    year_level = request.form.get('year_level', user['year_level'])
    major = request.form.get('major', user['major'])
    program = request.form.get('program', user['program']) # Get program

    # --- Major Validation (from user update) ---
    if year_level in ("3rd Year", "4th Year"):
        if program in ("BSIT", "BSCS"): # Only require for BSIT/BSCS
            if not major:
                flash(f"Major is required for 3rd and 4th year {program} students.")
                return redirect(url_for('core.profile'))
        else:
            major = None # Set major to None (NULL) for BSIS
    else:
        major = None # Set major to None (NULL) for 1st/2nd year

    update_data = {
        "first_name": request.form.get('first_name', user['first_name']),
        "middle_name": request.form.get('middle_name', user['middle_name']),
        "last_name": request.form.get('last_name', user['last_name']),
        "program": program, # Use the program variable
        "semester": request.form.get('semester', user['semester']),
        "year_level": year_level,
        "section": request.form.get('section', user['section']),
        "major": major,
        "picture_url": user.get('picture_url'),
        "signature_url": user.get('signature_url'),
        # Get existing approval statuses
        "picture_status": user.get('picture_status'),
        "signature_status": user.get('signature_status'),
        "disapproval_reason": user.get('disapproval_reason')
    }

    try:
        picture_file = request.files.get('picture')
        signature_file = request.files.get('signature')

        if picture_file and picture_file.filename:
            # Check size on update
            picture_bytes = picture_file.read()
            if len(picture_bytes) > Config.MAX_FILE_SIZE: # <-- Use Config.MAX_FILE_SIZE
                flash(f"Picture file size must be less than {Config.MAX_FILE_SIZE // 1024 // 1024}MB.")
                return redirect(url_for('core.profile'))
                
            file_ext = os.path.splitext(picture_file.filename)[1]
            file_name = f"{student_id}_picture{file_ext}"
            supabase.storage.from_("pictures").upload(
                file_name, 
                picture_bytes, 
                {"content-type": picture_file.mimetype, "upsert": "true"}
            )
            public_url_response = supabase.storage.from_("pictures").get_public_url(file_name)
            update_data["picture_url"] = public_url_response
            
            # --- FIXED: Reset status on new upload ---
            update_data["picture_status"] = "pending"
            # Clear disapproval reason when new file is uploaded
            update_data["disapproval_reason"] = None # Or logic to only remove picture-related reasons

        if signature_file and signature_file.filename:
            # Check size on update
            signature_bytes = signature_file.read()
            if len(signature_bytes) > Config.MAX_FILE_SIZE: # <-- Use Config.MAX_FILE_SIZE
                flash(f"Signature file size must be less than {Config.MAX_FILE_SIZE // 1024 // 1024}MB.")
                return redirect(url_for('core.profile'))

            # Check for PNG and transparency on update
            if not signature_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                flash("Signature must be a valid PNG file.")
                return redirect(url_for('core.profile'))
            signature_stream = io.BytesIO(signature_bytes)
            if not check_transparency(signature_stream):
                flash("Signature PNG must have a transparent background.")
                return redirect(url_for('core.profile'))
                
            file_ext = os.path.splitext(signature_file.filename)[1]
            file_name = f"{student_id}_signature{file_ext}"
            supabase.storage.from_("signatures").upload(
                file_name, 
                signature_bytes, 
                {"content-type": signature_file.mimetype, "upsert": "true"}
            )
            public_url_response = supabase.storage.from_("signatures").get_public_url(file_name)
            update_data["signature_url"] = public_url_response
            
            # --- FIXED: Reset status on new upload ---
            update_data["signature_status"] = "pending"
            # Clear disapproval reason when new file is uploaded
            update_data["disapproval_reason"] = None # Or logic to only remove signature-related reasons

        supabase.table("profiles").update(update_data).eq("id", user_id).execute()
        flash('Profile updated successfully. Approval status has been reset for new uploads.')

    except Exception as e:
        flash(f"Error updating profile: {str(e)}")

    return redirect(url_for('core.profile'))

@core_bp.route('/settings')
@login_required
def settings():
    # This just renders the HTML fragment, which is loaded by profile.html's JS
    return render_template('settings.html')

@core_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Handles the change password form submission from the settings page."""
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_new_password')

    if not all([current_password, new_password, confirm_password]):
        flash("Please fill out all password fields.", "error")
        return redirect(url_for('core.settings')) # Redirects back, JS should open settings

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for('core.settings'))

    try:
        # 1. Verify the user's current password by trying to sign in
        user_email = session.get('email')
        if not user_email:
            flash("Session expired. Please log in again.", "error")
            return redirect(url_for('auth.login'))

        # This will test the current password.
        # It also refreshes the auth token, which is needed for the update.
        supabase.auth.sign_in_with_password({
            "email": user_email,
            "password": current_password
        })

        # 2. If sign-in is successful, update the password
        supabase.auth.update_user(attributes={"password": new_password})
        
        flash("Password updated successfully.", "success")
    
    except Exception as e:
        if "Invalid login credentials" in str(e):
            flash("Incorrect current password.", "error")
        else:
            flash(f"An error occurred: {str(e)}", "error")

    # Redirect back to the profile page. 
    return redirect(url_for('core.settings'))