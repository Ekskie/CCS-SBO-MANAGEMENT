import os
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, session # Added session
from extensions import supabase, supabase_admin
from utils import admin_required, check_transparency
from datetime import datetime
from config import Config # <-- Import Config class

admin_bp = Blueprint('admin', __name__,
                     template_folder='../templates/admin')

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    try:
        # Get total student count
        profiles_res = supabase.table("profiles").select("id", count='exact').execute()
        student_count = profiles_res.count
        
        # Get unique program count
        programs_res = supabase.table("profiles").select("program").execute()
        program_count = len(set(p['program'] for p in programs_res.data if p.get('program')))
        
        # --- NEW: Fetch Pending Approvals ---
        pending_query = supabase.table("profiles").select("*", count='exact').or_("picture_status.eq.pending,signature_status.eq.pending")
        pending_res = pending_query.order("last_name", desc=False).execute()
        pending_students = pending_res.data
        pending_count = pending_res.count
        # --- END NEW ---
        
        return render_template(
            'dashboard.html', 
            student_count=student_count, 
            program_count=program_count,
            pending_count=pending_count,        # <-- Pass pending count
            pending_students=pending_students   # <-- Pass pending students list
        )
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template(
            'dashboard.html', 
            student_count=0, 
            program_count=0,
            pending_count=0,          # <-- Default values
            pending_students=[]       # <-- Default values
        )

# --- Keep all other routes (admin_students, admin_edit_student, etc.) exactly as they were ---
# (admin_students function)
@admin_bp.route('/students')
@admin_required
def admin_students():
    try:
        search_name = request.args.get('search_name', '')
        filter_program = request.args.get('filter_program', '')
        filter_section = request.args.get('filter_section', '')
        filter_year_level = request.args.get('filter_year_level', '') # <-- ADDED
        filter_major = request.args.get('filter_major', '')        # <-- ADDED

        # Base query
        query = supabase.table("profiles").select("*")

        # Apply filters
        if search_name:
            # This searches for the name in first_name, last_name, and middle_name
            # Also searches student_id and email
            query = query.or_(f"first_name.ilike.%{search_name}%,last_name.ilike.%{search_name}%,middle_name.ilike.%{search_name}%,student_id.ilike.%{search_name}%,email.ilike.%{search_name}%")
        if filter_program:
            query = query.eq('program', filter_program)
        if filter_section:
            query = query.eq('section', filter_section)
        if filter_year_level:                                         # <-- ADDED
            query = query.eq('year_level', filter_year_level)         # <-- ADDED
        if filter_major:                                              # <-- ADDED
            query = query.eq('major', filter_major)                   # <-- ADDED

        # Execute query
        response = query.order("last_name", desc=False).execute()
        students = response.data

        # Get filter options for dropdowns
        programs_res = supabase.table("profiles").select("program").execute()
        sections_res = supabase.table("profiles").select("section").execute()
        years_res = supabase.table("profiles").select("year_level").execute() # <-- ADDED
        majors_res = supabase.table("profiles").select("major").execute()      # <-- ADDED
        
        programs = sorted(list(set(p['program'] for p in programs_res.data if p.get('program'))))
        sections = sorted(list(set(s['section'] for s in sections_res.data if s.get('section'))))
        all_years = sorted(list(set(y['year_level'] for y in years_res.data if y.get('year_level'))), key=lambda x: (x or "Z")[0]) # <-- ADDED
        all_majors = sorted(list(set(m['major'] for m in majors_res.data if m.get('major'))))      # <-- ADDED

        return render_template(
            'students.html', 
            students=students,
            programs=programs,
            sections=sections,
            all_years=all_years,      # <-- ADDED
            all_majors=all_majors,    # <-- ADDED
            search_name=search_name,
            filter_program=filter_program,
            filter_section=filter_section,
            filter_year_level=filter_year_level, # <-- ADDED
            filter_major=filter_major            # <-- ADDED
        )
    except Exception as e:
        flash(f"Error fetching students: {str(e)}", "error")
        return render_template('students.html', students=[], programs=[], sections=[], all_years=[], all_majors=[])


