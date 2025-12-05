import os
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import supabase
from utils import president_required
from config import Config

president_bp = Blueprint('president', __name__, template_folder='../templates')

@president_bp.route('/')
@president_bp.route('/dashboard')
@president_required
def president_dashboard():
    try:
        program = session.get('program')
        year_level = session.get('year_level')
        section = session.get('section')
        major = session.get('major') 

        query = supabase.table("profiles").select("*")
        query = query.eq("program", program)
        query = query.eq("year_level", year_level)
        query = query.eq("section", section)
        if major: query = query.eq("major", major)
        else: query = query.is_("major", "null")
        query = query.neq("id", session['user_id'])
        
        response = query.order("last_name", desc=False).execute()
        classmates = response.data

        class_name_parts = [program, f"{year_level} {section}"]
        if major: class_name_parts.append(major)
        class_name = " - ".join(class_name_parts)

        fully_approved_count = 0
        pending_review_count = 0
        disapproved_count = 0
        
        for student in classmates:
            pic_status = student.get('picture_status')
            sig_status = student.get('signature_status')
            if pic_status == 'disapproved' or sig_status == 'disapproved':
                disapproved_count += 1
            elif pic_status == 'pending' or sig_status == 'pending':
                pending_review_count += 1
            elif pic_status == 'approved' and sig_status == 'approved':
                fully_approved_count += 1
        
        total_classmates = len(classmates)
        approval_percentage = 0
        if total_classmates > 0:
            approval_percentage = round((fully_approved_count / total_classmates) * 100)

        return render_template('president/dashboard.html', classmates=classmates, class_name=class_name, fully_approved_count=fully_approved_count, pending_review_count=pending_review_count, disapproved_count=disapproved_count, approval_percentage=approval_percentage)
    except Exception as e:
        flash(f"Error fetching classmates: {str(e)}", "error")
        return render_template('president/dashboard.html', classmates=[], class_name="Error", fully_approved_count=0, pending_review_count=0, disapproved_count=0, approval_percentage=0)

@president_bp.route('/review/<student_id>', methods=['GET', 'POST'])
@president_required
def president_review_student(student_id):
    if student_id == session['user_id']:
        flash("You cannot review your own profile.", "error")
        return redirect(url_for('president.president_dashboard'))

    try:
        student_res = supabase.table("profiles").select("*").eq("id", student_id).single().execute()
        if not student_res.data:
            flash("Student not found.", "error")
            return redirect(url_for('president.president_dashboard'))
        
        student = student_res.data
        pres_major = session.get('major')
        stud_major = student.get('major')
        majors_match = (pres_major == stud_major) or (not pres_major and not stud_major)

        if not (student.get('program') == session.get('program') and
                student.get('year_level') == session.get('year_level') and
                student.get('section') == session.get('section') and
                majors_match):
            flash("You do not have permission to review this student.", "error")
            return redirect(url_for('president.president_dashboard'))
    except Exception as e:
        flash(f"Error fetching student: {str(e)}", "error")
        return redirect(url_for('president.president_dashboard'))

    if request.method == 'POST':
        try:
            action = request.form.get('action')
            update_data = {}
            
            if action == 'approve_picture':
                update_data['picture_status'] = 'approved'
                update_data['picture_disapproval_reason'] = None
                # LOCK Account on President Approval
                update_data['is_locked'] = True

            elif action == 'approve_signature':
                update_data['signature_status'] = 'approved'
                update_data['signature_disapproval_reason'] = None
                # LOCK Account on President Approval
                update_data['is_locked'] = True
            
            elif action == 'disapprove_picture':
                reason = request.form.get('picture_disapproval_reason', '').strip()
                if not reason:
                    flash("A reason is required.", "error")
                    return render_template('president/review_student.html', student=student)
                update_data['picture_status'] = 'disapproved'
                update_data['picture_disapproval_reason'] = reason
                # UNLOCK on Disapproval
                update_data['is_locked'] = False

            elif action == 'disapprove_signature':
                reason = request.form.get('signature_disapproval_reason', '').strip()
                if not reason:
                    flash("A reason is required.", "error")
                    return render_template('president/review_student.html', student=student)
                update_data['signature_status'] = 'disapproved'
                update_data['signature_disapproval_reason'] = reason
                # UNLOCK on Disapproval
                update_data['is_locked'] = False
            
            else:
                flash("Invalid action.", "error")
                return render_template('president/review_student.html', student=student)
            
            if update_data:
                supabase.table("profiles").update(update_data).eq("id", student_id).execute()
                flash("Student profile updated.", "success")
            else:
                flash("No changes made.", "info")

            return redirect(url_for('president.president_review_student', student_id=student_id))

        except Exception as e:
            flash(f"Error updating student status: {str(e)}", "error")

    return render_template('president/review_student.html', student=student)

@president_bp.route('/notify_admin', methods=['POST'])
@president_required
def notify_admin():
    try:
        program = session.get('program')
        year_level = session.get('year_level')
        section = session.get('section')
        major = session.get('major')
        president_name = session.get('full_name') or "A President"
        class_name_parts = [program, f"{year_level} {section}"]
        if major: class_name_parts.append(major)
        class_name = " - ".join(class_name_parts)
        log_entry = {
            "admin_name": "System Notification",
            "action": "Class Review Complete",
            "details": f"President {president_name} has finished reviewing {class_name}. The class is ready for final checking.",
            "target_user_name": class_name 
        }
        supabase.table("activity_logs").insert(log_entry).execute()
        flash("Admin has been notified that your class is ready for checking.", "success")
    except Exception as e:
        flash(f"Error sending notification: {str(e)}", "error")
    return redirect(url_for('president.president_dashboard'))