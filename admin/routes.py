import os
import io
import mimetypes
from collections import Counter
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import supabase, supabase_admin
from utils import admin_required, check_transparency
from datetime import datetime
from config import Config

admin_bp = Blueprint('admin', __name__,
                     template_folder='../templates/admin')

# ... (Helper functions log_activity, get_verified_user_ids remain same) ...
def get_verified_user_ids():
    verified_ids = set()
    try:
        page = 1
        while True:
            result = supabase_admin.auth.admin.list_users(page=page, per_page=1000)
            users = result.users
            if not users:
                break
            for user in users:
                if user.email_confirmed_at:
                    verified_ids.add(user.id)
            if len(users) < 1000:
                break
            page += 1
    except Exception as e:
        print(f"Error fetching verified users: {e}")
    return verified_ids

def log_activity(action, target_user_id=None, target_user_name=None, details=None):
    try:
        admin_id = session.get('user_id')
        if not admin_id:
            return 

        admin_res = supabase.table("profiles").select("first_name, last_name, email").eq("id", admin_id).single().execute()
        admin_name = "Unknown Admin"
        if admin_res.data:
            admin_name = f"{admin_res.data.get('first_name', '')} {admin_res.data.get('last_name', '')}".strip()
            if not admin_name:
                admin_name = admin_res.data.get('email', 'Unknown Admin')

        log_data = {
            "admin_id": admin_id,
            "admin_name": admin_name,
            "action": action,
            "target_user_id": target_user_id,
            "target_user_name": target_user_name,
            "details": details
        }
        supabase.table("activity_logs").insert(log_data).execute()
    except Exception as e:
        print(f"Failed to log activity: {e}")

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    try:
        return render_template(
            'dashboard.html',
            supabase_url=Config.SUPABASE_URL,
            supabase_key=Config.SUPABASE_KEY 
        )
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template('dashboard.html', supabase_url=None, supabase_key=None)

@admin_bp.route('/mark_notification_read/<log_id>', methods=['POST'])
@admin_required
def mark_notification_read(log_id):
    try:
        supabase.table("activity_logs").update({"is_read": True}).eq("id", log_id).execute()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- NEW: Global Lock/Unlock Routes ---
@admin_bp.route('/lock_all_students', methods=['POST'])
@admin_required
def lock_all_students():
    try:
        # Update all profiles where account_type is NOT admin
        supabase.table("profiles").update({"is_locked": True}).neq("account_type", "admin").execute()
        
        log_activity("Global Lock", details="Locked all student accounts.")
        flash("All student accounts have been locked.", "success")
    except Exception as e:
        flash(f"Error locking accounts: {str(e)}", "error")
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/unlock_all_students', methods=['POST'])
@admin_required
def unlock_all_students():
    try:
        supabase.table("profiles").update({"is_locked": False}).neq("account_type", "admin").execute()
        
        log_activity("Global Unlock", details="Unlocked all student accounts.")
        flash("All student accounts have been unlocked.", "success")
    except Exception as e:
        flash(f"Error unlocking accounts: {str(e)}", "error")
    return redirect(url_for('admin.admin_dashboard'))