# (admin_edit_student function)
@admin_bp.route('/edit_student/<student_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_student(student_id):
    if request.method == 'POST':
        # Logic to UPDATE the student
        try:
            # Fetch the existing student profile to get student_id (for file naming)
            user_res = supabase.table("profiles").select("student_id, disapproval_reason, picture_status, signature_status").eq("id", student_id).single().execute() # Added statuses
            if not user_res.data:
                flash("Student profile not found.", "error")
                return redirect(url_for('admin.admin_students'))
            
            student_profile = user_res.data # Store the fetched profile
            student_num = student_profile['student_id'] # The Student's ID number
            
            # Start with existing reasons and statuses
            current_disapproval_reason = student_profile.get('disapproval_reason')
            current_picture_status = student_profile.get('picture_status')
            current_signature_status = student_profile.get('signature_status')


            year_level = request.form.get('year_level')
            major = request.form.get('major')
            program = request.form.get('program') # Get program

            # --- Major Validation (from user update) ---
            if year_level in ("3rd Year", "4th Year"):
                if program in ("BSIT", "BSCS"): # Only require for BSIT/BSCS
                    if not major:
                        flash(f"Major is required for 3rd and 4th year {program} students.")
                        # Fetch again for render_template on error
                        student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                        return render_template('edit_student.html', student=student_data)
                else: # For BSIS
                    major = None # Ensure major is None if program is BSIS
            else: # For 1st/2nd year
                 major = None # Ensure major is None

            update_data = {
                "first_name": request.form.get('first_name'),
                "middle_name": request.form.get('middle_name'),
                "last_name": request.form.get('last_name'),
                "program": program, # Use program variable
                "semester": request.form.get('semester'),
                "year_level": year_level,
                "section": request.form.get('section'),
                "major": major,
                "account_type": request.form.get('account_type'), # Admin can change role
                "disapproval_reason": current_disapproval_reason, # Start with existing reason
                "picture_status": current_picture_status,         # Start with existing status
                "signature_status": current_signature_status      # Start with existing status
            }

            # Handle file uploads (similar to update_profile)
            picture_file = request.files.get('picture')
            signature_file = request.files.get('signature')

            if picture_file and picture_file.filename:
                # Check size on update
                picture_bytes = picture_file.read()
                if len(picture_bytes) > Config.MAX_FILE_SIZE: # <-- Use Config.MAX_FILE_SIZE
                    flash(f"Picture file size must be less than {Config.MAX_FILE_SIZE // 1024 // 1024}MB.")
                    # Fetch again for render_template
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('edit_student.html', student=student_data)
                    
                file_ext = os.path.splitext(picture_file.filename)[1]
                file_name = f"{student_num}_picture{file_ext}"
                supabase.storage.from_("pictures").upload(
                    file_name, picture_bytes, {"content-type": picture_file.mimetype, "upsert": "true"}
                )
                update_data["picture_url"] = supabase.storage.from_("pictures").get_public_url(file_name)
                
                # --- Admin uploads are auto-approved ---
                update_data["picture_status"] = "approved"
                # Clear specific reason if it existed (might need more nuanced logic if reasons combine)
                # For simplicity, admin upload clears all reasons for now
                update_data["disapproval_reason"] = None 

            if signature_file and signature_file.filename:
                # Check size on update
                signature_bytes = signature_file.read()
                if len(signature_bytes) > Config.MAX_FILE_SIZE: # <-- Use Config.MAX_FILE_SIZE
                    flash(f"Signature file size must be less than {Config.MAX_FILE_SIZE // 1024 // 1024}MB.")
                    # Fetch again
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('edit_student.html', student=student_data)

                # Check for PNG and transparency on update
                if not signature_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                    flash("Signature must be a valid PNG file.")
                    # Fetch again
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('edit_student.html', student=student_data)
                signature_stream = io.BytesIO(signature_bytes)
                if not check_transparency(signature_stream):
                    flash("Signature PNG must have a transparent background.")
                    # Fetch again
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('edit_student.html', student=student_data)
                    
                file_ext = os.path.splitext(signature_file.filename)[1]
                file_name = f"{student_num}_signature{file_ext}"
                supabase.storage.from_("signatures").upload(
                    file_name, signature_bytes, {"content-type": signature_file.mimetype, "upsert": "true"}
                )
                update_data["signature_url"] = supabase.storage.from_("signatures").get_public_url(file_name)
                
                # --- Admin uploads are auto-approved ---
                update_data["signature_status"] = "approved"
                 # Clear specific reason if it existed
                update_data["disapproval_reason"] = None # Clear reason on admin upload

            supabase.table("profiles").update(update_data).eq("id", student_id).execute()
            flash('Student profile updated successfully.')
            return redirect(url_for('admin.admin_students'))

        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "error")
            # Don't redirect here, show the form again with the error
            # Fetch again for render_template on exception
            student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
            return render_template('edit_student.html', student=student_data)


    # GET request: Show the edit form
    try:
        response = supabase.table("profiles").select("*").eq("id", student_id).single().execute()
        if not response.data:
            flash("Student profile not found.", "error")
            return redirect(url_for('admin.admin_students'))
        
        return render_template('edit_student.html', student=response.data)
    except Exception as e:
        flash(f"Error fetching profile: {str(e)}", "error")
        return redirect(url_for('admin.admin_students'))

