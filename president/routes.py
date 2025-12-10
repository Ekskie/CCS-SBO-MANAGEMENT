import os
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import supabase
from utils import president_required, send_status_email
from config import Config
import pytz
from datetime import datetime
president_bp = Blueprint('president', __name__, template_folder='../templates')

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

        # Get current time in Philippines timezone
        ph_tz = pytz.timezone('Asia/Manila')
        timestamp_ph = datetime.now(ph_tz).isoformat()

        log_data = {
            "admin_id": admin_id,
            "admin_name": admin_name,
            "action": action,
            "target_user_id": target_user_id,
            "target_user_name": target_user_name,
            "details": details,
            "created_at": timestamp_ph
        }
        supabase.table("activity_logs").insert(log_data).execute()
    except Exception as e:
        print(f"Failed to log activity: {e}")

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

    # Prevent self-review
    if student_id == session['user_id']:
        flash("You cannot review your own profile.", "error")
        return redirect(url_for('president.president_dashboard'))

    # --- FETCH STUDENT ---
    try:
        student_res = (
            supabase.table("profiles")
            .select("*")
            .eq("id", student_id)
            .single()
            .execute()
        )

        if not student_res.data:
            flash("Student not found.", "error")
            return redirect(url_for('president.president_dashboard'))

        student = student_res.data

        # --- VALIDATE PRESIDENT CAN REVIEW THIS STUDENT ---
        pres_major = session.get('major')
        stud_major = student.get('major')
        majors_match = (pres_major == stud_major) or (not pres_major and not stud_major)

        if not (
            student.get('program') == session.get('program') and
            student.get('year_level') == session.get('year_level') and
            student.get('section') == session.get('section') and
            majors_match
        ):
            flash("You do not have permission to review this student.", "error")
            return redirect(url_for('president.president_dashboard'))

    except Exception as e:
        flash(f"Error fetching student: {str(e)}", "error")
        return redirect(url_for('president.president_dashboard'))

    # ========================
    #     PROCESS POST
    # ========================
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            update_data = {}
            email_subject = ""
            email_body = ""

            # ========= APPROVALS =========

            if action == 'approve_picture':
                update_data = {
                    'picture_status': 'approved',
                    'picture_disapproval_reason': None,
                    'is_locked': True
                }
                email_subject = "CCS SBO: Picture Approved"
                email_body = (
                    f"Hello {student.get('first_name')},\n\n"
                    "Your profile picture has been APPROVED by the Class President."
                )

            elif action == 'approve_signature':
                update_data = {
                    'signature_status': 'approved',
                    'signature_disapproval_reason': None,
                    'is_locked': True
                }
                email_subject = "CCS SBO: Signature Approved"
                email_body = (
                    f"Hello {student.get('first_name')},\n\n"
                    "Your digital signature has been APPROVED by the Class President."
                )

            # ========= DISAPPROVALS =========

            elif action == 'disapprove_picture':
                reason = request.form.get('picture_disapproval_reason', '').strip()
                if not reason:
                    flash("A reason is required.", "error")
                    return render_template('president/review_student.html', student=student)

                update_data = {
                    'picture_status': 'disapproved',
                    'picture_disapproval_reason': reason,
                    'is_locked': False
                }
                email_subject = "CCS SBO: Picture Disapproved"
                email_body = (
                    f"Hello {student.get('first_name')},\n\n"
                    "Your profile picture was DISAPPROVED by the Class President.\n"
                    f"Reason: {reason}\n\n"
                    "Please login and update your picture."
                )

            elif action == 'disapprove_signature':
                reason = request.form.get('signature_disapproval_reason', '').strip()
                if not reason:
                    flash("A reason is required.", "error")
                    return render_template('president/review_student.html', student=student)

                update_data = {
                    'signature_status': 'disapproved',
                    'signature_disapproval_reason': reason,
                    'is_locked': False
                }
                email_subject = "CCS SBO: Signature Disapproved"
                email_body = (
                    f"Hello {student.get('first_name')},\n\n"
                    "Your digital signature was DISAPPROVED by the Class President.\n"
                    f"Reason: {reason}\n\n"
                    "Please login and update your signature."
                )

            else:
                flash("Invalid action.", "error")
                return render_template('president/review_student.html', student=student)

            # ========= SAVE TO DB & SEND EMAIL =========

            if update_data:
                supabase.table("profiles").update(update_data).eq("id", student_id).execute()

                # Email the student
                if student.get('email'):
                    send_status_email(student.get('email'), email_subject, email_body)

                # Log activity
                student_name = f"{student.get('first_name')} {student.get('last_name')}"
                log_activity(
                    f"{action.replace('_', ' ').title()}",
                    target_user_id=student_id,
                    target_user_name=student_name,
                    details=f"Updated student status: {action}."
                )

                flash("Student profile updated and email notification sent.", "success")
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
