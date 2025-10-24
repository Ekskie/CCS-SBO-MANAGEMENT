import os
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import supabase, supabase_admin
from utils import admin_required, check_transparency
from config import MAX_FILE_SIZE
from datetime import datetime

# Define the Blueprint
# All routes in this file will be prefixed with /admin
admin_bp = Blueprint('admin', __name__, template_folder='../templates')

@admin_bp.route('/')
@admin_bp.route('/dashboard')
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

@admin_bp.route('/students')
@admin_required
def admin_students():
    try:
        search_name = request.args.get('search_name', '')
        filter_program = request.args.get('filter_program', '')
        filter_section = request.args.get('filter_section', '')
        filter_year_level = request.args.get('filter_year_level', '')
        filter_major = request.args.get('filter_major', '')

        query = supabase.table("profiles").select("*")

        if search_name:
            query = query.or_(f"first_name.ilike.%{search_name}%,last_name.ilike.%{search_name}%,middle_name.ilike.%{search_name}%")
        if filter_program:
            query = query.eq('program', filter_program)
        if filter_section:
            query = query.eq('section', filter_section)
        if filter_year_level:
            query = query.eq('year_level', filter_year_level)
        if filter_major:
            query = query.eq('major', filter_major)

        response = query.order("last_name", desc=False).execute()
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
            'admin/students.html', 
            students=students,
            programs=programs,
            sections=sections,
            all_years=all_years,
            all_majors=all_majors,
            search_name=search_name,
            filter_program=filter_program,
            filter_section=filter_section,
            filter_year_level=filter_year_level,
            filter_major=filter_major
        )
    except Exception as e:
        flash(f"Error fetching students: {str(e)}", "error")
        return render_template('admin/students.html', students=[], programs=[], sections=[], all_years=[], all_majors=[])