# (admin_delete_student function)
@admin_bp.route('/delete_student/<student_id>', methods=['POST'])
@admin_required
def admin_delete_student(student_id):
    try:
        # 1. Get profile data before deleting (for file names and auth ID)
        profile_res = supabase.table("profiles").select("id, student_id, picture_url, signature_url").eq("id", student_id).single().execute()
        
        if not profile_res.data:
            flash("Student not found.", "error")
            return redirect(url_for('admin.admin_students'))
        
        profile = profile_res.data
        auth_user_id = profile['id'] # This is the auth.users.id

        # 2. Delete files from Storage
        try:
            files_to_remove_pic = []
            files_to_remove_sig = []
            if profile.get('picture_url'):
                # Extract file name from URL more robustly
                pic_file_name = profile['picture_url'].split('/')[-1].split('?')[0] 
                if pic_file_name:
                    files_to_remove_pic.append(pic_file_name)
            if profile.get('signature_url'):
                 # Extract file name from URL more robustly
                sig_file_name = profile['signature_url'].split('/')[-1].split('?')[0]
                if sig_file_name:
                    files_to_remove_sig.append(sig_file_name)
            
            if files_to_remove_pic:
                supabase.storage.from_("pictures").remove(files_to_remove_pic)
            if files_to_remove_sig:
                supabase.storage.from_("signatures").remove(files_to_remove_sig)
                
        except Exception as e:
            # Log this error instead of flashing to user?
            print(f"Warning: Failed to delete storage files for {student_id}: {str(e)}")
            flash(f"Profile deleted, but failed to delete storage files: {str(e)}", "warning") # Keep flash for now

        # 3. Delete from 'profiles' table (public schema)
        # Done first to avoid orphaned auth users if profile delete fails
        supabase.table("profiles").delete().eq("id", auth_user_id).execute()
        
        # 4. Delete from 'auth.users' (requires SERVICE_ROLE_KEY)
        # Use try-except specifically for the admin auth action
        try:
             supabase_admin.auth.admin.delete_user(auth_user_id)
        except Exception as auth_e:
             # If auth deletion fails AFTER profile deletion, it's harder to recover automatically
             print(f"CRITICAL ERROR: Profile {auth_user_id} deleted, but failed to delete auth user: {str(auth_e)}")
             flash(f"Profile deleted, but FAILED to delete authentication account: {str(auth_e)}. Manual cleanup required in Supabase Auth.", "error")
             # Redirect even on failure here, as profile is gone
             return redirect(url_for('admin.admin_students')) 
             
        flash("Student deleted successfully (Auth, Profile, and Files).")
    except Exception as e:
        flash(f"Error during student deletion process: {str(e)}.", "error")
        
    return redirect(url_for('admin.admin_students'))

