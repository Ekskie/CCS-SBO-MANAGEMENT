from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import supabase
from utils import president_required

# Define the Blueprint
# All routes in this file will be prefixed with /president
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
        
        if major:
            query = query.eq("major", major)
        else:
            query = query.is_("major", "null")
            
        query = query.neq("id", session['user_id'])
        
        response = query.order("last_name", desc=False).execute()
        classmates = response.data

        class_name_parts = [program, f"{year_level} {section}"]
        if major:
            class_name_parts.append(major)
        class_name = " - ".join(class_name_parts)

        # --- New Chart Logic ---
        fully_approved_count = 0
        pending_review_count = 0
        disapproved_count = 0
        
        for student in classmates:
            pic_status = student.get('picture_status')
            sig_status = student.get('signature_status')
            
            # Priority 1: If anything is disapproved
            if pic_status == 'disapproved' or sig_status == 'disapproved':
                disapproved_count += 1
            # Priority 2: If anything is pending (and not disapproved)
            elif pic_status == 'pending' or sig_status == 'pending':
                pending_review_count += 1
            # Priority 3: If both are approved
            elif pic_status == 'approved' and sig_status == 'approved':
                fully_approved_count += 1
        
        total_classmates = len(classmates)
        approval_percentage = 0
        if total_classmates > 0:
            approval_percentage = round((fully_approved_count / total_classmates) * 100)
        # --- End Chart Logic ---

        return render_template(
            'president/dashboard.html', 
            classmates=classmates,
            class_name=class_name,
            # --- Pass new data ---
            fully_approved_count=fully_approved_count,
            pending_review_count=pending_review_count,
            disapproved_count=disapproved_count,
            approval_percentage=approval_percentage
        )
    except Exception as e:
        flash(f"Error fetching classmates: {str(e)}", "error")
        # Pass 0s for chart data on error to prevent template crash
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
        
        if not (student.get('program') == session.get('program') and
                student.get('year_level') == session.get('year_level') and
                student.get('section') == session.get('section') and
                student.get('major') == session.get('major')):
            flash("You do not have permission to review this student.", "error")
            return redirect(url_for('president.president_dashboard'))
            
    except Exception as e:
        flash(f"Error fetching student: {str(e)}", "error")
        return redirect(url_for('president.president_dashboard'))
        

    if request.method == 'POST':
        try:
            action = request.form.get('action')
            disapproval_reason = request.form.get('disapproval_reason', '').strip()
            
            update_data = {}
            
            # --- FIX: Match button values from HTML template ---
            if action == 'approve_picture':
                update_data['picture_status'] = 'approved'
            elif action == 'approve_signature':
                update_data['signature_status'] = 'approved'
            
            elif action in ('disapprove_picture', 'disapprove_signature'):
                if not disapproval_reason:
                    flash("A reason is required for disapproval.", "error")
                    return render_template('president/review_student.html', student=student)
                
                existing_reason = student.get('disapproval_reason') or ""
                if disapproval_reason not in existing_reason:
                    new_reason = f"{existing_reason} [Reason: {disapproval_reason}]".strip()
                else:
                    new_reason = existing_reason
                
                update_data['disapproval_reason'] = new_reason

                if action == 'disapprove_picture':
                    update_data['picture_status'] = 'disapproved'
                elif action == 'disapprove_signature':
                    update_data['signature_status'] = 'disapproved'
            # --- END OF FIX ---
            
            else:
                flash("Invalid action.", "error")
                return render_template('president/review_student.html', student=student)
            
            supabase.table("profiles").update(update_data).eq("id", student_id).execute()
            flash("Student profile updated.", "success")
            return redirect(url_for('president.president_review_student', student_id=student_id))

        except Exception as e:
            flash(f"Error updating student status: {str(e)}", "error")

    # GET request
    return render_template('president/review_student.html', student=student)