import os
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash
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
        profiles_res = supabase.table("profiles").select("id", count='exact').execute()
        student_count = profiles_res.count
        
        programs_res = supabase.table("profiles").select("program").execute()
        program_count = len(set(p['program'] for p in programs_res.data if p.get('program')))
        
        return render_template('dashboard.html', student_count=student_count, program_count=program_count)
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template('dashboard.html', student_count=0, program_count=0)

@admin_bp.route('/students')
@admin_required
def admin_students():
    try:
        search_name = request.args.get('search_name', '')
        filter_program = request.args.get('filter_program', '')
        filter_section = request.args.get('filter_section', '')
        filter_year_level = request.args.get('filter_year_level', '') # <-- ADDED
        filter_major = request.args.get('filter_major', '')          # <-- ADDED

        # Base query
        query = supabase.table("profiles").select("*")

        # Apply filters
        if search_name:
            # This searches for the name in first_name, last_name, and middle_name
            query = query.or_(f"first_name.ilike.%{search_name}%,last_name.ilike.%{search_name}%,middle_name.ilike.%{search_name}%")
        if filter_program:
            query = query.eq('program', filter_program)
        if filter_section:
            query = query.eq('section', filter_section)
        if filter_year_level:                                        # <-- ADDED
            query = query.eq('year_level', filter_year_level)        # <-- ADDED
        if filter_major:                                             # <-- ADDED
            query = query.eq('major', filter_major)                  # <-- ADDED

        # Execute query
        response = query.order("last_name", desc=False).execute()
        students = response.data

        # Get filter options for dropdowns
        programs_res = supabase.table("profiles").select("program").execute()
        sections_res = supabase.table("profiles").select("section").execute()
        years_res = supabase.table("profiles").select("year_level").execute() # <-- ADDED
        majors_res = supabase.table("profiles").select("major").execute()     # <-- ADDED
        
        programs = sorted(list(set(p['program'] for p in programs_res.data if p.get('program'))))
        sections = sorted(list(set(s['section'] for s in sections_res.data if s.get('section'))))
        all_years = sorted(list(set(y['year_level'] for y in years_res.data if y.get('year_level'))), key=lambda x: (x or "Z")[0]) # <-- ADDED
        all_majors = sorted(list(set(m['major'] for m in majors_res.data if m.get('major'))))     # <-- ADDED

        return render_template(
            'students.html', 
            students=students,
            programs=programs,
            sections=sections,
            all_years=all_years,     # <-- ADDED
            all_majors=all_majors,   # <-- ADDED
            search_name=search_name,
            filter_program=filter_program,
            filter_section=filter_section,
            filter_year_level=filter_year_level, # <-- ADDED
            filter_major=filter_major            # <-- ADDED
        )
    except Exception as e:
        flash(f"Error fetching students: {str(e)}", "error")
        return render_template('students.html', students=[], programs=[], sections=[], all_years=[], all_majors=[])