# (admin_archive function)
@admin_bp.route('/archive')
@admin_required
def admin_archive():
    try:
        # Get filters from URL
        filter_ay = request.args.get('filter_ay', '')
        filter_semester = request.args.get('filter_semester', '')
        filter_program = request.args.get('filter_program', '')
        filter_major = request.args.get('filter_major', '')

        # Base query
        query = supabase.table("archived_groups").select("*")

        # Apply filters
        if filter_ay:
            query = query.eq('academic_year', filter_ay)
        if filter_semester:
            query = query.eq('semester', filter_semester)
        if filter_program:
            # Assumes program is the start of the group_name, e.g., "BSIT%"
            query = query.ilike('group_name', f'{filter_program}%')
        if filter_major:
            # Assumes major is contained anywhere in the name, e.g., "%NETAD%"
             # Handle 'None' explicitly if it's a possible value from filter dropdown
            if filter_major == 'None':
                 # This logic depends on how group_name is constructed. 
                 # If 'None' major means major part is absent, this might need adjustment.
                 # Assuming for now 'None' won't be part of group_name if major is NULL.
                 # A safer filter might be complex, or better stored in separate columns.
                 pass # Or add specific logic if group_name can indicate 'None' major
            else:
                query = query.ilike('group_name', f'%{filter_major}%') 
        
        # Execute query
        archives_res = query.order("created_at", desc=True).execute()
        archives = archives_res.data
        
        # Format the created_at timestamp for display
        for archive in archives:
            try:
                # Parse the full ISO timestamp including timezone offset
                utc_time = datetime.fromisoformat(archive['created_at'].replace('Z', '+00:00'))
                # Format without timezone info for cleaner display
                archive['created_at_display'] = utc_time.strftime('%Y-%m-%d %I:%M %p') 
                # Keep original for potential sorting later if needed
                # archive['created_at_iso'] = archive['created_at'] 
            except Exception as parse_e:
                 print(f"Error parsing date {archive.get('created_at')}: {parse_e}")
                 archive['created_at_display'] = str(archive.get('created_at', '')) # Fallback to string


        # Get all unique options for dropdowns
        all_options_res = supabase.table("archived_groups").select("academic_year, semester, group_name").execute()
        all_data = all_options_res.data
        
        all_academic_years = sorted(list(set(d['academic_year'] for d in all_data if d.get('academic_year'))))
        all_semesters = sorted(list(set(d['semester'] for d in all_data if d.get('semester'))))
        
        all_programs = set()
        all_majors = set(['None']) # Start with 'None' as an option
        for d in all_data:
            if d.get('group_name'):
                parts = d['group_name'].split(' - ')
                if len(parts) > 0:
                    all_programs.add(parts[0])
                if len(parts) > 2: # Has a major part in the name
                    all_majors.add(parts[2])
                    
        all_programs = sorted(list(all_programs))
        all_majors = sorted(list(all_majors))

        return render_template(
            'archive.html', 
            archives=archives,
            all_academic_years=all_academic_years,
            all_semesters=all_semesters,
            all_programs=all_programs,
            all_majors=all_majors,
            current_ay=filter_ay,
            current_semester=filter_semester,
            current_program=filter_program,
            current_major=filter_major
        )
    except Exception as e:
        flash(f"Error loading archive: {str(e)}", "error")
        return render_template('archive.html', archives=[], all_academic_years=[], all_semesters=[], all_programs=[], all_majors=[], current_ay='', current_semester='', current_program='', current_major='')

