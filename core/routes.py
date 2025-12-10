import os
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import supabase, supabase_admin  # Added supabase_admin
from config import Config
from utils import login_required, check_transparency

core_bp = Blueprint('core', __name__, template_folder='../templates')

@core_bp.route('/')
def index():
    return render_template('index.html')

@core_bp.route('/about')
def about():
    return render_template('about.html')

@core_bp.route('/team')
def team(): 
    return render_template('team.html')

@core_bp.route('/privacy')
def privacy(): 
    return render_template('privacy.html')

@core_bp.route('/terms')
def terms(): 
    return render_template('terms.html')


@core_bp.route('/profile')
@login_required
def profile():
    user_id = session.get('user_id')
    try:
        # Fetch the profile using the session user_id
        response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        profile_data = response.data
        
        if not profile_data:
            flash("Profile not found.", "error")
            # Clear session if profile not found to prevent redirect loops
            session.clear() 
            return redirect(url_for('auth.login'))

        return render_template('client/profile.html', profile=profile_data)
        
    except Exception as e:
        flash(f"Error fetching profile: {str(e)}", "error")
        # If it's a build error (like core.settings missing), it might crash here.
        # We redirect to index to be safe.
        return redirect(url_for('core.index'))

@core_bp.route('/settings')
@login_required
def settings():
    # This route is required for the 'Edit Personal Info' or settings link in profile.html
    return render_template('client/settings.html')