# ... (admin_students remains same) ...
@admin_bp.route('/students')
@admin_required
def admin_students():
    try:
        search_name = request.args.get('search_name', '')
        filter_program = request.args.get('filter_program', '')
        filter_section = request.args.get('filter_section', '')
        filter_year_level = request.args.get('filter_year_level', '') 
        filter_major = request.args.get('filter_major', '') 
        sort_by = request.args.get('sort_by', 'last_name')
        sort_order = request.args.get('sort_order', 'asc')

        allowed_sorts = ['last_name', 'student_id', 'program', 'account_type', 'picture_status', 'signature_status']
        if sort_by not in allowed_sorts: sort_by = 'last_name'
        is_desc = (sort_order == 'desc')

        page = request.args.get('page', 1, type=int)
        per_page = 10 

        # Build Query
        query = supabase.table("profiles").select("*")
        query = query.eq('email_verified', True) # Verified filter

        if search_name:
            query = query.or_(f"first_name.ilike.%{search_name}%,last_name.ilike.%{search_name}%,middle_name.ilike.%{search_name}%,student_id.ilike.%{search_name}%,email.ilike.%{search_name}%")
        if filter_program: query = query.eq('program', filter_program)
        if filter_section: query = query.eq('section', filter_section)
        if filter_year_level: query = query.eq('year_level', filter_year_level) 
        if filter_major: query = query.eq('major', filter_major) 

        query = query.order(sort_by, desc=is_desc)
        if sort_by != 'last_name': query = query.order('last_name', desc=False) 

        start = (page - 1) * per_page
        end = start + per_page - 1
        
        # Get count
        count_query = supabase.table("profiles").select("*", count='exact', head=True).eq('email_verified', True)
        if search_name: 
             count_query = count_query.or_(f"first_name.ilike.%{search_name}%,last_name.ilike.%{search_name}%,middle_name.ilike.%{search_name}%,student_id.ilike.%{search_name}%,email.ilike.%{search_name}%")
        if filter_program: count_query = count_query.eq('program', filter_program)
        if filter_section: count_query = count_query.eq('section', filter_section)
        if filter_year_level: count_query = count_query.eq('year_level', filter_year_level) 
        if filter_major: count_query = count_query.eq('major', filter_major)

        count_res = count_query.execute()
        total_students = count_res.count if count_res.count is not None else 0
        total_pages = (total_students + per_page - 1) // per_page
        
        query = query.range(start, end)
        response = query.execute()
        students = response.data
        
        programs_res = supabase.table("profiles").select("program").execute()
        sections_res = supabase.table("profiles").select("section").execute()
        years_res = supabase.table("profiles").select("year_level").execute()
        majors_res = supabase.table("profiles").select("major").execute() 
        
        programs = sorted(list(set(p['program'] for p in programs_res.data if p.get('program'))))
        sections = sorted(list(set(s['section'] for s in sections_res.data if s.get('section'))))
        all_years = sorted(list(set(y['year_level'] for y in years_res.data if y.get('year_level'))), key=lambda x: (x or "Z")[0])
        all_majors = sorted(list(set(m['major'] for m in majors_res.data if m.get('major')))) 

        return render_template(
            'students.html', 
            students=students,
            programs=programs,
            sections=sections,
            all_years=all_years, 
            all_majors=all_majors, 
            search_name=search_name,
            filter_program=filter_program,
            filter_section=filter_section,
            filter_year_level=filter_year_level, 
            filter_major=filter_major,
            current_sort_by=sort_by,
            current_sort_order=sort_order,
            page=page,
            total_pages=total_pages,
            total_students=total_students
        )
    except Exception as e:
        flash(f"Error fetching students: {str(e)}", "error")
        return render_template('students.html', students=[], page=1, total_pages=1, total_students=0)