# (admin_printing function)
@admin_bp.route('/printing')
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
        all_years = sorted(list(set(p['year_level'] for p in all_profiles_data if p.get('year_level'))), key=lambda x: (x or "Z")[0]) # Sort by '1st', '2nd'
        all_sections = sorted(list(set(p['section'] for p in all_profiles_data if p.get('section'))))
        all_semesters = sorted(list(set(p['semester'] for p in all_profiles_data if p.get('semester'))))

        # Build unique groups from the *filtered* profiles
        unique_groups = set()
        for profile in profiles:
            # Ensure essential fields are present
            if not all([profile.get('program'), profile.get('year_level'), profile.get('section'), profile.get('semester')]):
                continue 
            
            major_val = profile.get('major') or 'None' # Use 'None' string if major is None or empty
            semester_val = profile.get('semester')
            
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
            'printing.html', 
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
        # Redirecting might hide the error context, consider rendering template with error
        return render_template('printing.html', groups=[], error=str(e), all_programs=[], all_years=[], all_sections=[], all_semesters=[]) # Pass defaults

# (admin_print_preview function)
@admin_bp.route('/print_preview')
@admin_required
def admin_print_preview():
    program = request.args.get('program')
    year_level = request.args.get('year_level')
    section = request.args.get('section')
    major = request.args.get('major') # Will be 'None' string if no major
    semester = request.args.get('semester') 

    # Check required fields
    if not all([program, year_level, section, semester]): # Major can be 'None', semester is required
        flash("Error: Missing required group information (Program, Year, Section, Semester).", "error")
        return redirect(url_for('admin.admin_printing'))

    try:
        query = supabase.table("profiles").select("*")
        query = query.eq("program", program)
        query = query.eq("year_level", year_level)
        query = query.eq("section", section)
        query = query.eq("semester", semester) 
        
        # Handle major filtering carefully
        if major == 'None' or major is None:
            query = query.is_("major", None) # Check for actual NULL in database
        else:
            query = query.eq("major", major)

        response = query.execute()
        group_profiles = response.data

        # It's okay if a group has no members, just show an empty preview
        # if not group_profiles:
        #     flash(f"No profiles found for this group.", "info") # Info instead of error
        #     # Maybe redirect back or render preview with message?
        #     # return redirect(url_for('admin.admin_printing'))

        members = []
        for p in group_profiles:
            # Ensure required name parts exist, provide defaults if missing
            last_name = p.get('last_name', '')
            first_name = p.get('first_name', '')
            middle_name = p.get('middle_name', '')
            
            full_name = f"{last_name}, {first_name} {middle_name}".strip()
            if full_name == ',': full_name = "Name Missing" # Handle completely empty name
                
            # Construct the course string, handling optional major
            course_parts = [p.get('program', 'N/A'), f"{p.get('year_level', 'N/A')}{p.get('section', 'N/A')}"]
            if p.get('major'):
                course_parts.append(p.get('major'))
            course = " - ".join(filter(None, course_parts)).strip() 
            
            member = {
                'full_name': full_name,
                'student_id': p.get('student_id', 'N/A'),
                'course': course,
                'picture_url': p.get('picture_url'),
                'signature_url': p.get('signature_url')
            }
            members.append(member)
            
        # Sort the list of dictionaries by the 'full_name' key
        sorted_members = sorted(members, key=lambda m: m.get('full_name', '').lower()) # Use lower for case-insensitive sort

        # --- Automation Logic ---
        today = datetime.now()
        semester_display = f"{semester} Sem." 
        current_year_num = today.year
        # Academic year calculation based on month
        if today.month >= 8: # Aug-Dec part of AY YYYY-(YYYY+1)
            academic_year = f"AY {current_year_num}-{current_year_num + 1}"
        else: # Jan-Jul part of AY (YYYY-1)-YYYY
            academic_year = f"AY {current_year_num - 1}-{current_year_num}"
        generation_date = today.strftime("%B %d, %Y") 

        return render_template(
            './print_template.html', # Path relative to blueprint's template_folder
            members=sorted_members, 
            semester_display=semester_display,
            academic_year=academic_year,
            generation_date=generation_date
        )
    
    except Exception as e:
        print(f"Error in admin_print_preview: {str(e)}") # Log the full error
        flash(f"Error generating print preview: {str(e)}", "error")
        return redirect(url_for('admin.admin_printing'))