@core_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Handles the change password form submission from the settings page."""
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_new_password')

    if not all([current_password, new_password, confirm_password]):
        flash("Please fill out all password fields.", "error")
        return redirect(url_for('core.settings'))

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for('core.settings'))

    try:
        user_email = session.get('email')
        if not user_email:
            flash("Session expired. Please log in again.", "error")
            return redirect(url_for('auth.login'))

        # Verify current password by signing in
        supabase.auth.sign_in_with_password({
            "email": user_email,
            "password": current_password
        })

        # Update password
        supabase.auth.update_user({"password": new_password})
        
        flash("Password updated successfully.", "success")
    
    except Exception as e:
        if "Invalid login credentials" in str(e):
            flash("Incorrect current password.", "error")
        else:
            flash(f"An error occurred: {str(e)}", "error")

    return redirect(url_for('core.settings'))

@core_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user_id = session.get('user_id')
    
    try:
        # Check if account is locked first
        profile_check = supabase.table("profiles").select("is_locked").eq("id", user_id).single().execute()
        if profile_check.data and profile_check.data.get('is_locked'):
            flash("Your account is locked and cannot be edited. Please contact the administrator.", "error")
            return redirect(url_for('core.profile'))

        # Collect form data
        first_name = request.form.get('first_name')
        middle_name = request.form.get('middle_name')
        last_name = request.form.get('last_name')
        suffix_name = request.form.get('suffix_name')
        program = request.form.get('program')
        year_level = request.form.get('year_level')
        section = request.form.get('section')
        major = request.form.get('major')
        semester = request.form.get('semester')
        graduating_year = request.form.get('graduating_year')

        # Logic for major requirement based on program/year
        if year_level == "Graduate":
            major = None # Graduates don't use the major field in the same way
            if not graduating_year:
                flash("Graduating Academic Year is required for Graduates.", "error")
                return redirect(url_for('core.profile'))
        elif year_level in ("3rd Year", "4th Year"):
            graduating_year = None # Undergrads don't have this yet
            if program in ("BSIT", "BSCS"):
                if not major:
                    flash(f"Major is required for 3rd/4th year {program}.", "error")
                    return redirect(url_for('core.profile'))
            else:
                major = None 
        else:
            major = None
            graduating_year = None

        update_data = {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "suffix_name": suffix_name,
            "program": program,
            "year_level": year_level,
            "section": section,
            "major": major,
            "graduating_year": graduating_year,
            "semester": semester
        }

        # Handle File Uploads (Optional in this specific update route, but handled if present)
        picture_file = request.files.get('picture')
        signature_file = request.files.get('signature')
        
        # Get student ID for filename
        profile_res = supabase.table("profiles").select("student_id").eq("id", user_id).single().execute()
        student_id_num = profile_res.data.get('student_id')

        if picture_file and picture_file.filename:
            picture_bytes = picture_file.read()
            if len(picture_bytes) > Config.MAX_FILE_SIZE:
                 flash("Picture is too large (max 5MB).", "error")
                 return redirect(url_for('core.profile'))
            
            file_ext = os.path.splitext(picture_file.filename)[1]
            file_name = f"{student_id_num}_picture{file_ext}"
            
            supabase.storage.from_("pictures").upload(
                file_name, picture_bytes, {"content-type": picture_file.mimetype, "upsert": "true"}
            )
            update_data["picture_url"] = supabase.storage.from_("pictures").get_public_url(file_name)
            update_data["picture_status"] = "pending" 
            update_data["picture_disapproval_reason"] = None 

        if signature_file and signature_file.filename:
            signature_bytes = signature_file.read()
            if len(signature_bytes) > Config.MAX_FILE_SIZE:
                 flash("Signature is too large (max 5MB).", "error")
                 return redirect(url_for('core.profile'))
            
            if not signature_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                 flash("Signature must be a PNG file.", "error")
                 return redirect(url_for('core.profile'))

            signature_stream = io.BytesIO(signature_bytes)
            if not check_transparency(signature_stream):
                 flash("Signature must have a transparent background.", "error")
                 return redirect(url_for('core.profile'))

            file_ext = os.path.splitext(signature_file.filename)[1]
            file_name = f"{student_id_num}_signature{file_ext}"
            
            supabase.storage.from_("signatures").upload(
                file_name, signature_bytes, {"content-type": signature_file.mimetype, "upsert": "true"}
            )
            update_data["signature_url"] = supabase.storage.from_("signatures").get_public_url(file_name)
            update_data["signature_status"] = "pending" 
            update_data["signature_disapproval_reason"] = None 

        supabase.table("profiles").update(update_data).eq("id", user_id).execute()
        
        flash("Profile updated successfully.", "success")
        return redirect(url_for('core.profile'))

    except Exception as e:
        err_msg = str(e)
        flash(f"Error updating profile: {err_msg}", "error")
        return redirect(url_for('core.profile'))

# --- NEW: Delete Account Route ---
@core_bp.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    password = request.form.get('password_confirm')
    user_id = session.get('user_id')
    user_email = session.get('email')

    if not password:
        flash("Password is required to delete your account.", "error")
        return redirect(url_for('core.settings'))

    try:
        # 1. Verify Password
        auth = supabase.auth.sign_in_with_password({
            "email": user_email,
            "password": password
        })
        if not auth.user:
            flash("Incorrect password. Account deletion aborted.", "error")
            return redirect(url_for('core.settings'))

        # 2. Fetch Profile to get file paths
        profile_res = supabase.table("profiles").select("picture_url, signature_url, student_id").eq("id", user_id).single().execute()
        profile = profile_res.data

        if profile:
            # 3. Delete Files from Storage
            try:
                files_to_remove_pic = []
                files_to_remove_sig = []
                
                # Extract filename from URL or reconstruct it
                # Assuming standard naming: {student_id}_picture.ext
                # But safer to parse URL if available, or just use the naming convention logic if consistent
                # Here we try to parse the URL if it exists
                if profile.get('picture_url'):
                    pic_name = profile['picture_url'].split('/')[-1].split('?')[0]
                    files_to_remove_pic.append(pic_name)
                
                if profile.get('signature_url'):
                    sig_name = profile['signature_url'].split('/')[-1].split('?')[0]
                    files_to_remove_sig.append(sig_name)

                if files_to_remove_pic:
                    supabase.storage.from_("pictures").remove(files_to_remove_pic)
                if files_to_remove_sig:
                    supabase.storage.from_("signatures").remove(files_to_remove_sig)
            except Exception as storage_e:
                print(f"Storage cleanup error (non-fatal): {storage_e}")

            # 4. Delete Profile Row
            supabase.table("profiles").delete().eq("id", user_id).execute()

        # 5. Delete Auth User (Requires Admin Privilege)
        supabase_admin.auth.admin.delete_user(user_id)

        # 6. Cleanup Session
        session.clear()
        flash("Your account has been permanently deleted.", "success")
        return redirect(url_for('auth.login'))

    except Exception as e:
        if "Invalid login credentials" in str(e):
            flash("Incorrect password.", "error")
        else:
            flash(f"An error occurred during deletion: {str(e)}", "error")
        return redirect(url_for('core.settings'))