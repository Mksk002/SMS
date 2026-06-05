from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import hashlib
import io

app = Flask(__name__)
app.secret_key = "super_secret_key"

# ==================== UTILITIES & DB UPGRADE ====================
def get_db_connection():
    conn = sqlite3.connect('school_cs_pro.db')
    conn.row_factory = sqlite3.Row  
    return conn

# Auto-add the 'course' column to the notes table if it doesn't exist yet
def upgrade_db():
    conn = get_db_connection()
    try:
        conn.execute("ALTER TABLE notes ADD COLUMN course TEXT DEFAULT 'ALL'")
        conn.commit()
    except sqlite3.OperationalError:
        pass # The column already exists, do nothing
    finally:
        conn.close()

upgrade_db() # Run upgrade check on startup

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_int(val):
    try: return int(val)
    except (ValueError, TypeError): return 0

# ==================== LOGIN & LOGOUT ====================
@app.route('/')
def main_menu():
    if 'role' in session:
        if session['role'] == 'Admin': return redirect(url_for('admin_dashboard'))
        if session['role'] == 'Teacher': return redirect(url_for('teacher_dashboard'))
        if session['role'] == 'Student': return redirect(url_for('student_dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    uid, password, role = request.form['uid'], hash_password(request.form['password']), request.form['role']
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE uid=? AND password=? AND role=?", (uid, password, role)).fetchone()
    conn.close()

    if user:
        session['uid'], session['name'], session['role'] = user['uid'], user['name'], user['role']
        if role == 'Admin': return redirect(url_for('admin_dashboard'))
        elif role == 'Teacher': return redirect(url_for('teacher_dashboard'))
        elif role == 'Student': return redirect(url_for('student_dashboard'))
    else:
        flash("Invalid Credentials or Role!", "error")
        return redirect(url_for('main_menu'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main_menu'))

# ==================== ADMIN ROUTES ====================
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'Admin': return redirect(url_for('main_menu'))
    conn = get_db_connection()
    teachers = conn.execute("SELECT uid, name, email, contact FROM users WHERE role='Teacher'").fetchall()
    students = conn.execute("SELECT uid, name, course, contact FROM users WHERE role='Student'").fetchall()
    conn.close()
    return render_template('admin.html', teachers=teachers, students=students)

@app.route('/add_teacher', methods=['POST'])
def add_teacher():
    if session.get('role') != 'Admin': return redirect(url_for('main_menu'))
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO users (uid, name, password, role, email, contact) VALUES (?,?,?,?,?,?)",
                     (request.form['uid'], request.form['name'], hash_password(request.form['password']), "Teacher", request.form['email'], request.form['contact']))
        conn.commit()
        flash("Teacher Added Successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Error: Teacher ID already exists!", "error")
    finally:
        conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/update_teacher', methods=['POST'])
def update_teacher():
    if session.get('role') != 'Admin': return redirect(url_for('main_menu'))
    uid, name, password, email, contact = request.form['uid'], request.form['name'], request.form['password'], request.form['email'], request.form['contact']
    conn = get_db_connection()
    if password: 
        conn.execute("UPDATE users SET name=?, password=?, email=?, contact=? WHERE uid=? AND role='Teacher'", (name, hash_password(password), email, contact, uid))
    else:
        conn.execute("UPDATE users SET name=?, email=?, contact=? WHERE uid=? AND role='Teacher'", (name, email, contact, uid))
    conn.commit()
    conn.close()
    flash("Teacher Updated Successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_teacher/<uid>')
def delete_teacher(uid):
    if session.get('role') != 'Admin': return redirect(url_for('main_menu'))
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE uid=? AND role='Teacher'", (uid,))
    conn.commit()
    conn.close()
    flash("Teacher Removed!", "success")
    return redirect(url_for('admin_dashboard'))

# ==================== TEACHER ROUTES ====================
@app.route('/teacher')
def teacher_dashboard():
    if session.get('role') != 'Teacher': return redirect(url_for('main_menu'))
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM users WHERE role='Student'").fetchall()
    conn.close()
    return render_template('teacher.html', students=students)

@app.route('/add_student', methods=['POST'])
def add_student():
    if session.get('role') != 'Teacher': return redirect(url_for('main_menu'))
    f = request.form
    conn = get_db_connection()
    try:
        conn.execute("""INSERT INTO users (uid, name, password, role, email, address, course, m1, m2, cs1, cs2, attendance, sec_answer, contact) 
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (f['uid'], f['name'], hash_password(f['password']), 'Student', f['email'], f['address'], f['course'], 
                      get_int(f['m1']), get_int(f['m2']), get_int(f['cs1']), get_int(f['cs2']), get_int(f['attendance']), f['sec_answer'].lower(), f['contact']))
        conn.commit()
        flash("Student Enrolled Successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Error: Roll Number already exists!", "error")
    finally:
        conn.close()
    return redirect(url_for('teacher_dashboard'))

@app.route('/update_student', methods=['POST'])
def update_student():
    if session.get('role') != 'Teacher': return redirect(url_for('main_menu'))
    f = request.form
    conn = get_db_connection()
    if f['password']:
        conn.execute("""UPDATE users SET name=?, password=?, email=?, address=?, course=?, m1=?, m2=?, cs1=?, cs2=?, attendance=?, sec_answer=?, contact=? WHERE uid=? AND role='Student'""",
                     (f['name'], hash_password(f['password']), f['email'], f['address'], f['course'], get_int(f['m1']), get_int(f['m2']), get_int(f['cs1']), get_int(f['cs2']), get_int(f['attendance']), f['sec_answer'].lower(), f['contact'], f['uid']))
    else:
        conn.execute("""UPDATE users SET name=?, email=?, address=?, course=?, m1=?, m2=?, cs1=?, cs2=?, attendance=?, sec_answer=?, contact=? WHERE uid=? AND role='Student'""",
                     (f['name'], f['email'], f['address'], f['course'], get_int(f['m1']), get_int(f['m2']), get_int(f['cs1']), get_int(f['cs2']), get_int(f['attendance']), f['sec_answer'].lower(), f['contact'], f['uid']))
    conn.commit()
    conn.close()
    flash("Student Details Updated!", "success")
    return redirect(url_for('teacher_dashboard'))

@app.route('/delete_student/<uid>')
def delete_student(uid):
    if session.get('role') != 'Teacher': return redirect(url_for('main_menu'))
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE uid=? AND role='Student'", (uid,))
    conn.commit()
    conn.close()
    flash("Student Removed Successfully!", "success")
    return redirect(url_for('teacher_dashboard'))

# --- NEW SEPARATE NOTES MODULE FOR TEACHERS ---
@app.route('/teacher/notes')
def teacher_notes():
    if session.get('role') != 'Teacher': return redirect(url_for('main_menu'))
    conn = get_db_connection()
    # Fetch notes along with their designated course
    notes = conn.execute("SELECT id, title, teacher_name, file_name, course FROM notes").fetchall()
    conn.close()
    return render_template('teacher_notes.html', notes=notes)

@app.route('/add_note', methods=['POST'])
def add_note():
    if session.get('role') != 'Teacher': return redirect(url_for('main_menu'))
    file = request.files.get('file_upload')
    file_name = file.filename if (file and file.filename != '') else None
    file_data = file.read() if file_name else None
    course = request.form['course'] # Get the target course
        
    conn = get_db_connection()
    conn.execute("INSERT INTO notes (title, content, teacher_name, file_name, file_data, course) VALUES (?, ?, ?, ?, ?, ?)", 
                 (request.form['title'], request.form['content'], session['name'], file_name, file_data, course))
    conn.commit()
    conn.close()
    flash("Note Uploaded and Assigned to Course Successfully!", "success")
    return redirect(url_for('teacher_notes')) # Redirects back to the dedicated notes page

@app.route('/delete_note/<int:note_id>')
def delete_note(note_id):
    if session.get('role') != 'Teacher': return redirect(url_for('main_menu'))
    conn = get_db_connection()
    conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
    conn.commit()
    conn.close()
    flash("Note Deleted!", "success")
    return redirect(url_for('teacher_notes'))

# ==================== STUDENT ROUTES ====================
@app.route('/student')
def student_dashboard():
    if session.get('role') != 'Student': return redirect(url_for('main_menu'))
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM users WHERE uid=? AND role='Student'", (session['uid'],)).fetchone()
    
    # MAGIC HAPPENS HERE: Only fetch notes meant for "ALL" courses, or this specific student's course!
    notes = conn.execute("SELECT id, title, content, teacher_name, file_name, course FROM notes WHERE course='ALL' OR course=?", (student['course'],)).fetchall()
    conn.close()
    
    m1, m2, cs1, cs2 = student['m1'] or 0, student['m2'] or 0, student['cs1'] or 0, student['cs2'] or 0
    total = m1 + m2 + cs1 + cs2
    pct = (total / 400) * 100
    if pct >= 90: grade = "A+ 🌟"
    elif pct >= 80: grade = "A 👍"
    elif pct >= 70: grade = "B"
    elif pct >= 60: grade = "C"
    else: grade = "F ⚠️"
    
    return render_template('student.html', student=student, total=total, pct=pct, grade=grade, notes=notes)

@app.route('/download_file/<int:note_id>')
def download_file(note_id):
    if session.get('role') not in ['Student', 'Teacher']: return redirect(url_for('main_menu'))
    conn = get_db_connection()
    note = conn.execute("SELECT file_name, file_data FROM notes WHERE id=?", (note_id,)).fetchone()
    conn.close()
    
    if note and note['file_data']:
        return send_file(io.BytesIO(note['file_data']), download_name=note['file_name'], as_attachment=True)
    return "File not found", 404

if __name__ == '__main__':
    app.run(debug=True)