# (admin_archive_group function)
@admin_bp.route('/archive_group', methods=['POST'])
@admin_required
def admin_archive_group():
    try:
        # Get data from the form
        program = request.form.get('program')
        year_level = request.form.get('year_level')
        section = request.form.get('section')
        major = request.form.get('major') # Will be 'None' if major was None/empty
        semester = request.form.get('semester')
        academic_year_form = request.form.get('academic_year') # User-supplied AY

        if not academic_year_form:
            flash("Academic Year is required to create an archive.", "error")
            return redirect(url_for('admin.admin_printing'))
            
        # Validate required fields for fetching live data
        if not all([program, year_level, section, semester]):
             flash("Missing required group information to fetch live data for archive.", "error")
             return redirect(url_for('admin.admin_printing'))

        # Fetch the live data for this group
        query = supabase.table("profiles").select("*")
        query = query.eq("program", program)
        query = query.eq("year_level", year_level)
        query = query.eq("section", section)
        query = query.eq("semester", semester)
        
        if major == 'None' or major is None:
            query = query.is_("major", None)
        else:
            query = query.eq("major", major)
        
        group_profiles = query.execute().data

        if not group_profiles:
            flash("Cannot archive an empty group. No students found matching the criteria.", "warning") # Warning instead of error
            return redirect(url_for('admin.admin_printing'))

        # --- Build the JSONB data blob ---
        members = []
        for p in group_profiles:
            last_name = p.get('last_name', '')
            first_name = p.get('first_name', '')
            middle_name = p.get('middle_name', '')
            full_name = f"{last_name}, {first_name} {middle_name}".strip()
            if full_name == ',': full_name = "Name Missing"
                
            course_parts = [p.get('program', 'N/A'), f"{p.get('year_level', 'N/A')}{p.get('section', 'N/A')}"]
            if p.get('major'):
                course_parts.append(p.get('major'))
            course = " - ".join(filter(None, course_parts)).strip()
            
            member = {
                'full_name': full_name,
                'student_id': p.get('student_id', 'N/A'),
                'course': course,
                'picture_url': p.get('picture_url'),
                'signature_url': p.get('signature_url')
            }
            members.append(member)
        
        sorted_members = sorted(members, key=lambda m: m.get('full_name', '').lower())
        # --- End of JSONB data blob ---

        today = datetime.now()
        generation_date = today.strftime("%B %d, %Y")
        
        # Build the group name for the archive record
        group_name_parts = [program, f"{year_level}{section}"]
        if major != 'None' and major: # Add major only if it's not 'None' or empty
            group_name_parts.append(major)
        group_name = " - ".join(group_name_parts)

        # Data to insert into the archived_groups table
        insert_data = {
            "academic_year": academic_year_form, # Use the user-provided AY
            "semester": semester,
            "group_name": group_name,
            "student_data": sorted_members, # Store the JSON list
            "generation_date": generation_date
            # created_at is handled by Supabase default
        }
        
        supabase_admin.table("archived_groups").insert(insert_data).execute() # Use admin client
        
        flash(f"Successfully archived group '{group_name}' for {academic_year_form}.", "success")

    except Exception as e:
        print(f"Error archiving group: {str(e)}") # Log the error
        flash(f"Error creating archive: {str(e)}", "error")
        
    return redirect(url_for('admin.admin_printing'))