@admin_bp.route('/edit_student/<student_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_student(student_id):
    if request.method == 'POST':
        try:
            user_res = supabase.table("profiles").select("student_id, disapproval_reason").eq("id", student_id).single().execute()
            if not user_res.data:
                flash("Student profile not found.", "error")
                return redirect(url_for('admin.admin_students'))
            
            student_num = user_res.data['student_id']
            current_disapproval_reason = user_res.data.get('disapproval_reason')

            year_level = request.form.get('year_level')
            major = request.form.get('major')

            if year_level in ("3rd Year", "4th Year"):
                if not major:
                    flash("Major is required for 3rd and 4th year students.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('admin/edit_student.html', student=student_data)
            else:
                major = None 

            update_data = {
                "first_name": request.form.get('first_name'),
                "middle_name": request.form.get('middle_name'),
                "last_name": request.form.get('last_name'),
                "program": request.form.get('program'),
                "semester": request.form.get('semester'),
                "year_level": year_level,
                "section": request.form.get('section'),
                "major": major,
                "account_type": request.form.get('account_type'),
                "disapproval_reason": current_disapproval_reason
            }

            picture_file = request.files.get('picture')
            signature_file = request.files.get('signature')

            if picture_file and picture_file.filename:
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
                update_data["picture_status"] = "pending"
                update_data["disapproval_reason"] = None 

            if signature_file and signature_file.filename:
                signature_bytes = signature_file.read()
                if len(signature_bytes) > MAX_FILE_SIZE:
                    flash(f"Signature file size must be less than {MAX_FILE_SIZE // 1024 // 1024}MB.")
                    student_data = supabase.table("profiles").select("*").eq("id", student_id).single().execute().data
                    return render_template('admin/edit_student.html', student=student_data)

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
                update_data["signature_status"] = "pending"
                update_data["disapproval_reason"] = None 

            supabase.table("profiles").update(update_data).eq("id", student_id).execute()
            flash('Student profile updated successfully.')
            return redirect(url_for('admin.admin_students'))

        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "error")
            return redirect(url_for('admin.admin_edit_student', student_id=student_id))

    # GET request
    try:
        response = supabase.table("profiles").select("*").eq("id", student_id).single().execute()
        if not response.data:
            flash("Student profile not found.", "error")
            return redirect(url_for('admin.admin_students'))
        
        return render_template('admin/edit_student.html', student=response.data)
    except Exception as e:
        flash(f"Error fetching profile: {str(e)}", "error")
        return redirect(url_for('admin.admin_students'))

@admin_bp.route('/delete_student/<student_id>', methods=['POST'])
@admin_required
def admin_delete_student(student_id):
    try:
        profile_res = supabase.table("profiles").select("id, student_id, picture_url, signature_url").eq("id", student_id).single().execute()
        
        if not profile_res.data:
            flash("Student not found.", "error")
            return redirect(url_for('admin.admin_students'))
        
        profile = profile_res.data
        auth_user_id = profile['id']

        try:
            if profile.get('picture_url'):
                pic_file_name = profile['picture_url'].split('/')[-1].split('?')[0]
                if pic_file_name:
                    supabase.storage.from_("pictures").remove([pic_file_name])
            if profile.get('signature_url'):
                sig_file_name = profile['signature_url'].split('/')[-1].split('?')[0]
                if sig_file_name:
                    supabase.storage.from_("signatures").remove([sig_file_name])
        except Exception as e:
            flash(f"Profile deleted, but failed to delete storage files: {str(e)}", "warning")

        supabase.table("profiles").delete().eq("id", auth_user_id).execute()
        
        supabase_admin.auth.admin.delete_user(auth_user_id)
        
        flash("Student deleted successfully (Auth, Profile, and Files).")
    except Exception as e:
        flash(f"Error deleting student: {str(e)}. You may need to manually delete the user from the Supabase Auth panel.", "error")
        
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
            query = query.ilike('group_name', f'%{filter_major}%')
        
        archives_res = query.order("created_at", desc=True).execute()
        archives = archives_res.data
        
        for archive in archives:
            try:
                utc_time = datetime.fromisoformat(archive['created_at'].replace('Z', '+00:00'))
                archive['created_at'] = utc_time.strftime('%Y-%m-%d %I:%M %p')
            except Exception:
                archive['created_at'] = str(archive.get('created_at', ''))

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
                if len(parts) > 2: 
                    all_majors.add(parts[2])
                    
        all_programs = sorted(list(all_programs))
        all_majors = sorted(list(all_majors))

        return render_template(
            'admin/archive.html', 
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
        return render_template('admin/archive.html', archives=[], all_academic_years=[], all_semesters=[], all_programs=[], all_majors=[], current_ay='', current_semester='', current_program='', current_major='')


@admin_bp.route('/printing')
@admin_required
def admin_printing():
    try:
        current_program = request.args.get('program', '')
        current_year = request.args.get('year_level', '')
        current_section = request.args.get('section', '')
        current_semester = request.args.get('semester', '')

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
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/print_preview')
@admin_required
def admin_print_preview():
    program = request.args.get('program')
    year_level = request.args.get('year_level')
    section = request.args.get('section')
    major = request.args.get('major') 
    semester = request.args.get('semester') 

    if not all([program, year_level, section, major, semester]):
        flash("Error: Missing group information, including semester.", "error")
        return redirect(url_for('admin.admin_printing'))

    try:
        query = supabase.table("profiles").select("*")
        query = query.eq("program", program)
        query = query.eq("year_level", year_level)
        query = query.eq("section", section)
        query = query.eq("semester", semester)
        
        if major == 'None':
            query = query.is_("major", "null")
        else:
            query = query.eq("major", major)

        response = query.execute()
        group_profiles = response.data

        if not group_profiles:
            flash(f"No profiles found for this group.", "error")
            return redirect(url_for('admin.admin_printing'))

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

        semester_display = f"{semester} Sem."
        
        today = datetime.now()
        current_year = today.year
        if today.month >= 8: 
            academic_year = f"AY {current_year}-{current_year + 1}"
        else: 
            academic_year = f"AY {current_year - 1}-{current_year}"
            
        generation_date = today.strftime("%B %d, %Y") 

        return render_template(
            'print_template.html', 
            members=sorted_members, 
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
        program = request.form.get('program')
        year_level = request.form.get('year_level')
        section = request.form.get('section')
        major = request.form.get('major')
        semester = request.form.get('semester')
        academic_year_form = request.form.get('academic_year')

        if not academic_year_form:
            flash("Academic Year is required to create an archive.", "error")
            return redirect(url_for('admin.admin_printing'))

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

        today = datetime.now()
        generation_date = today.strftime("%B %d, %Y")
        
        group_name_parts = [program, f"{year_level}{section}"]
        if major != 'None':
            group_name_parts.append(major)
        group_name = " - ".join(group_name_parts)

        insert_data = {
            "academic_year": academic_year_form, 
            "semester": semester,
            "group_name": group_name,
            "student_data": sorted_members,
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
        archive_res = supabase.table("archived_groups").select("*").eq("id", archive_id).single().execute()
        
        if not archive_res.data:
            flash("Archive not found.", "error")
            return redirect(url_for('admin.admin_archive'))
            
        archive = archive_res.data
        
        sorted_members = archive.get('student_data', [])
        semester_display = f"{archive.get('semester')} Sem."
        academic_year = archive.get('academic_year')
        generation_date = archive.get('generation_date')

        return render_template(
            'print_template.html', 
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

# --- NEW: Admin Review Route ---
@admin_bp.route('/review/<student_id>', methods=['GET', 'POST'])
@admin_required
def admin_review_student(student_id):
    # Admins can review anyone, so we only fetch the student
    try:
        student_res = supabase.table("profiles").select("*").eq("id", student_id).single().execute()
        if not student_res.data:
            flash("Student not found.", "error")
            return redirect(url_for('admin.admin_students'))
        
        student = student_res.data
            
    except Exception as e:
        flash(f"Error fetching student: {str(e)}", "error")
        return redirect(url_for('admin.admin_students'))
        
    # Handle the form submission
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
                    return render_template('admin/review_student.html', student=student)
                
                # Overwrite reason completely, as admin has final say
                update_data['disapproval_reason'] = f"[Admin Reason: {disapproval_reason}]".strip()

                if action == 'disapprove_picture':
                    update_data['picture_status'] = 'disapproved'
                elif action == 'disapprove_signature':
                    update_data['signature_status'] = 'disapproved'
            
            else:
                flash("Invalid action.", "error")
                return render_template('admin/review_student.html', student=student)
            
            # Apply the update
            supabase.table("profiles").update(update_data).eq("id", student_id).execute()
            flash("Student profile updated by admin.", "success")
            return redirect(url_for('admin.admin_students'))

        except Exception as e:
            flash(f"Error updating student status: {str(e)}", "error")

    # GET request: Show the review page
    return render_template('admin/review_student.html', student=student)

