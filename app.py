import csv
import io
import os
import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from functools import wraps
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)
secret_key = os.getenv("SECRET_KEY")
if not secret_key and os.getenv("FLASK_DEBUG", "false").lower() != "true":
    raise RuntimeError("Set SECRET_KEY in the environment before starting the production app.")
app.secret_key = secret_key or "local-development-only-change-me"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("FLASK_DEBUG", "false").lower() != "true",
)


def db():
    options = dict(
        host=os.getenv("DB_HOST") or os.getenv("MYSQLHOST", "localhost"),
        port=int(os.getenv("DB_PORT") or os.getenv("MYSQLPORT", "3306")),
        user=os.getenv("DB_USER") or os.getenv("MYSQLUSER", "root"),
        password=os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD", ""),
        database=os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE", "attendance_db"),
    )
    ca_file = os.getenv("DB_SSL_CA")
    if ca_file:
        options.update(ssl_ca=ca_file, ssl_verify_cert=True, ssl_verify_identity=True)
    return mysql.connector.connect(**options)


def query(sql, params=(), one=False, write=False):
    conn = db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        result = cur.fetchone() if one else (cur.fetchall() if not write else None)
        if write:
            conn.commit()
        return result
    finally:
        cur.close()
        conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped


@app.context_processor
def common_values():
    email_ready = all(os.getenv(key) for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"))
    return {"today": date.today().isoformat(), "current_user": session.get("username"),
            "email_ready": email_ready}


def record_notification(student_id, attendance_date, subject_name, channel, recipient, status, details=""):
    try:
        query("""INSERT INTO notification_logs(student_id,attendance_date,subject_name,channel,recipient,delivery_status,details)
          VALUES(%s,%s,%s,%s,%s,%s,%s)""",
          (student_id, attendance_date, subject_name, channel, recipient, status, details[:250] or None), write=True)
    except mysql.connector.Error:
        app.logger.exception("Could not save notification delivery log")


def send_guardian_email(student, attendance_date, subject_name, status):
    results = []
    date_label = datetime.strptime(attendance_date, "%Y-%m-%d").strftime("%d %b %Y")

    email_to = (student.get("guardian_email") or "").strip()
    if email_to and all(os.getenv(key) for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM")):
        try:
            message = EmailMessage()
            message["Subject"] = f"Attendance update: {student['full_name']} marked {status}"
            message["From"] = os.getenv("SMTP_FROM")
            message["To"] = email_to
            message.set_content(
                f"Hello {student.get('guardian_name') or 'Parent/Guardian'},\n\n"
                f"{student['full_name']} (Roll {student['roll_no']}, Class {student['class_name']}) "
                f"was marked {status} for {subject_name} on {date_label}.\n\nAttendEase"
            )
            host = os.getenv("SMTP_HOST")
            port = int(os.getenv("SMTP_PORT", "587"))
            if os.getenv("SMTP_USE_SSL", "false").lower() == "true":
                with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                    smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(host, port, timeout=15) as smtp:
                    smtp.ehlo()
                    if os.getenv("SMTP_USE_TLS", "true").lower() == "true":
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                    smtp.send_message(message)
            record_notification(student["id"], attendance_date, subject_name, "Email", email_to, "Sent", "Accepted by SMTP server")
            results.append({"channel": "Email", "sent": True})
        except Exception as exc:
            record_notification(student["id"], attendance_date, subject_name, "Email", email_to, "Failed", str(exc))
            results.append({"channel": "Email", "sent": False})
    return results


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = query("SELECT * FROM users WHERE username=%s", (username,), one=True)
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Username ya password sahi nahi hai.", "error")
    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def dashboard():
    counts = query("""SELECT COUNT(*) total,
      SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) present,
      SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) absent,
      SUM(CASE WHEN status='Late' THEN 1 ELSE 0 END) late
      FROM attendance WHERE attendance_date=%s""", (date.today(),), one=True)
    student_count = query("SELECT COUNT(*) n FROM students WHERE active=1", one=True)["n"]
    recent = query("""SELECT a.attendance_date,s.roll_no,s.full_name,a.status
      FROM attendance a JOIN students s ON s.id=a.student_id
      ORDER BY a.attendance_date DESC,a.updated_at DESC LIMIT 8""")
    return render_template("dashboard.html", counts=counts, student_count=student_count, recent=recent)


@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    if request.method == "POST":
        roll = request.form.get("roll_no", "").strip()
        name = request.form.get("full_name", "").strip()
        klass = request.form.get("class_name", "").strip()
        section = request.form.get("section", "").strip()
        email = request.form.get("email", "").strip() or None
        guardian_name = request.form.get("guardian_name", "").strip() or None
        guardian_email = request.form.get("guardian_email", "").strip() or None
        if not roll or not name or not klass:
            flash("Roll number, name aur class zaroori hain.", "error")
        else:
            try:
                query("""INSERT INTO students(roll_no,full_name,class_name,section,email,guardian_name,guardian_email)
                  VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                  (roll, name, klass, section, email, guardian_name, guardian_email), write=True)
                flash("Student add ho gaya.", "success")
                return redirect(url_for("students"))
            except mysql.connector.IntegrityError:
                flash("Yeh roll number pehle se maujood hai.", "error")
    search = request.args.get("q", "").strip()
    pattern = f"%{search}%"
    rows = query("""SELECT * FROM students WHERE active=1 AND (%s='' OR roll_no LIKE %s OR full_name LIKE %s OR class_name LIKE %s)
      ORDER BY class_name,section,full_name""", (search, pattern, pattern, pattern))
    return render_template("students.html", students=rows, search=search)


@app.route("/students/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def edit_student(sid):
    student = query("SELECT * FROM students WHERE id=%s AND active=1", (sid,), one=True)
    if not student:
        flash("Student nahi mila.", "error")
        return redirect(url_for("students"))
    if request.method == "POST":
        try:
            query("""UPDATE students SET roll_no=%s,full_name=%s,class_name=%s,section=%s,email=%s,
              guardian_name=%s,guardian_email=%s WHERE id=%s""",
                  (request.form["roll_no"].strip(), request.form["full_name"].strip(), request.form["class_name"].strip(),
                   request.form.get("section", "").strip(), request.form.get("email", "").strip() or None,
                   request.form.get("guardian_name", "").strip() or None,
                   request.form.get("guardian_email", "").strip() or None, sid), write=True)
            flash("Student details update ho gayi.", "success")
            return redirect(url_for("students"))
        except mysql.connector.IntegrityError:
            flash("Yeh roll number kisi aur student ka hai.", "error")
    return render_template("student_edit.html", student=student)


@app.post("/students/<int:sid>/delete")
@login_required
def delete_student(sid):
    query("UPDATE students SET active=0 WHERE id=%s", (sid,), write=True)
    flash("Student archive kar diya.", "success")
    return redirect(url_for("students"))


@app.route("/subjects", methods=["GET", "POST"])
@login_required
def subjects():
    if request.method == "POST":
        klass = request.form.get("class_name", "").strip()
        name = request.form.get("subject_name", "").strip()
        teacher = request.form.get("teacher_name", "").strip() or None
        if not klass or not name:
            flash("Class aur subject name zaroori hain.", "error")
        else:
            existing = query("SELECT id,active FROM subjects WHERE class_name=%s AND subject_name=%s", (klass, name), one=True)
            if existing and existing["active"]:
                flash("Yeh subject is class mein pehle se hai.", "error")
            elif existing:
                query("UPDATE subjects SET active=1,teacher_name=%s WHERE id=%s", (teacher, existing["id"]), write=True)
                flash("Archived subject dobara active ho gaya.", "success")
                return redirect(url_for("subjects"))
            else:
                query("INSERT INTO subjects(class_name,subject_name,teacher_name) VALUES(%s,%s,%s)",
                      (klass, name, teacher), write=True)
                flash("Subject add ho gaya.", "success")
                return redirect(url_for("subjects"))
    rows = query("SELECT * FROM subjects WHERE active=1 ORDER BY class_name,subject_name")
    classes = query("SELECT DISTINCT class_name FROM students WHERE active=1 ORDER BY class_name")
    return render_template("subjects.html", subjects=rows, classes=classes)


@app.post("/subjects/<int:subject_id>/archive")
@login_required
def archive_subject(subject_id):
    query("UPDATE subjects SET active=0 WHERE id=%s", (subject_id,), write=True)
    flash("Subject archive ho gaya; purane attendance records safe hain.", "success")
    return redirect(url_for("subjects"))


@app.get("/api/classes")
@login_required
def api_classes():
    return jsonify(query("SELECT DISTINCT class_name FROM students WHERE active=1 ORDER BY class_name"))


@app.get("/api/classes/<class_name>/subjects")
@login_required
def api_class_subjects(class_name):
    return jsonify(query("SELECT id,subject_name,teacher_name FROM subjects WHERE active=1 AND class_name=%s ORDER BY subject_name", (class_name,)))


@app.get("/api/students")
@login_required
def api_students():
    klass = request.args.get("class_name", "")
    return jsonify(query("""SELECT id,roll_no,full_name,class_name,section FROM students
      WHERE active=1 AND (%s='' OR class_name=%s) ORDER BY class_name,section,roll_no""", (klass, klass)))


@app.get("/api/attendance/summary")
@login_required
def api_attendance_summary():
    start = request.args.get("start", date.today().isoformat())
    end = request.args.get("end", start)
    klass = request.args.get("class_name", "")
    subject_id = request.args.get("subject_id", "")
    summary = query("""SELECT COUNT(a.id) marked,
      COALESCE(SUM(a.status='Present'),0) present,
      COALESCE(SUM(a.status='Absent'),0) absent,
      COALESCE(SUM(a.status='Late'),0) late,
      ROUND(100*COALESCE(SUM(a.status='Present'),0)/NULLIF(COUNT(a.id),0),1) attendance_percentage
      FROM attendance a JOIN students s ON s.id=a.student_id
      WHERE s.active=1 AND a.attendance_date BETWEEN %s AND %s
      AND (%s='' OR s.class_name=%s) AND (%s='' OR a.subject_id=%s)""",
      (start, end, klass, klass, subject_id, subject_id or 0), one=True)
    return jsonify(summary)


@app.get("/notifications")
@login_required
def notifications():
    logs = query("""SELECT n.*,s.full_name,s.roll_no FROM notification_logs n
      JOIN students s ON s.id=n.student_id WHERE n.channel='Email' ORDER BY n.created_at DESC LIMIT 50""")
    return render_template("notifications.html", logs=logs)


@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    selected = request.values.get("attendance_date", date.today().isoformat())
    try:
        datetime.strptime(selected, "%Y-%m-%d")
    except ValueError:
        selected = date.today().isoformat()
    klass = request.values.get("class_name", "")
    subject_id = request.values.get("subject_id", "")
    classes = query("SELECT DISTINCT class_name FROM students WHERE active=1 ORDER BY class_name")
    available_subjects = query("SELECT id,subject_name,teacher_name FROM subjects WHERE active=1 AND class_name=%s ORDER BY subject_name", (klass,)) if klass else []
    if request.method == "POST":
        if not klass or not subject_id:
            flash("Attendance mark karne se pehle class aur subject select karo.", "error")
            return redirect(url_for("attendance", attendance_date=selected, class_name=klass))
        valid_subject = query("SELECT id,subject_name FROM subjects WHERE id=%s AND class_name=%s AND active=1", (subject_id, klass), one=True)
        if not valid_subject:
            flash("Selected subject is class ke liye available nahi hai.", "error")
            return redirect(url_for("attendance", attendance_date=selected, class_name=klass))
        ids = request.form.getlist("student_id")
        allowed = {str(s["id"]): s for s in query("""SELECT id,roll_no,full_name,class_name,guardian_name,guardian_email
          FROM students WHERE active=1 AND class_name=%s""", (klass,))}
        changed_absences = []
        saved_count = 0
        conn = db()
        cur = conn.cursor()
        try:
            for sid in ids:
                if sid in allowed:
                    status = request.form.get(f"status_{sid}", "Absent")
                    if status not in ("Present", "Absent", "Late"):
                        status = "Absent"
                    cur.execute("SELECT status FROM attendance WHERE student_id=%s AND subject_id=%s AND attendance_date=%s",
                                (int(sid), int(subject_id), selected))
                    previous = cur.fetchone()
                    cur.execute("""INSERT INTO attendance(student_id,subject_id,attendance_date,status,marked_by) VALUES(%s,%s,%s,%s,%s)
                      ON DUPLICATE KEY UPDATE status=VALUES(status),marked_by=VALUES(marked_by),updated_at=CURRENT_TIMESTAMP""",
                      (int(sid), int(subject_id), selected, status, session["user_id"]))
                    saved_count += 1
                    if status in ("Absent", "Late") and (not previous or previous[0] != status):
                        changed_absences.append(allowed[sid])
            conn.commit()
        finally:
            cur.close(); conn.close()
        attempts = []
        for student in changed_absences:
            attempts.extend(send_guardian_email(student, selected, valid_subject["subject_name"],
                                                 request.form.get(f"status_{student['id']}", "Absent")))
        delivered = sum(1 for attempt in attempts if attempt["sent"])
        failed = sum(1 for attempt in attempts if not attempt["sent"])
        flash(f"{saved_count} students ki attendance save ho gayi.", "success")
        if delivered:
            flash(f"{delivered} guardian notification(s) accepted for delivery.", "success")
        if failed:
            flash(f"{failed} notification(s) fail hue. Notifications page par details dekho.", "warning")
        return redirect(url_for("attendance", attendance_date=selected, class_name=klass, subject_id=subject_id))
    if klass and subject_id:
        sql = """SELECT s.id,s.roll_no,s.full_name,s.class_name,s.section,a.status
          FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.attendance_date=%s AND a.subject_id=%s
          WHERE s.active=1 AND s.class_name=%s ORDER BY s.section,s.roll_no"""
        rows = query(sql, (selected, subject_id, klass))
    else:
        rows = []
    return render_template("attendance.html", students=rows, classes=classes, subjects=available_subjects,
                           selected=selected, selected_class=klass, selected_subject=subject_id)


@app.get("/reports")
@login_required
def reports():
    start = request.args.get("start", date.today().replace(day=1).isoformat())
    end = request.args.get("end", date.today().isoformat())
    sid = request.args.get("student_id", "")
    class_name = request.args.get("class_name", "")
    subject_id = request.args.get("subject_id", "")
    students_list = query("SELECT id,roll_no,full_name FROM students WHERE active=1 ORDER BY full_name")
    classes = query("SELECT DISTINCT class_name FROM students WHERE active=1 ORDER BY class_name")
    subjects_list = query("SELECT id,class_name,subject_name FROM subjects WHERE active=1 ORDER BY class_name,subject_name")
    selected_subject = query("SELECT subject_name FROM subjects WHERE id=%s", (subject_id,), one=True) if subject_id else None
    rows = query("""SELECT s.id,s.roll_no,s.full_name,s.class_name,s.section,
      SUM(a.status='Present') present,SUM(a.status='Absent') absent,SUM(a.status='Late') late,COUNT(a.id) marked,
      ROUND(100*SUM(a.status='Present')/NULLIF(COUNT(a.id),0),1) percentage
      FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.attendance_date BETWEEN %s AND %s AND (%s='' OR a.subject_id=%s)
      WHERE s.active=1 AND (%s='' OR s.id=%s) AND (%s='' OR s.class_name=%s)
      GROUP BY s.id ORDER BY s.class_name,s.roll_no""",
      (start, end, subject_id, subject_id or 0, sid, sid or 0, class_name, class_name))
    low_attendance_count = sum(1 for row in rows if row["percentage"] is not None and row["percentage"] < 75)
    return render_template("reports.html", rows=rows, students=students_list, classes=classes, subjects=subjects_list,
                           start=start, end=end, selected_student=sid, selected_class=class_name,
                           selected_subject=subject_id, selected_subject_name=selected_subject["subject_name"] if selected_subject else "All subjects",
                           low_attendance_count=low_attendance_count)


@app.get("/reports/export")
@login_required
def export_report():
    start = request.args.get("start", date.today().replace(day=1).isoformat())
    end = request.args.get("end", date.today().isoformat())
    sid = request.args.get("student_id", "")
    class_name = request.args.get("class_name", "")
    subject_id = request.args.get("subject_id", "")
    selected_subject = query("SELECT subject_name FROM subjects WHERE id=%s", (subject_id,), one=True) if subject_id else None
    rows = query("""SELECT s.roll_no,s.full_name,s.class_name,s.section,
      SUM(a.status='Present') present,SUM(a.status='Absent') absent,SUM(a.status='Late') late,COUNT(a.id) marked,
      ROUND(100*SUM(a.status='Present')/NULLIF(COUNT(a.id),0),1) percentage
      FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.attendance_date BETWEEN %s AND %s AND (%s='' OR a.subject_id=%s)
      WHERE s.active=1 AND (%s='' OR s.id=%s) AND (%s='' OR s.class_name=%s)
      GROUP BY s.id ORDER BY s.class_name,s.roll_no""", (start, end, subject_id, subject_id or 0, sid, sid or 0, class_name, class_name))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Roll No", "Student", "Class", "Section", "Subject Filter", "Present", "Absent", "Late", "Sessions Marked", "Attendance %", "Alert"])
    for r in rows:
        writer.writerow([r["roll_no"], r["full_name"], r["class_name"], r["section"], selected_subject["subject_name"] if selected_subject else "All subjects", r["present"] or 0,
                         r["absent"] or 0, r["late"] or 0, r["marked"], r["percentage"] or 0,
                         "Below 75%" if r["percentage"] is not None and r["percentage"] < 75 else ""])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=attendance-report.csv"})


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