# (admin_archive_preview function)
@admin_bp.route('/archive_preview/<archive_id>')
@admin_required
def admin_archive_preview(archive_id):
    try:
        # Fetch the specific archive record
        archive_res = supabase.table("archived_groups").select("*").eq("id", archive_id).single().execute()
        
        if not archive_res.data:
            flash("Archive not found.", "error")
            return redirect(url_for('admin.admin_archive'))
            
        archive = archive_res.data
        
        # Extract the data needed by the template
        sorted_members = archive.get('student_data', [])
        semester_display = f"{archive.get('semester', '?')} Sem." # Add fallback
        academic_year = archive.get('academic_year', 'N/A')
        generation_date = archive.get('generation_date', 'N/A')

        return render_template(
            './print_template.html', # Path relative to blueprint's template_folder
            members=sorted_members,
            semester_display=semester_display,
            academic_year=academic_year,
            generation_date=generation_date
        )
    except Exception as e:
        print(f"Error loading archive preview {archive_id}: {str(e)}") # Log error
        flash(f"Error loading archive preview: {str(e)}", "error")
        return redirect(url_for('admin.admin_archive'))

# (admin_delete_archive function)
@admin_bp.route('/delete_archive/<archive_id>', methods=['POST'])
@admin_required
def admin_delete_archive(archive_id):
    try:
        supabase.table("archived_groups").delete().eq("id", archive_id).execute()
        flash("Archive deleted successfully.", "success")
    except Exception as e:
        print(f"Error deleting archive {archive_id}: {str(e)}") # Log error
        flash(f"Error deleting archive: {str(e)}", "error")
    return redirect(url_for('admin.admin_archive'))


# (admin_review_student function)
@admin_bp.route('/review_student/<student_id>', methods=['GET', 'POST'])
@admin_required
def admin_review_student(student_id):
    # Fetch the student's profile
    try:
        student_res = supabase.table("profiles").select("*").eq("id", student_id).single().execute()
        if not student_res.data:
            flash("Student not found.", "error")
            return redirect(url_for('admin.admin_students'))
        
        student = student_res.data
            
    except Exception as e:
        flash(f"Error fetching student: {str(e)}", "error")
        return redirect(url_for('admin.admin_students'))
        

    if request.method == 'POST':
        try:
            action = request.form.get('action')
            disapproval_reason = request.form.get('disapproval_reason', '').strip()
            
            update_data = {}
            new_reason_part = "" # For constructing the reason message

            # Determine status update and prepare reason part
            if action == 'approve_picture':
                update_data['picture_status'] = 'approved'
            elif action == 'approve_signature':
                update_data['signature_status'] = 'approved'
            elif action in ('disapprove_picture', 'disapprove_signature'):
                if not disapproval_reason:
                    flash("A reason is required for disapproval.", "error")
                    return render_template('review_student.html', student=student)
                
                # Prepare the reason part to be potentially added
                new_reason_part = f"[Reason: {disapproval_reason}]" 

                if action == 'disapprove_picture':
                    update_data['picture_status'] = 'disapproved'
                elif action == 'disapprove_signature':
                    update_data['signature_status'] = 'disapproved'
            else:
                flash("Invalid action.", "error")
                return render_template('review_student.html', student=student)

            # Handle disapproval reason update
            if new_reason_part: # If we are disapproving
                 # Admin reason overwrites previous reasons completely
                update_data['disapproval_reason'] = new_reason_part 
            elif 'picture_status' in update_data or 'signature_status' in update_data:
                 # If we approved something, clear the reason field
                 update_data['disapproval_reason'] = None


            # Apply the update
            if update_data: # Only update if there are changes
                 supabase.table("profiles").update(update_data).eq("id", student_id).execute()
                 flash("Student status updated.", "success")
            else:
                 flash("No changes detected.", "info") # Should not happen with current logic

            # Redirect back to the review page to see updated status
            return redirect(url_for('admin.admin_review_student', student_id=student_id)) 

        except Exception as e:
            flash(f"Error updating student status: {str(e)}", "error")
            # Render template again to show error with current data
            return render_template('review_student.html', student=student)


    # GET request
    return render_template('review_student.html', student=student)