@admin_bp.route('/edit_student/<student_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_student(student_id):
    if request.method == 'POST':
        try:
            user_res = supabase.table("profiles").select("student_id, picture_disapproval_reason, signature_disapproval_reason, picture_status, signature_status").eq("id", student_id).single().execute()
            if not user_res.data:
                flash("Student profile not found.", "error")
                return redirect(url_for('admin.admin_students'))
            
            student_profile = user_res.data 
            student_num = student_profile['student_id'] 
            
            current_picture_reason = student_profile.get('picture_disapproval_reason')
            current_signature_reason = student_profile.get('signature_disapproval_reason')
            current_picture_status = student_profile.get('picture_status')
            current_signature_status = student_profile.get('signature_status')

            year_level = request.form.get('year_level')
            major = request.form.get('major')
            program = request.form.get('program') 

            if year_level in ("3rd Year", "4th Year"):
                if program in ("BSIT", "BSCS"):
                    if not major:
                        flash(f"Major is required for 3rd and 4th year {program} students.")
                        student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                        return render_template('edit_student.html', student=student_data)
                else: 
                    major = None
            else: 
                 major = None

            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')

            update_data = {
                "first_name": first_name,
                "middle_name": request.form.get('middle_name'),
                "last_name": last_name,
                "suffix_name": request.form.get('suffix_name'),
                "program": program,
                "semester": request.form.get('semester'),
                "year_level": year_level,
                "section": request.form.get('section'),
                "major": major,
                "account_type": request.form.get('account_type'),
                "picture_disapproval_reason": current_picture_reason,
                "signature_disapproval_reason": current_signature_reason,
                "picture_status": current_picture_status,
                "signature_status": current_signature_status
            }

            picture_file = request.files.get('picture')
            signature_file = request.files.get('signature')

            if picture_file and picture_file.filename:
                picture_bytes = picture_file.read()
                if len(picture_bytes) > Config.MAX_FILE_SIZE: 
                    flash(f"Picture file size must be less than {Config.MAX_FILE_SIZE // 1024 // 1024}MB.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('edit_student.html', student=student_data)
                    
                file_ext = os.path.splitext(picture_file.filename)[1]
                file_name = f"{student_num}_picture{file_ext}"
                supabase.storage.from_("pictures").upload(
                    file_name, picture_bytes, {"content-type": picture_file.mimetype, "upsert": "true"}
                )
                update_data["picture_url"] = supabase.storage.from_("pictures").get_public_url(file_name)
                update_data["picture_status"] = "approved"
                update_data["picture_disapproval_reason"] = None 

            if signature_file and signature_file.filename:
                signature_bytes = signature_file.read()
                if len(signature_bytes) > Config.MAX_FILE_SIZE:
                    flash(f"Signature file size must be less than {Config.MAX_FILE_SIZE // 1024 // 1024}MB.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('edit_student.html', student=student_data)

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
                update_data["signature_status"] = "approved"
                update_data["signature_disapproval_reason"] = None

            supabase.table("profiles").update(update_data).eq("id", student_id).execute()
            
            log_activity("Update Student", target_user_id=student_id, target_user_name=f"{first_name} {last_name}", details="Updated student profile details via admin edit.")

            flash('Student profile updated successfully.')
            return redirect(url_for('admin.admin_students'))

        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "error")
            student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
            return render_template('edit_student.html', student=student_data)

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
        profile_res = supabase.table("profiles").select("id, first_name, last_name, student_id, picture_url, signature_url").eq("id", student_id).single().execute()
        
        if not profile_res.data:
            flash("Student not found.", "error")
            return redirect(url_for('admin.admin_students'))
        
        profile = profile_res.data
        auth_user_id = profile['id']
        student_name = f"{profile.get('first_name')} {profile.get('last_name')}"

        try:
            files_to_remove_pic = []
            files_to_remove_sig = []
            if profile.get('picture_url'):
                pic_file_name = profile['picture_url'].split('/')[-1].split('?')[0] 
                if pic_file_name:
                    files_to_remove_pic.append(pic_file_name)
            if profile.get('signature_url'):
                sig_file_name = profile['signature_url'].split('/')[-1].split('?')[0]
                if sig_file_name:
                    files_to_remove_sig.append(sig_file_name)
            
            if files_to_remove_pic:
                supabase.storage.from_("pictures").remove(files_to_remove_pic)
            if files_to_remove_sig:
                supabase.storage.from_("signatures").remove(files_to_remove_sig)
                
        except Exception as e:
            print(f"Warning: Failed to delete storage files for {student_id}: {str(e)}")
            flash(f"Profile deleted, but failed to delete storage files: {str(e)}", "warning") 

        log_activity("Delete Student", target_user_id=auth_user_id, target_user_name=student_name, details=f"Deleted student {profile.get('student_id')}.")

        supabase.table("profiles").delete().eq("id", auth_user_id).execute()
        
        try:
             supabase_admin.auth.admin.delete_user(auth_user_id)
        except Exception as auth_e:
             print(f"CRITICAL ERROR: Profile {auth_user_id} deleted, but failed to delete auth user: {str(auth_e)}")
             flash(f"Profile deleted, but FAILED to delete authentication account: {str(auth_e)}. Manual cleanup required in Supabase Auth.", "error")
             return redirect(url_for('admin.admin_students')) 
             
        flash("Student deleted successfully (Auth, Profile, and Files).")
    except Exception as e:
        flash(f"Error during student deletion process: {str(e)}.", "error")
        
    return redirect(url_for('admin.admin_students'))

@admin_bp.route('/archive')
@admin_required
def admin_archive():
    try:
        filter_ay = request.args.get('filter_ay', '')
        filter_semester = request.args.get('filter_semester', '')
        filter_program = request.args.get('filter_program', '')
        filter_major = request.args.get('filter_major', '')

        query = supabase.table("archived_groups").select("*")

        if filter_ay:
            query = query.eq('academic_year', filter_ay)
        if filter_semester:
            query = query.eq('semester', filter_semester)
        if filter_program:
            query = query.ilike('group_name', f'{filter_program}%')
        if filter_major:
            if filter_major == 'None':
                 pass 
            else:
                 query = query.ilike('group_name', f'%{filter_major}%') 
        
        archives_res = query.order("created_at", desc=True).execute()
        archives = archives_res.data
        
        for archive in archives:
            try:
                utc_time = datetime.fromisoformat(archive['created_at'].replace('Z', '+00:00'))
                archive['created_at_display'] = utc_time.strftime('%Y-%m-%d %I:%M %p') 
            except Exception as parse_e:
                print(f"Error parsing date {archive.get('created_at')}: {parse_e}")
                archive['created_at_display'] = str(archive.get('created_at', ''))

        all_options_res = supabase.table("archived_groups").select("academic_year, semester, group_name").execute()
        all_data = all_options_res.data
        
        all_academic_years = sorted(list(set(d['academic_year'] for d in all_data if d.get('academic_year'))))
        all_semesters = sorted(list(set(d['semester'] for d in all_data if d.get('semester'))))
        
        all_programs = set()
        all_majors = set(['None']) 
        for d in all_data:
            if d.get('group_name'):
                parts = d['group_name'].split(' - ')
                if len(parts) > 0:
                    all_programs.add(parts[0])
                if len(parts) > 2: 
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
        current_program = request.args.get('program', '')
        current_year = request.args.get('year_level', '')
        current_section = request.args.get('section', '')
        current_semester = request.args.get('semester', '')

        # Fetch print settings
        settings_res = supabase.table("print_settings").select("*").eq("id", 1).single().execute()
        print_settings = settings_res.data if settings_res.data else {}

        query = supabase.table("profiles").select("program, year_level, section, major, semester")

        if current_program:
            query = query.eq('program', current_program)
        if current_year:
            query = query.eq('year_level', current_year)
        if current_section:
            query = query.eq('section', current_section)
        if current_semester:
            query = query.eq('semester', current_semester)
            
        profiles = query.execute().data
        
        all_profiles_res = supabase.table("profiles").select("program, year_level, section, semester").execute()
        all_profiles_data = all_profiles_res.data
        
        all_programs = sorted(list(set(p['program'] for p in all_profiles_data if p.get('program'))))
        all_years = sorted(list(set(p['year_level'] for p in all_profiles_data if p.get('year_level'))), key=lambda x: (x or "Z")[0])
        all_sections = sorted(list(set(p['section'] for p in all_profiles_data if p.get('section'))))
        all_semesters = sorted(list(set(p['semester'] for p in all_profiles_data if p.get('semester'))))

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
                semester_val
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
            current_semester=current_semester,
            print_settings=print_settings 
        )
    except Exception as e:
        flash(f"Error fetching groups: {str(e)}", "error")
        return render_template('printing.html', groups=[], error=str(e), all_programs=[], all_years=[], all_sections=[], all_semesters=[])

@admin_bp.route('/save_print_settings', methods=['POST'])
@admin_required
def admin_save_print_settings():
    try:
        settings_data = {
            "adviser1_name": request.form.get('adviser1_name'),
            "adviser1_title": request.form.get('adviser1_title'),
            "adviser1_date": request.form.get('adviser1_date'),
            "adviser2_name": request.form.get('adviser2_name'),
            "adviser2_title": request.form.get('adviser2_title'),
            "adviser2_date": request.form.get('adviser2_date'),
            "dean_name": request.form.get('dean_name'),
            "dean_title": request.form.get('dean_title'),
            "head_name": request.form.get('head_name'),
            "head_title": request.form.get('head_title'),
            "director_name": request.form.get('director_name'),
            "director_title": request.form.get('director_title'),
            "academic_year": request.form.get('academic_year')
        }
        settings_data['id'] = 1 
        supabase.table("print_settings").upsert(settings_data).execute()
        flash("Print settings saved successfully.", "success")
        return redirect(url_for('admin.admin_printing'))
    except Exception as e:
        flash(f"Error saving print settings: {str(e)}", "error")
        return redirect(url_for('admin.admin_printing'))

@admin_bp.route('/print_preview')
@admin_required
def admin_print_preview():
    program = request.args.get('program')
    year_level = request.args.get('year_level')
    section = request.args.get('section')
    major = request.args.get('major')
    semester = request.args.get('semester') 
    
    adviser1_name = request.args.get('adviser1_name')
    adviser1_title = request.args.get('adviser1_title')
    adviser1_date = request.args.get('adviser1_date')
    adviser2_name = request.args.get('adviser2_name')
    adviser2_title = request.args.get('adviser2_title')
    adviser2_date = request.args.get('adviser2_date')
    dean_name = request.args.get('dean_name')
    dean_title = request.args.get('dean_title')
    head_name = request.args.get('head_name')
    head_title = request.args.get('head_title')
    director_name = request.args.get('director_name')
    director_title = request.args.get('director_title')

    if not adviser1_name:
        try:
            settings_res = supabase.table("print_settings").select("*").eq("id", 1).single().execute()
            s = settings_res.data
            if s:
                adviser1_name = s.get('adviser1_name')
                adviser1_title = s.get('adviser1_title')
                adviser1_date = s.get('adviser1_date')
                adviser2_name = s.get('adviser2_name')
                adviser2_title = s.get('adviser2_title')
                adviser2_date = s.get('adviser2_date')
                dean_name = s.get('dean_name')
                dean_title = s.get('dean_title')
                head_name = s.get('head_name')
                head_title = s.get('head_title')
                director_name = s.get('director_name')
                director_title = s.get('director_title')
        except Exception as e:
            print(f"Error fetching print settings: {e}")

    if not all([program, year_level, section, semester]):
        flash("Error: Missing required group information (Program, Year, Section, Semester).", "error")
        return redirect(url_for('admin.admin_printing'))

    try:
        query = supabase.table("profiles").select("*")
        query = query.eq("program", program)
        query = query.eq("year_level", year_level)
        query = query.eq("section", section)
        query = query.eq("semester", semester) 
        query = query.eq("email_verified", True)
        if major == 'None' or major is None: query = query.is_("major", None)
        else: query = query.eq("major", major)

        response = query.execute()
        group_profiles = response.data

        members = []
        for p in group_profiles:
            last_name = p.get('last_name', '')
            first_name = p.get('first_name', '')
            middle_name = p.get('middle_name', '')
            suffix_name = p.get('suffix_name', '')
            full_name_parts = [last_name]
            if suffix_name: full_name_parts.append(suffix_name)
            full_name_str = " ".join(full_name_parts) + ","
            full_name = f"{full_name_str} {first_name} {middle_name}".strip()
            full_name = " ".join(full_name.split())
            if full_name == ',': full_name = "Name Missing"
                
            course_parts = [p.get('program', 'N/A'), f"{p.get('year_level', 'N/A')} {p.get('section', 'N/A')}"]
            if p.get('major'): course_parts.append(p.get('major'))
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

        today = datetime.now()
        generation_date = today.strftime("%B %d, %Y") 
        log_activity("Generate Print Preview", details=f"Generated preview for {program} {year_level}-{section}.")

        return render_template(
            './print_template.html',
            members=sorted_members, 
            # ... (other args) ...
            adviser1={'name': adviser1_name, 'title': adviser1_title, 'date': adviser1_date},
            adviser2={'name': adviser2_name, 'title': adviser2_title, 'date': adviser2_date},
            dean={'name': dean_name, 'title': dean_title},
            head={'name': head_name, 'title': head_title},
            director={'name': director_name, 'title': director_title},
            # Add missing args for template
            semester_display=f"{semester} Sem.",
            academic_year=f"AY {today.year}-{today.year+1}" # Simple default, ideally passed from form
        )
    except Exception as e:
        print(f"Error in admin_print_preview: {str(e)}") 
        flash(f"Error generating print preview: {str(e)}", "error")
        return redirect(url_for('admin.admin_printing'))

@admin_bp.route('/archive_group', methods=['POST'])
@admin_required
def admin_archive_group():
    try:
        program = request.form.get('program')
        year_level = request.form.get('year_level')
        section = request.form.get('section')
        major = request.form.get('major')
        semester = request.form.get('semester')
        academic_year_form = request.form.get('academic_year') 

        group_name_parts = [program, f"{year_level}{section}"]
        if major != 'None' and major: group_name_parts.append(major)
        group_name = " - ".join(group_name_parts)

        check_query = supabase.table("archived_groups").select("id").eq("group_name", group_name).eq("academic_year", academic_year_form).eq("semester", semester)
        check_res = check_query.execute()
        if check_res.data and len(check_res.data) > 0:
            flash(f"Archive for {group_name} ({academic_year_form} - {semester}) already exists.", "warning")
            return redirect(url_for('admin.admin_printing'))

        signatories = {
            "adviser1": { "name": request.form.get('adviser1_name'), "title": request.form.get('adviser1_title'), "date": request.form.get('adviser1_date') },
            "adviser2": { "name": request.form.get('adviser2_name'), "title": request.form.get('adviser2_title'), "date": request.form.get('adviser2_date') },
            "dean": { "name": request.form.get('dean_name'), "title": request.form.get('dean_title') },
            "head": { "name": request.form.get('head_name'), "title": request.form.get('head_title') },
            "director": { "name": request.form.get('director_name'), "title": request.form.get('director_title') }
        }

        if not academic_year_form or not all([program, year_level, section, semester]):
             flash("Missing required group information.", "error")
             return redirect(url_for('admin.admin_printing'))

        query = supabase.table("profiles").select("*")
        query = query.eq("program", program)
        query = query.eq("year_level", year_level)
        query = query.eq("section", section)
        query = query.eq("semester", semester)
        query = query.eq("email_verified", True)
        if major == 'None' or major is None: query = query.is_("major", None)
        else: query = query.eq("major", major)
        
        group_profiles = query.execute().data
        if not group_profiles:
            flash("Cannot archive an empty group. No verified students found matching the criteria.", "warning")
            return redirect(url_for('admin.admin_printing'))

        members = []
        for p in group_profiles:
            # ... (Name construction same as print_preview) ...
            last_name = p.get('last_name', '')
            first_name = p.get('first_name', '')
            middle_name = p.get('middle_name', '')
            suffix_name = p.get('suffix_name', '')
            full_name_parts = [last_name]
            if suffix_name: full_name_parts.append(suffix_name)
            full_name_str = " ".join(full_name_parts) + ","
            full_name = f"{full_name_str} {first_name} {middle_name}".strip()
            full_name = " ".join(full_name.split())
            if full_name == ',': full_name = "Name Missing"

            course_parts = [p.get('program', 'N/A'), f"{p.get('year_level', 'N/A')}{p.get('section', 'N/A')}"]
            if p.get('major'): course_parts.append(p.get('major'))
            course = " - ".join(filter(None, course_parts)).strip()
            
            archived_pic_url = p.get('picture_url') 
            if p.get('picture_url'):
                try:
                    src_filename = p['picture_url'].split('/')[-1].split('?')[0]
                    file_data = supabase_admin.storage.from_("pictures").download(src_filename)
                    if file_data:
                        ext = os.path.splitext(src_filename)[1]
                        safe_ay = academic_year_form.replace('/', '-').replace('\\', '-')
                        safe_sem = semester.replace(' ', '_')
                        dest_path = f"{safe_ay}/{safe_sem}/{p['student_id']}_picture{ext}"
                        content_type = mimetypes.guess_type(dest_path)[0] or 'application/octet-stream'
                        upload_res = supabase_admin.storage.from_("archive").upload(dest_path, file_data, {"upsert": "true", "content-type": content_type})
                        if hasattr(upload_res, 'status_code') and not str(upload_res.status_code).startswith('2'):
                             print(f"Failed to upload picture")
                        else:
                             archived_pic_url = supabase_admin.storage.from_("archive").get_public_url(dest_path)
                except Exception as e:
                    print(f"Error archiving picture for {p['student_id']}: {e}")

            archived_sig_url = p.get('signature_url') 
            if p.get('signature_url'):
                try:
                    src_filename = p['signature_url'].split('/')[-1].split('?')[0]
                    file_data = supabase_admin.storage.from_("signatures").download(src_filename)
                    if file_data:
                        ext = os.path.splitext(src_filename)[1]
                        safe_ay = academic_year_form.replace('/', '-').replace('\\', '-')
                        safe_sem = semester.replace(' ', '_')
                        dest_path = f"{safe_ay}/{safe_sem}/{p['student_id']}_signature{ext}"
                        content_type = mimetypes.guess_type(dest_path)[0] or 'application/octet-stream'
                        upload_res = supabase_admin.storage.from_("archive").upload(dest_path, file_data, {"upsert": "true", "content-type": content_type})
                        if hasattr(upload_res, 'status_code') and not str(upload_res.status_code).startswith('2'):
                             print(f"Failed to upload signature")
                        else:
                             archived_sig_url = supabase_admin.storage.from_("archive").get_public_url(dest_path)
                except Exception as e:
                    print(f"Error archiving signature for {p['student_id']}: {e}")

            member = {
                'full_name': full_name,
                'student_id': p.get('student_id', 'N/A'),
                'course': course,
                'picture_url': archived_pic_url, 
                'signature_url': archived_sig_url
            }
            members.append(member)
        
        sorted_members = sorted(members, key=lambda m: m.get('full_name', '').lower())
        today = datetime.now()
        generation_date = today.strftime("%B %d, %Y")
        
        insert_data = {
            "academic_year": academic_year_form,
            "semester": semester,
            "group_name": group_name,
            "student_data": sorted_members,
            "generation_date": generation_date,
            "signatories": signatories
        }
        
        supabase_admin.table("archived_groups").insert(insert_data).execute()
        log_activity("Archive Group", details=f"Archived group {group_name} for AY {academic_year_form}.")
        flash(f"Successfully archived group '{group_name}' for {academic_year_form}.", "success")
    except Exception as e:
        print(f"Error archiving group: {str(e)}") 
        flash(f"Error creating archive: {str(e)}", "error")
        
    return redirect(url_for('admin.admin_printing'))

@admin_bp.route('/archive_preview/<archive_id>')
@admin_required
def admin_archive_preview(archive_id):
    # ... (Keep existing logic, omitted for brevity as it's correct) ...
    try:
        archive_res = supabase.table("archived_groups").select("*").eq("id", archive_id).single().execute()
        if not archive_res.data:
            flash("Archive not found.", "error")
            return redirect(url_for('admin.admin_archive'))
        archive = archive_res.data
        sorted_members = archive.get('student_data', [])
        semester_display = f"{archive.get('semester', '?')} Sem."
        academic_year = archive.get('academic_year', 'N/A')
        generation_date = archive.get('generation_date', 'N/A')
        signatories = archive.get('signatories', {})
        default_date = generation_date
        
        adviser1 = signatories.get('adviser1', {'name': 'MERVIN JOMMEL T. DE JESUS', 'title': 'Organization Adviser', 'date': default_date})
        adviser2 = signatories.get('adviser2', {'name': 'LOUIE JEROME L. ROLDAN', 'title': 'Organization Adviser', 'date': default_date})
        dean = signatories.get('dean', {'name': 'FRANCIS F. BALAHADIA, DIT', 'title': 'Dean/Assoc. Dean of College'})
        head = signatories.get('head', {'name': 'NIÑO EMMANUEL ALDI L. ASTOVEZA', 'title': 'Head, Student Organization and Activities Unit'})
        director = signatories.get('director', {'name': 'JEANFEL J. CASIÑO', 'title': 'Director/Chairperson, Office of Student Affairs and Services'})

        return render_template('./print_template.html', members=sorted_members, semester_display=semester_display, academic_year=academic_year, generation_date=generation_date, adviser1=adviser1, adviser2=adviser2, dean=dean, head=head, director=director)
    except Exception as e:
        print(f"Error loading archive preview {archive_id}: {str(e)}") 
        flash(f"Error loading archive preview: {str(e)}", "error")
        return redirect(url_for('admin.admin_archive'))

@admin_bp.route('/delete_archive/<archive_id>', methods=['POST'])
@admin_required
def admin_delete_archive(archive_id):
    # ... (Keep existing logic, omitted for brevity) ...
    try:
        archive_res = supabase.table("archived_groups").select("group_name, academic_year").eq("id", archive_id).single().execute()
        archive_details = "Unknown Archive"
        if archive_res.data: archive_details = f"{archive_res.data.get('group_name')} ({archive_res.data.get('academic_year')})"
        supabase.table("archived_groups").delete().eq("id", archive_id).execute()
        log_activity("Delete Archive", details=f"Deleted archive: {archive_details}.")
        flash("Archive deleted successfully.", "success")
    except Exception as e:
        print(f"Error deleting archive {archive_id}: {str(e)}")
        flash(f"Error deleting archive: {str(e)}", "error")
    return redirect(url_for('admin.admin_archive'))

@admin_bp.route('/review_student/<student_id>', methods=['GET', 'POST'])
@admin_required
def admin_review_student(student_id):
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
            update_data = {}
            if action == 'approve_picture':
                update_data['picture_status'] = 'approved'
                update_data['picture_disapproval_reason'] = None
                update_data['is_locked'] = True
            elif action == 'approve_signature':
                update_data['signature_status'] = 'approved'
                update_data['signature_disapproval_reason'] = None
                update_data['is_locked'] = True
            elif action == 'disapprove_picture':
                reason = request.form.get('picture_disapproval_reason', '').strip()
                if not reason:
                    flash(f"A reason is required.", "error")
                    return render_template('review_student.html', student=student)
                update_data['picture_status'] = 'disapproved'
                update_data['picture_disapproval_reason'] = reason
                update_data['is_locked'] = False
            elif action == 'disapprove_signature':
                reason = request.form.get('signature_disapproval_reason', '').strip()
                if not reason:
                    flash(f"A reason is required.", "error")
                    return render_template('review_student.html', student=student)
                update_data['signature_status'] = 'disapproved'
                update_data['signature_disapproval_reason'] = reason
                update_data['is_locked'] = False
            else:
                flash("Invalid action.", "error")
                return render_template('review_student.html', student=student)

            if update_data: 
                 supabase.table("profiles").update(update_data).eq("id", student_id).execute()
                 student_name = f"{student.get('first_name')} {student.get('last_name')}"
                 log_activity("Review Student", target_user_id=student_id, target_user_name=student_name, details=f"Updated student status: {action}.")
                 flash("Student status updated.", "success")
            else:
                 flash("No changes detected.", "info") 
            return redirect(url_for('admin.admin_review_student', student_id=student_id)) 
        except Exception as e:
            flash(f"Error updating student status: {str(e)}", "error")
            return render_template('review_student.html', student=student)

    return render_template('review_student.html', student=student)

@admin_bp.route('/activity_logs')
@admin_required
def activity_logs():
    # ... (Keep existing logic) ...
    try:
        response = supabase.table("activity_logs").select("*").order("created_at", desc=True).limit(50).execute()
        logs = response.data
        for log in logs:
            try:
                if log.get('created_at'):
                    dt = datetime.fromisoformat(log['created_at'].replace('Z', '+00:00'))
                    log['created_at_display'] = dt.strftime('%b %d, %Y %I:%M %p')
                else:
                    log['created_at_display'] = 'N/A'
            except Exception as e:
                log['created_at_display'] = str(log.get('created_at'))
        return render_template('activity_logs.html', logs=logs)
    except Exception as e:
        flash(f"Error fetching activity logs: {str(e)}", "error")
        return render_template('activity_logs.html', logs=[])