@admin_bp.route('/edit_student/<student_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_student(student_id):
    if request.method == 'POST':
        # Logic to UPDATE the student
        try:
            # Fetch the existing student profile to get student_id (for file naming)
            user_res = supabase.table("profiles").select("student_id, disapproval_reason").eq("id", student_id).single().execute()
            if not user_res.data:
                flash("Student profile not found.", "error")
                return redirect(url_for('admin.admin_students'))
            
            student_num = user_res.data['student_id'] # The Student's ID number
            current_disapproval_reason = user_res.data.get('disapproval_reason')

            year_level = request.form.get('year_level')
            major = request.form.get('major')
            program = request.form.get('program') # Get program

            # --- Major Validation (from user update) ---
            if year_level in ("3rd Year", "4th Year"):
                if program in ("BSIT", "BSCS"): # Only require for BSIT/BSCS
                    if not major:
                        flash(f"Major is required for 3rd and 4th year {program} students.")
                        student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                        return render_template('edit_student.html', student=student_data)
                else:
                    major = None # Set major to None (NULL) for BSIS
            else:
                major = None # Set major to None (NULL) for 1st/2nd year

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
                "disapproval_reason": current_disapproval_reason # Start with existing reason
            }

            # Handle file uploads (similar to update_profile)
            picture_file = request.files.get('picture')
            signature_file = request.files.get('signature')

            if picture_file and picture_file.filename:
                # Check size on update
                picture_bytes = picture_file.read()
                if len(picture_bytes) > Config.MAX_FILE_SIZE: # <-- Use Config.MAX_FILE_SIZE
                    flash(f"Picture file size must be less than {Config.MAX_FILE_SIZE // 1024 // 1024}MB.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('edit_student.html', student=student_data)
                    
                file_ext = os.path.splitext(picture_file.filename)[1]
                file_name = f"{student_num}_picture{file_ext}"
                supabase.storage.from_("pictures").upload(
                    file_name, picture_bytes, {"content-type": picture_file.mimetype, "upsert": "true"}
                )
                update_data["picture_url"] = supabase.storage.from_("pictures").get_public_url(file_name)
                
                # --- FIXED: Reset status on new upload ---
                update_data["picture_status"] = "pending"
                update_data["disapproval_reason"] = None # Clear reason on admin upload

            if signature_file and signature_file.filename:
                # Check size on update
                signature_bytes = signature_file.read()
                if len(signature_bytes) > Config.MAX_FILE_SIZE: # <-- Use Config.MAX_FILE_SIZE
                    flash(f"Signature file size must be less than {Config.MAX_FILE_SIZE // 1024 // 1024}MB.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('edit_student.html', student=student_data)

                # Check for PNG and transparency on update
                if not signature_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                    flash("Signature must be a valid PNG file.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('edit_student.html', student=student_data)
                signature_stream = io.BytesIO(signature_bytes)
                if not check_transparency(signature_stream):
                    flash("Signature PNG must have a transparent background.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('edit_student.html', student=student_data)
                    
                file_ext = os.path.splitext(signature_file.filename)[1]
                file_name = f"{student_num}_signature{file_ext}"
                supabase.storage.from_("signatures").upload(
                    file_name, signature_bytes, {"content-type": signature_file.mimetype, "upsert": "true"}
                )
                update_data["signature_url"] = supabase.storage.from_("signatures").get_public_url(file_name)
                
                # --- FIXED: Reset status on new upload ---
                update_data["signature_status"] = "pending"
                update_data["disapproval_reason"] = None # Clear reason on admin upload

            supabase.table("profiles").update(update_data).eq("id", student_id).execute()
            flash('Student profile updated successfully.')
            return redirect(url_for('admin.admin_students'))

        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "error")
            return redirect(url_for('admin.admin_edit_student', student_id=student_id))

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
            if profile.get('picture_url'):
                # Extract file name from URL
                pic_file_name = profile['picture_url'].split('/')[-1].split('?')[0]
                if pic_file_name:
                    supabase.storage.from_("pictures").remove([pic_file_name])
            if profile.get('signature_url'):
                # Extract file name from URL
                sig_file_name = profile['signature_url'].split('/')[-1].split('?')[0]
                if sig_file_name:
                    supabase.storage.from_("signatures").remove([sig_file_name])
        except Exception as e:
            flash(f"Profile deleted, but failed to delete storage files: {str(e)}", "warning")

        # 3. Delete from 'profiles' table (public schema)
        # This is done first so that if auth deletion fails, we don't have an orphaned profile
        supabase.table("profiles").delete().eq("id", auth_user_id).execute()
        
        # 4. Delete from 'auth.users' (requires SERVICE_ROLE_KEY)
        supabase_admin.auth.admin.delete_user(auth_user_id)
        
        flash("Student deleted successfully (Auth, Profile, and Files).")
    except Exception as e:
        flash(f"Error deleting student: {str(e)}. You may need to manually delete the user from the Supabase Auth panel.", "error")
        
    return redirect(url_for('admin.admin_students'))

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
            query = query.ilike('group_name', f'%{filter_major}%')
        
        # Execute query
        archives_res = query.order("created_at", desc=True).execute()
        archives = archives_res.data
        
        # Format the created_at timestamp for display
        for archive in archives:
            try:
                # Parse the full ISO timestamp
                utc_time = datetime.fromisoformat(archive['created_at'].replace('Z', '+00:00'))
                # Format it
                archive['created_at'] = utc_time.strftime('%Y-%m-%d %I:%M %p')
            except Exception:
                archive['created_at'] = str(archive.get('created_at', '')) # Fallback

        # Get all unique options for dropdowns
        all_options_res = supabase.table("archived_groups").select("academic_year, semester, group_name").execute()
        all_data = all_options_res.data
        
        all_academic_years = sorted(list(set(d['academic_year'] for d in all_data if d.get('academic_year'))))
        all_semesters = sorted(list(set(d['semester'] for d in all_data if d.get('semester'))))
        
        all_programs = set()
        all_majors = set()
        for d in all_data:
            if d.get('group_name'):
                parts = d['group_name'].split(' - ')
                if len(parts) > 0:
                    all_programs.add(parts[0])
                if len(parts) > 2: # Has a major
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
            if not all([profile.get('program'), profile.get('year_level'), profile.get('section'), profile.get('semester')]):
                continue 
            
            major_val = profile.get('major') or 'None' 
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
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/print_preview')
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
        return redirect(url_for('admin.admin_printing'))

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
            return redirect(url_for('admin.admin_printing'))

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
        sorted_members = sorted(members, key=lambda m: m.get('full_name', ''))

        # --- Automation Logic ---
        # 1. Format Semester
        semester_display = f"{semester} Sem." # e.g., "1st Sem."
        
        # 2. Calculate Academic Year (e.g., AY 2025-2026)
        today = datetime.now()
        current_year = today.year
        if today.month >= 8: # August to December
            academic_year = f"AY {current_year}-{current_year + 1}"
        else: # January to July
            academic_year = f"AY {current_year - 1}-{current_year}"
            
        # 3. Get Formatted Current Date
        generation_date = today.strftime("%B %d, %Y") # e.g., "October 24, 2025"

        return render_template(
            './print_template.html', # Use shared template
            members=sorted_members, # Pass the new sorted list
            semester_display=semester_display,
            academic_year=academic_year,
            generation_date=generation_date
        )
    
    except Exception as e:
        flash(f"Error generating print preview: {str(e)}", "error")
        return redirect(url_for('admin.admin_printing'))

@admin_bp.route('/archive_group', methods=['POST'])
@admin_required
def admin_archive_group():
    try:
        # Get data from the form
        program = request.form.get('program')
        year_level = request.form.get('year_level')
        section = request.form.get('section')
        major = request.form.get('major')
        semester = request.form.get('semester')
        academic_year_form = request.form.get('academic_year') # This is the user-supplied AY

        if not academic_year_form:
            flash("Academic Year is required to create an archive.", "error")
            return redirect(url_for('admin.admin_printing'))

        # Fetch the live data for this group
        query = supabase.table("profiles").select("*")
        query = query.eq("program", program)
        query = query.eq("year_level", year_level)
        query = query.eq("section", section)
        query = query.eq("semester", semester)
        
        if major == 'None':
            query = query.is_("major", "null")
        else:
            query = query.eq("major", major)
        
        group_profiles = query.execute().data

        if not group_profiles:
            flash("Cannot archive an empty group.", "error")
            return redirect(url_for('admin.admin_printing'))

        # --- Build the JSONB data blob ---
        members = []
        for p in group_profiles:
            full_name = f"{p.get('last_name', '')}, {p.get('first_name', '')} {p.get('middle_name', '')}".strip()
            course_parts = [p.get('program', ''), f"{p.get('year_level', '')}{p.get('section', '')}"]
            if p.get('major'):
                course_parts.append(p.get('major'))
            course = " - ".join(filter(None, course_parts)).strip()
            
            member = {
                'full_name': full_name,
                'student_id': p.get('student_id'),
                'course': course,
                'picture_url': p.get('picture_url'),
                'signature_url': p.get('signature_url')
            }
            members.append(member)
        
        sorted_members = sorted(members, key=lambda m: m.get('full_name', ''))
        # --- End of JSONB data blob ---

        today = datetime.now()
        generation_date = today.strftime("%B %d, %Y")
        semester_display = f"{semester} Sem."
        
        # Build the group name for the archive
        group_name_parts = [program, f"{year_level}{section}"]
        if major != 'None':
            group_name_parts.append(major)
        group_name = " - ".join(group_name_parts)

        # Data to insert into the new table
        insert_data = {
            "academic_year": academic_year_form, # Use the user-provided AY
            "semester": semester,
            "group_name": group_name,
            "student_data": sorted_members, # Store the JSON list
            "generation_date": generation_date
        }
        
        supabase.table("archived_groups").insert(insert_data).execute()
        
        flash(f"Successfully archived group '{group_name}' for {academic_year_form}.", "success")

    except Exception as e:
        flash(f"Error creating archive: {str(e)}", "error")
        
    return redirect(url_for('admin.admin_printing'))


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
        
        # Extract the data
        sorted_members = archive.get('student_data', [])
        semester_display = f"{archive.get('semester')} Sem."
        academic_year = archive.get('academic_year')
        generation_date = archive.get('generation_date')

        return render_template(
            './print_template.html', # Use shared template
            members=sorted_members,
            semester_display=semester_display,
            academic_year=academic_year,
            generation_date=generation_date
        )
    except Exception as e:
        flash(f"Error loading archive preview: {str(e)}", "error")
        return redirect(url_for('admin.admin_archive'))

@admin_bp.route('/delete_archive/<archive_id>', methods=['POST'])
@admin_required
def admin_delete_archive(archive_id):
    try:
        supabase.table("archived_groups").delete().eq("id", archive_id).execute()
        flash("Archive deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting archive: {str(e)}", "error")
    return redirect(url_for('admin.admin_archive'))


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
            
            if action == 'approve_picture':
                update_data['picture_status'] = 'approved'
            elif action == 'approve_signature':
                update_data['signature_status'] = 'approved'
            
            elif action in ('disapprove_picture', 'disapprove_signature'):
                if not disapproval_reason:
                    flash("A reason is required for disapproval.", "error")
                    return render_template('review_student.html', student=student)
                
                # Combine new reason with existing (if any)
                existing_reason = student.get('disapproval_reason') or ""
                # Simple way to avoid duplicate reasons
                if disapproval_reason not in existing_reason:
                    new_reason = f"{existing_reason} [Reason: {disapproval_reason}]".strip()
                else:
                    new_reason = existing_reason
                
                update_data['disapproval_reason'] = new_reason

                if action == 'disapprove_picture':
                    update_data['picture_status'] = 'disapproved'
                elif action == 'disapprove_signature':
                    update_data['signature_status'] = 'disapproved'
            
            else:
                flash("Invalid action.", "error")
                return render_template('review_student.html', student=student)
            
            # Apply the update
            supabase.table("profiles").update(update_data).eq("id", student_id).execute()
            flash("Student profile updated.", "success")
            return redirect(url_for('admin.admin_students'))

        except Exception as e:
            flash(f"Error updating student status: {str(e)}", "error")

    # GET request
    return render_template('review_student.html', student=student)

