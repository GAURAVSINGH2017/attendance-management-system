import csv
import io
import json
import os
import re
import smtplib
import urllib.error
import urllib.request
import unicodedata
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from functools import wraps
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from leave_pdf import build_leave_pdf

load_dotenv()
app = Flask(__name__)
secret_key = os.getenv("SECRET_KEY")
if not secret_key and os.getenv("FLASK_DEBUG", "false").lower() != "true":
    raise RuntimeError("Set SECRET_KEY in the environment before starting the production app.")
app.config["MAX_CONTENT_LENGTH"] = 27 * 1024 * 1024
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
        if session.get("user_role", "teacher") == "student":
            if session.get("must_change_password") and request.endpoint != "student_change_password":
                return redirect(url_for("student_change_password"))
            if request.endpoint not in ("student_attendance", "student_change_password", "student_leave", "student_leave_pdf", "student_leave_document"):
                return redirect(url_for("student_attendance"))
        return fn(*args, **kwargs)
    return wrapped


@app.context_processor
def common_values():
    email_ready = (
        bool(os.getenv("GOOGLE_APPS_SCRIPT_URL") and os.getenv("GOOGLE_APPS_SCRIPT_TOKEN"))
        or bool(os.getenv("RESEND_API_KEY") and os.getenv("RESEND_FROM"))
        or all(os.getenv(key) for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"))
    )
    return {"today": date.today().isoformat(), "current_user": session.get("username"),
            "current_role": session.get("user_role", "teacher"), "email_ready": email_ready}


def record_notification(student_id, attendance_date, subject_name, channel, recipient, status, details=""):
    try:
        query("""INSERT INTO notification_logs(student_id,attendance_date,subject_name,channel,recipient,delivery_status,details)
          VALUES(%s,%s,%s,%s,%s,%s,%s)""",
          (student_id, attendance_date, subject_name, channel, recipient, status, details[:250] or None), write=True)
    except mysql.connector.Error:
        app.logger.exception("Could not save notification delivery log")


def send_attendance_emails(student, attendance_date, subject_name, status):
    results = []
    date_label = datetime.strptime(attendance_date, "%Y-%m-%d").strftime("%d %b %Y")
    recipients = []
    guardian_email = (student.get("guardian_email") or "").strip()
    student_email = (student.get("email") or "").strip()
    if guardian_email:
        recipients.append((guardian_email, student.get("guardian_name") or "Parent/Guardian"))
    if student_email and student_email.casefold() != guardian_email.casefold():
        recipients.append((student_email, student["full_name"]))

    google_script_url = os.getenv("GOOGLE_APPS_SCRIPT_URL")
    google_script_token = os.getenv("GOOGLE_APPS_SCRIPT_TOKEN")
    resend_key = os.getenv("RESEND_API_KEY")
    resend_from = os.getenv("RESEND_FROM")
    smtp_configured = all(os.getenv(key) for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"))

    for email_to, greeting in recipients:
        subject = f"Attendance update: {student['full_name']} marked {status}"
        body = (
            f"Hello {greeting},\n\n"
            f"{student['full_name']} (Roll {student['roll_no']}, Class {student['class_name']}) "
            f"was marked {status} for {subject_name} on {date_label}.\n\nAttendEase"
        )
        try:
            if google_script_url and google_script_token:
                payload = {"token": google_script_token, "to": email_to, "subject": subject, "body": body}
                req = urllib.request.Request(google_script_url, data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=20) as response:
                    response_data = json.loads(response.read().decode("utf-8"))
                if not response_data.get("ok"):
                    raise RuntimeError(response_data.get("error", "Google Apps Script did not confirm the email"))
                details = "Accepted by Google Apps Script; mailbox delivery not confirmed"
            elif resend_key and resend_from:
                payload = {"from": resend_from, "to": [email_to], "subject": subject, "text": body}
                req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(payload).encode("utf-8"),
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=15) as response:
                    response_data = json.loads(response.read().decode("utf-8"))
                details = f"Accepted by Resend; message ID {response_data.get('id', 'unknown')}"
            elif smtp_configured:
                message = EmailMessage()
                message["Subject"] = subject
                message["From"] = os.getenv("SMTP_FROM")
                message["To"] = email_to
                message.set_content(body)
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
                details = "Accepted by SMTP server"
            else:
                continue
            record_notification(student["id"], attendance_date, subject_name, "Email", email_to, "Sent", details)
            results.append({"channel": "Email", "sent": True})
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")[:200]
            provider_error = f"Email provider HTTP {exc.code}: {error_body}"
            record_notification(student["id"], attendance_date, subject_name, "Email", email_to, "Failed", provider_error)
            results.append({"channel": "Email", "sent": False})
        except Exception as exc:
            record_notification(student["id"], attendance_date, subject_name, "Email", email_to, "Failed", str(exc))
            results.append({"channel": "Email", "sent": False})
    return results


@app.get("/login")
def login():
    if session.get("user_id"):
        if session.get("user_role") == "student":
            return redirect(url_for("student_change_password" if session.get("must_change_password") else "student_attendance"))
        return redirect(url_for("dashboard"))
    return render_template("login.html")


def student_name_key(full_name):
    normalized = unicodedata.normalize("NFKD", full_name).encode("ascii", "ignore").decode("ascii").lower()
    key = "".join(character for character in normalized if character.isalnum())
    return key or "student"


def roll_sort_key(roll_no):
    parts = re.split(r"(\d+)", str(roll_no or ""))
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold()) for part in parts)


def format_clock(value):
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    if isinstance(value, timedelta):
        total_minutes = int(value.total_seconds() // 60)
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"
    return str(value or "")[:5]


def create_student_login(cur, student_id, full_name, dob):
    name_key = student_name_key(full_name)
    suffix = dob.strftime("%d%m%y")
    base = f"{name_key[:42]}{suffix}"
    username = base
    duplicate_number = 2
    while True:
        cur.execute("SELECT id FROM users WHERE username=%s", (username,))
        if not cur.fetchone():
            break
        extra = str(duplicate_number)
        username = f"{name_key[:max(1, 49-len(suffix)-len(extra))]}{suffix}{extra}"
        duplicate_number += 1
    initial_password = f"{name_key}@123"
    cur.execute("""INSERT INTO users(username,password_hash,role,student_id,must_change_password)
      VALUES(%s,%s,'student',%s,1)""",
      (username, generate_password_hash(initial_password), student_id))
    return username, initial_password


def authenticate_user(expected_role):
    if session.get("user_id"):
        if session.get("user_role") == "student":
            return redirect(url_for("student_change_password" if session.get("must_change_password") else "student_attendance"))
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = query("SELECT * FROM users WHERE username=%s", (username,), one=True)
        actual_role = user.get("role", "teacher") if user else None
        account_active = True
        if user and actual_role == "student":
            linked_student = query("SELECT id FROM students WHERE id=%s AND active=1", (user.get("student_id"),), one=True)
            account_active = bool(linked_student)
        if (user and actual_role == expected_role and account_active and
                check_password_hash(user["password_hash"], request.form.get("password", ""))):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_role"] = actual_role
            if actual_role == "student":
                session["student_id"] = user["student_id"]
                session["must_change_password"] = bool(user.get("must_change_password"))
            flash("Welcome back!", "success")
            if actual_role == "student":
                return redirect(url_for("student_change_password" if session["must_change_password"] else "student_attendance"))
            return redirect(url_for("dashboard"))
        flash("Username ya password sahi nahi hai.", "error")
    return render_template("login_form.html", login_role=expected_role)


@app.route("/login/teacher", methods=["GET", "POST"])
def teacher_login():
    return authenticate_user("teacher")


@app.route("/login/student", methods=["GET", "POST"])
def student_login():
    return authenticate_user("student")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def dashboard():
    if session.get("user_role") == "student":
        return redirect(url_for("student_attendance"))
    counts = query("""SELECT COUNT(*) total,
      SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) present,
      SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) absent,
      SUM(CASE WHEN status='Late' THEN 1 ELSE 0 END) late
      FROM attendance WHERE attendance_date=%s""", (date.today(),), one=True)
    student_count = query("SELECT COUNT(*) n FROM students WHERE active=1", one=True)["n"]
    recent = query("""SELECT a.attendance_date,s.roll_no,s.full_name,a.status
      FROM attendance a JOIN students s ON s.id=a.student_id
      ORDER BY a.attendance_date DESC,a.updated_at DESC LIMIT 8""")
    low_attendance = query("""SELECT s.roll_no,s.full_name,s.class_name,s.section,
      SUM(a.status='Present') present,COUNT(a.id) marked,
      ROUND(100*SUM(a.status='Present')/NULLIF(COUNT(a.id),0),1) percentage
      FROM students s JOIN attendance a ON a.student_id=s.id
      WHERE s.active=1 GROUP BY s.id
      HAVING percentage < 75
      ORDER BY percentage,s.class_name,s.section,s.roll_no""")
    today_date = date.today()
    today_periods = query("""SELECT t.class_name,t.section,t.period_type,t.lecture_number,
      t.subject_name,t.start_time,t.end_time,t.room,s.id subject_id,
      COALESCE(th.full_name,s.teacher_name) teacher_name
      FROM class_timetable t LEFT JOIN subjects s
        ON s.class_name=t.class_name AND s.subject_name=t.subject_name AND s.active=1
      LEFT JOIN teachers th ON th.id=s.teacher_id
      WHERE t.weekday=%s
      ORDER BY t.start_time,t.class_name,t.section""", (today_date.strftime("%A"),))
    for period in today_periods:
        period["start_label"] = format_clock(period["start_time"])
        period["end_label"] = format_clock(period["end_time"])
    return render_template("dashboard.html", counts=counts, student_count=student_count,
                           recent=recent, low_attendance=low_attendance,
                           today_periods=today_periods, today_date=today_date.isoformat(),
                           today_weekday=today_date.strftime("%A"))


@app.get("/student/attendance")
@login_required
def student_attendance():
    if session.get("user_role") != "student" or not session.get("student_id"):
        return redirect(url_for("dashboard"))
    student = query("SELECT id,roll_no,full_name,class_name,section,date_of_birth FROM students WHERE id=%s AND active=1",
                    (session["student_id"],), one=True)
    if not student:
        session.clear()
        flash("Student account active nahi hai. Teacher se sampark karein.", "error")
        return redirect(url_for("student_login"))
    rows = query("""SELECT a.attendance_date,sub.subject_name,a.status
      FROM attendance a LEFT JOIN subjects sub ON sub.id=a.subject_id
      WHERE a.student_id=%s ORDER BY a.attendance_date DESC,sub.subject_name LIMIT 100""", (student["id"],))
    counts = query("""SELECT COUNT(*) total,
      COALESCE(SUM(status='Present'),0) present,
      COALESCE(SUM(status='Absent'),0) absent,
      COALESCE(SUM(status='Late'),0) late,
      ROUND(100*COALESCE(SUM(status='Present'),0)/NULLIF(COUNT(*),0),1) percentage
      FROM attendance WHERE student_id=%s""", (student["id"],), one=True)
    timetable = query("""SELECT t.weekday,t.period_type,t.lecture_number,t.subject_name,t.start_time,t.end_time,t.room,
        COALESCE(th.full_name,s.teacher_name) teacher_name
      FROM class_timetable t LEFT JOIN subjects s
        ON s.class_name=t.class_name AND s.subject_name=t.subject_name AND s.active=1
      LEFT JOIN teachers th ON th.id=s.teacher_id
      WHERE t.class_name=%s AND t.section=%s
      ORDER BY FIELD(t.weekday,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'),t.start_time""",
      (student["class_name"], student["section"] or ""))
    for period in timetable:
        period["start_label"] = format_clock(period["start_time"])
        period["end_label"] = format_clock(period["end_time"])
    return render_template("student_attendance.html", student=student, rows=rows, counts=counts,
                           timetable=timetable)


@app.route("/student/change-password", methods=["GET", "POST"])
@login_required
def student_change_password():
    if session.get("user_role") != "student":
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(password) < 8:
            flash("Naya password kam se kam 8 characters ka hona chahiye.", "error")
        elif password != confirm:
            flash("Dono password match nahi karte.", "error")
        else:
            query("UPDATE users SET password_hash=%s,must_change_password=0 WHERE id=%s AND role='student'",
                  (generate_password_hash(password), session["user_id"]), write=True)
            session["must_change_password"] = False
            flash("Password update ho gaya.", "success")
            return redirect(url_for("student_attendance"))
    return render_template("student_change_password.html")


@app.route("/teacher/change-password", methods=["GET", "POST"])
@login_required
def teacher_change_password():
    if session.get("user_role", "teacher") != "teacher":
        return redirect(url_for("student_attendance"))
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        user = query("SELECT password_hash FROM users WHERE id=%s AND role='teacher'",
                     (session["user_id"],), one=True)
        if not user or not check_password_hash(user["password_hash"], current_password):
            flash("Current password sahi nahi hai.", "error")
        elif len(new_password) < 8:
            flash("Naya password kam se kam 8 characters ka hona chahiye.", "error")
        elif new_password != confirm:
            flash("Dono new password match nahi karte.", "error")
        else:
            query("UPDATE users SET password_hash=%s WHERE id=%s AND role='teacher'",
                  (generate_password_hash(new_password), session["user_id"]), write=True)
            flash("Teacher password update ho gaya.", "success")
            return redirect(url_for("dashboard"))
    return render_template("teacher_change_password.html")


@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    if request.method == "POST":
        roll = request.form.get("roll_no", "").strip()
        name = request.form.get("full_name", "").strip()
        klass = request.form.get("class_name", "").strip()
        section = request.form.get("section", "").strip()
        email = request.form.get("email", "").strip() or None
        dob_text = request.form.get("date_of_birth", "").strip()
        guardian_name = request.form.get("guardian_name", "").strip() or None
        guardian_email = request.form.get("guardian_email", "").strip() or None
        try:
            dob = date.fromisoformat(dob_text)
        except ValueError:
            dob = None
        if not roll or not name or not klass or not dob:
            flash("Roll number, name, class aur valid date of birth zaroori hain.", "error")
        elif dob > date.today():
            flash("Date of birth future mein nahi ho sakti.", "error")
        else:
            conn = db()
            cur = conn.cursor()
            try:
                cur.execute("""INSERT INTO students(roll_no,full_name,class_name,section,date_of_birth,email,guardian_name,guardian_email)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (roll, name, klass, section, dob, email, guardian_name, guardian_email))
                student_id = cur.lastrowid
                username, initial_password = create_student_login(cur, student_id, name, dob)
                conn.commit()
                flash(f"Student add hua. Student login: {username} · Pehla password: {initial_password}. Student pehli login par password badlega.", "success")
                return redirect(url_for("students"))
            except mysql.connector.IntegrityError:
                conn.rollback()
                flash("Yeh roll number pehle se maujood hai.", "error")
            finally:
                cur.close()
                conn.close()
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
    student_login = query("SELECT id,username FROM users WHERE student_id=%s", (sid,), one=True)
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        dob_text = request.form.get("date_of_birth", "").strip()
        try:
            dob = date.fromisoformat(dob_text)
        except ValueError:
            dob = None
        if not full_name or not dob:
            flash("Student ka naam aur valid date of birth zaroori hain.", "error")
            return render_template("student_edit.html", student=student, student_login=student_login)
        if dob > date.today():
            flash("Date of birth future mein nahi ho sakti.", "error")
            return render_template("student_edit.html", student=student, student_login=student_login)
        try:
            conn = db()
            cur = conn.cursor()
            try:
                cur.execute("""UPDATE students SET roll_no=%s,full_name=%s,class_name=%s,section=%s,date_of_birth=%s,email=%s,
                  guardian_name=%s,guardian_email=%s WHERE id=%s""",
                    (request.form["roll_no"].strip(), full_name, request.form["class_name"].strip(),
                     request.form.get("section", "").strip(), dob,
                     request.form.get("email", "").strip() or None,
                     request.form.get("guardian_name", "").strip() or None,
                     request.form.get("guardian_email", "").strip() or None, sid))
                created_login = None
                if not student_login:
                    created_login = create_student_login(cur, sid, full_name, dob)
                elif request.form.get("reset_student_password") == "yes":
                    reset_password = f"{student_name_key(full_name)}@123"
                    cur.execute("UPDATE users SET password_hash=%s,must_change_password=1 WHERE id=%s",
                                (generate_password_hash(reset_password), student_login["id"]))
                    created_login = (student_login["username"], reset_password)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()
            if created_login:
                flash(f"Student details update ho gayi. Student login: {created_login[0]} · Pehla password: {created_login[1]}. Student pehli login par password badlega.", "success")
            else:
                flash("Student details update ho gayi.", "success")
            return redirect(url_for("students"))
        except mysql.connector.IntegrityError:
            flash("Yeh roll number ya login username kisi aur account mein use ho raha hai.", "error")
            student_login = query("SELECT id,username FROM users WHERE student_id=%s", (sid,), one=True)
    return render_template("student_edit.html", student=student, student_login=student_login)


@app.post("/students/<int:sid>/delete")
@login_required
def delete_student(sid):
    query("UPDATE students SET active=0 WHERE id=%s", (sid,), write=True)
    flash("Student archive kar diya.", "success")
    return redirect(url_for("students"))


@app.route("/classes", methods=["GET", "POST"])
@login_required
def classes():
    if request.method == "POST":
        class_name = request.form.get("class_name", "").strip()
        section = request.form.get("section", "").strip()
        try:
            count = int(request.form.get("student_count", "0"))
        except ValueError:
            count = 0
        if not class_name or not section or not 1 <= count <= 60:
            flash("Class, section aur 1 se 60 tak students ki sankhya bharo.", "error")
        else:
            session["bulk_class_setup"] = {"class_name": class_name, "section": section, "count": count}
            return redirect(url_for("bulk_add_students"))
    groups = query("""SELECT class_name,COALESCE(section,'') section,COUNT(*) student_count
      FROM students WHERE active=1 GROUP BY class_name,COALESCE(section,'') ORDER BY class_name,section""")
    return render_template("classes.html", classes=groups,
        class_name_value=request.args.get("class_name", ""), section_value=request.args.get("section", ""))


@app.route("/classes/add-students", methods=["GET", "POST"])
@login_required
def bulk_add_students():
    setup = session.get("bulk_class_setup")
    if not setup:
        flash("Pehle class aur section ki jankari bharo.", "error")
        return redirect(url_for("classes"))
    if request.method == "POST":
        new_students = []
        errors = []
        for index in range(setup["count"]):
            prefix = f"student_{index}_"
            row = {key: request.form.get(prefix + key, "").strip() for key in
                   ("roll_no", "full_name", "date_of_birth", "email", "guardian_name", "guardian_email")}
            try:
                dob = date.fromisoformat(row["date_of_birth"])
            except ValueError:
                dob = None
            if not row["roll_no"] or not row["full_name"] or not dob:
                errors.append(f"Student {index + 1}: roll number, name aur DOB zaroori hain.")
            elif dob > date.today():
                errors.append(f"Student {index + 1}: DOB future mein nahi ho sakti.")
            row["dob"] = dob
            new_students.append(row)
        if errors:
            for message in errors[:5]:
                flash(message, "error")
        else:
            conn = db()
            cur = conn.cursor()
            credentials = []
            try:
                for row in new_students:
                    cur.execute("""INSERT INTO students(roll_no,full_name,class_name,section,date_of_birth,email,guardian_name,guardian_email)
                      VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                      (row["roll_no"], row["full_name"], setup["class_name"], setup["section"], row["dob"],
                       row["email"] or None, row["guardian_name"] or None, row["guardian_email"] or None))
                    username, initial_password = create_student_login(cur, cur.lastrowid, row["full_name"], row["dob"])
                    credentials.append({"full_name": row["full_name"], "roll_no": row["roll_no"],
                                        "username": username, "initial_password": initial_password})
                conn.commit()
                session.pop("bulk_class_setup", None)
                return render_template("class_added.html", class_name=setup["class_name"],
                                       section=setup["section"], credentials=credentials)
            except mysql.connector.IntegrityError:
                conn.rollback()
                flash("Kisi student ka roll number pehle se use ho raha hai. Roll numbers check karke dobara save karo.", "error")
            finally:
                cur.close()
                conn.close()
    return render_template("bulk_add_students.html", setup=setup, student_slots=range(setup["count"]))


@app.get("/classes/detail")
@login_required
def class_detail():
    class_name = request.args.get("class_name", "").strip()
    section_arg = request.args.get("section")
    section = (section_arg or "").strip()
    if not class_name or section_arg is None:
        return redirect(url_for("classes"))
    rows = query("""SELECT s.id,s.roll_no,s.full_name,s.class_name,s.section,s.date_of_birth,s.email,
      u.username,u.must_change_password FROM students s LEFT JOIN users u ON u.student_id=s.id
      WHERE s.active=1 AND s.class_name=%s AND COALESCE(s.section,'')=%s ORDER BY s.roll_no""", (class_name, section))
    rows.sort(key=lambda row: roll_sort_key(row["roll_no"]))
    for row in rows:
        row["initial_password"] = f"{student_name_key(row['full_name'])}@123" if row.get("must_change_password") else None
    subjects = query("""SELECT s.subject_name,COALESCE(t.full_name,s.teacher_name) teacher_name
      FROM subjects s LEFT JOIN teachers t ON t.id=s.teacher_id
      WHERE s.class_name=%s AND s.active=1 ORDER BY s.subject_name""", (class_name,))
    timetable = query("""SELECT t.id,t.weekday,t.period_type,t.lecture_number,t.subject_name,t.start_time,t.end_time,t.room,
        COALESCE(th.full_name,s.teacher_name) teacher_name
      FROM class_timetable t LEFT JOIN subjects s
        ON s.class_name=t.class_name AND s.subject_name=t.subject_name AND s.active=1
      LEFT JOIN teachers th ON th.id=s.teacher_id
      WHERE t.class_name=%s AND t.section=%s
      ORDER BY FIELD(t.weekday,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'),t.start_time""",
      (class_name, section))
    for period in timetable:
        period["start_label"] = format_clock(period["start_time"])
        period["end_label"] = format_clock(period["end_time"])
    return render_template("class_detail.html", class_name=class_name, section=section,
                           students=rows, subjects=subjects, timetable=timetable)


@app.route("/teachers", methods=["GET", "POST"])
@login_required
def teachers():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip() or None
        if not full_name:
            flash("Teacher ka naam zaroori hai.", "error")
        else:
            try:
                query("INSERT INTO teachers(full_name,email) VALUES(%s,%s)",
                      (full_name, email), write=True)
                flash("Teacher add ho gaya. Ab Subjects section mein unke subjects assign karo.", "success")
                return redirect(url_for("teachers"))
            except mysql.connector.IntegrityError:
                flash("Is naam ka teacher pehle se maujood hai.", "error")
    rows = query("SELECT id,full_name,email FROM teachers WHERE active=1 ORDER BY full_name")
    return render_template("teachers.html", teachers=rows)


@app.get("/timetable")
@login_required
def timetable():
    groups = query("""SELECT s.class_name,COALESCE(s.section,'') section,COUNT(DISTINCT s.id) student_count,
      COUNT(t.id) period_count FROM students s LEFT JOIN class_timetable t
      ON t.class_name=s.class_name AND t.section=COALESCE(s.section,'')
      WHERE s.active=1 GROUP BY s.class_name,COALESCE(s.section,'') ORDER BY s.class_name,section""")
    return render_template("timetable.html", classes=groups)


@app.post("/classes/timetable/add")
@login_required
def add_timetable_period():
    class_name = request.form.get("class_name", "").strip()
    section = request.form.get("section", "").strip()
    weekday = request.form.get("weekday", "").strip()
    period_type = request.form.get("period_type", "lecture").strip()
    subject_name = request.form.get("subject_name", "").strip() or None
    lecture_number_text = request.form.get("lecture_number", "").strip()
    start_text = request.form.get("start_time", "").strip()
    end_text = request.form.get("end_time", "").strip()
    room = request.form.get("room", "").strip() or None
    days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
    try:
        start_time = datetime.strptime(start_text, "%H:%M").time()
        end_time = datetime.strptime(end_text, "%H:%M").time()
    except ValueError:
        start_time = end_time = None
    subject = query("SELECT id FROM subjects WHERE class_name=%s AND subject_name=%s AND active=1",
                    (class_name, subject_name), one=True) if class_name and subject_name else None
    try:
        lecture_number = int(lecture_number_text) if lecture_number_text else None
    except ValueError:
        lecture_number = None
    valid_period = (period_type == "lunch" or
                    (period_type == "lecture" and subject and lecture_number is not None and 1 <= lecture_number <= 20))
    if not class_name or weekday not in days or not valid_period or not start_time or not end_time:
        flash("Class, day, valid times aur lecture ke liye subject + lecture number (1–20) select karo.", "error")
    elif start_time >= end_time:
        flash("End time start time ke baad hona chahiye.", "error")
    else:
        overlap = query("""SELECT id FROM class_timetable
          WHERE class_name=%s AND section=%s AND weekday=%s AND start_time < %s AND end_time > %s LIMIT 1""",
          (class_name, section, weekday, end_time, start_time), one=True)
        if overlap:
            flash("Is time par isi class-section ka doosra lecture pehle se scheduled hai.", "error")
        else:
            try:
                query("""INSERT INTO class_timetable(class_name,section,weekday,period_type,lecture_number,subject_name,start_time,end_time,room)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (class_name, section, weekday, period_type, lecture_number if period_type == "lecture" else None,
                   subject_name if period_type == "lecture" else None,
                   start_time, end_time, room), write=True)
                flash("Lunch break timetable mein add ho gaya." if period_type == "lunch" else "Lecture timetable mein add ho gaya.", "success")
            except mysql.connector.IntegrityError:
                flash("Is time ka period pehle se maujood hai.", "error")
    return redirect(url_for("class_detail", class_name=class_name, section=section))


@app.post("/classes/timetable/<int:period_id>/delete")
@login_required
def delete_timetable_period(period_id):
    class_name = request.form.get("class_name", "").strip()
    section = request.form.get("section", "").strip()
    query("DELETE FROM class_timetable WHERE id=%s AND class_name=%s AND section=%s",
          (period_id, class_name, section), write=True)
    flash("Timetable period delete ho gaya.", "success")
    return redirect(url_for("class_detail", class_name=class_name, section=section))


@app.route("/subjects", methods=["GET", "POST"])
@login_required
def subjects():
    if request.method == "POST":
        klass = request.form.get("class_name", "").strip()
        name = request.form.get("subject_name", "").strip()
        try:
            teacher_id = int(request.form.get("teacher_id", "0"))
        except ValueError:
            teacher_id = 0
        teacher = query("SELECT id,full_name FROM teachers WHERE id=%s AND active=1", (teacher_id,), one=True) if teacher_id else None
        if not klass or not name or not teacher:
            flash("Class, subject aur assigned teacher select karo.", "error")
        else:
            existing = query("SELECT id,active FROM subjects WHERE class_name=%s AND subject_name=%s", (klass, name), one=True)
            if existing and existing["active"]:
                flash("Yeh subject is class mein pehle se hai.", "error")
            elif existing:
                query("UPDATE subjects SET active=1,teacher_id=%s,teacher_name=%s WHERE id=%s",
                      (teacher["id"], teacher["full_name"], existing["id"]), write=True)
                flash("Archived subject dobara active ho gaya.", "success")
                return redirect(url_for("subjects"))
            else:
                query("INSERT INTO subjects(class_name,subject_name,teacher_id,teacher_name) VALUES(%s,%s,%s,%s)",
                      (klass, name, teacher["id"], teacher["full_name"]), write=True)
                flash("Subject add ho gaya.", "success")
                return redirect(url_for("subjects"))
    rows = query("""SELECT s.*,COALESCE(t.full_name,s.teacher_name) assigned_teacher
      FROM subjects s LEFT JOIN teachers t ON t.id=s.teacher_id
      WHERE s.active=1 ORDER BY s.class_name,s.subject_name""")
    classes = query("SELECT DISTINCT class_name FROM students WHERE active=1 ORDER BY class_name")
    teachers_list = query("SELECT id,full_name FROM teachers WHERE active=1 ORDER BY full_name")
    return render_template("subjects.html", subjects=rows, classes=classes, teachers=teachers_list)


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
    return jsonify(query("""SELECT s.id,s.subject_name,COALESCE(t.full_name,s.teacher_name) teacher_name
      FROM subjects s LEFT JOIN teachers t ON t.id=s.teacher_id
      WHERE s.active=1 AND s.class_name=%s ORDER BY s.subject_name""", (class_name,)))


@app.get("/api/classes/<class_name>/sections")
@login_required
def api_class_sections(class_name):
    return jsonify(query("""SELECT DISTINCT COALESCE(section,'') section FROM students
      WHERE active=1 AND class_name=%s ORDER BY section""", (class_name,)))


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
    selected_section_value = request.values.get("section", "")
    subject_id = request.values.get("subject_id", "")
    classes = query("SELECT DISTINCT class_name FROM students WHERE active=1 ORDER BY class_name")
    sections = query("""SELECT DISTINCT COALESCE(section,'') section FROM students
      WHERE active=1 AND class_name=%s ORDER BY section""", (klass,)) if klass else []
    if request.method == "GET" and klass and not selected_section_value:
        if len(sections) == 1:
            selected_section_value = sections[0]["section"] or "__blank__"
        elif len(sections) > 1:
            selected_section_value = "__choose__"
    section = "" if selected_section_value == "__blank__" else selected_section_value
    available_subjects = query("SELECT id,subject_name,teacher_name FROM subjects WHERE active=1 AND class_name=%s ORDER BY subject_name", (klass,)) if klass else []
    if request.method == "POST":
        valid_section_values = {s["section"] or "__blank__" for s in sections}
        if not klass or selected_section_value not in valid_section_values or not subject_id:
            flash("Attendance se pehle class, section aur subject select karo.", "error")
            return redirect(url_for("attendance", attendance_date=selected, class_name=klass))
        valid_subject = query("SELECT id,subject_name FROM subjects WHERE id=%s AND class_name=%s AND active=1", (subject_id, klass), one=True)
        if not valid_subject:
            flash("Selected subject is class ke liye available nahi hai.", "error")
            return redirect(url_for("attendance", attendance_date=selected, class_name=klass, section=selected_section_value))
        ids = request.form.getlist("student_id")
        allowed = {str(s["id"]): s for s in query("""SELECT id,roll_no,full_name,class_name,email,guardian_name,guardian_email
          FROM students WHERE active=1 AND class_name=%s AND COALESCE(section,'')=%s""", (klass, section))}
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
                    if not previous or previous[0] != status:
                        cur.execute("""INSERT INTO attendance_audit_log
                          (student_id,subject_id,attendance_date,previous_status,new_status,changed_by)
                          VALUES(%s,%s,%s,%s,%s,%s)""",
                          (int(sid), int(subject_id), selected, previous[0] if previous else None,
                           status, session["user_id"]))
                    saved_count += 1
                    if status in ("Absent", "Late") and (not previous or previous[0] != status):
                        changed_absences.append(allowed[sid])
            conn.commit()
        finally:
            cur.close(); conn.close()
        attempts = []
        for student in changed_absences:
            attempts.extend(send_attendance_emails(
                student, selected, valid_subject["subject_name"],
                request.form.get(f"status_{student['id']}", "Absent")))
        delivered = sum(1 for attempt in attempts if attempt["sent"])
        failed = sum(1 for attempt in attempts if not attempt["sent"])
        flash(f"{saved_count} students ki attendance save ho gayi.", "success")
        if delivered:
            flash(f"{delivered} email notification(s) accepted for delivery.", "success")
        if failed:
            flash(f"{failed} notification(s) fail hue. Notifications page par details dekho.", "warning")
        return redirect(url_for("attendance", attendance_date=selected, class_name=klass,
                                section=selected_section_value, subject_id=subject_id))
    if klass and subject_id and selected_section_value not in ("", "__choose__"):
        sql = """SELECT s.id,s.roll_no,s.full_name,s.class_name,s.section,a.status
          FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.attendance_date=%s AND a.subject_id=%s
          WHERE s.active=1 AND s.class_name=%s AND COALESCE(s.section,'')=%s ORDER BY s.roll_no"""
        rows = query(sql, (selected, subject_id, klass, section))
        rows.sort(key=lambda row: roll_sort_key(row["roll_no"]))
    else:
        rows = []
    return render_template("attendance.html", students=rows, classes=classes, subjects=available_subjects,
                           selected=selected, selected_class=klass, selected_section=section,
                           selected_section_value=selected_section_value,
                           selected_subject=subject_id, sections=sections)


@app.get("/attendance/history")
@login_required
def attendance_history():
    rows = query("""SELECT h.attendance_date,h.previous_status,h.new_status,h.changed_at,
      s.roll_no,s.full_name,s.class_name,s.section,sub.subject_name,u.username changed_by
      FROM attendance_audit_log h
      JOIN students s ON s.id=h.student_id
      JOIN subjects sub ON sub.id=h.subject_id
      JOIN users u ON u.id=h.changed_by
      ORDER BY h.changed_at DESC,h.id DESC LIMIT 200""")
    return render_template("attendance_history.html", history=rows)


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



# ---------- Leave applications ----------
LEAVE_TYPES = ["Sick leave", "Casual leave", "Emergency", "Family function", "Other"]
LEAVE_EXTENSIONS = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
LEAVE_MAX_FILES = 5
LEAVE_MAX_FILE_BYTES = 5 * 1024 * 1024


def leave_file_is_valid(ext, data):
    if ext == ".pdf":
        return data[:4] == b"%PDF"
    if ext == ".png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    return data[:3] == b"\xff\xd8\xff"


def current_student():
    if session.get("user_role") != "student" or not session.get("student_id"):
        return None
    return query("""SELECT id,roll_no,full_name,class_name,section,date_of_birth,guardian_name
        FROM students WHERE id=%s AND active=1""", (session["student_id"],), one=True)


LEAVE_SELECT = """SELECT l.*, s.full_name, s.roll_no, s.class_name, s.section,
    s.date_of_birth, s.guardian_name
    FROM leave_applications l JOIN students s ON s.id=l.student_id"""


def load_leave(leave_id, student_id=None):
    sql = LEAVE_SELECT + " WHERE l.id=%s"
    params = [leave_id]
    if student_id is not None:
        sql += " AND l.student_id=%s"
        params.append(student_id)
    leave = query(sql, tuple(params), one=True)
    if not leave:
        abort(404)
    return leave


def leave_documents_for(leave_id):
    return query("SELECT id,filename,file_size FROM leave_documents WHERE leave_id=%s ORDER BY id", (leave_id,))


def send_leave_document(leave_id, doc_id, student_id=None):
    sql = """SELECT d.filename,d.mime_type,d.file_data FROM leave_documents d
        JOIN leave_applications l ON l.id=d.leave_id WHERE d.id=%s AND d.leave_id=%s"""
    params = [doc_id, leave_id]
    if student_id is not None:
        sql += " AND l.student_id=%s"
        params.append(student_id)
    doc = query(sql, tuple(params), one=True)
    if not doc:
        abort(404)
    safe_name = doc["filename"].replace('"', "")
    return Response(bytes(doc["file_data"]), mimetype=doc["mime_type"],
                    headers={"Content-Disposition": f'inline; filename="{safe_name}"'})


@app.route("/student/leave", methods=["GET", "POST"])
@login_required
def student_leave():
    student = current_student()
    if not student:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        leave_type = request.form.get("leave_type", "").strip()
        reason = request.form.get("reason", "").strip()
        try:
            from_date = datetime.strptime(request.form.get("from_date", ""), "%Y-%m-%d").date()
            to_date = datetime.strptime(request.form.get("to_date", ""), "%Y-%m-%d").date()
        except ValueError:
            from_date = to_date = None
        files = [f for f in request.files.getlist("documents") if f and f.filename]
        prepared, error = [], None
        if leave_type not in LEAVE_TYPES:
            error = "Leave type chuniye."
        elif not from_date or not to_date or to_date < from_date:
            error = "Sahi from date aur to date chuniye (to date from date ke same ya baad ki honi chahiye)."
        elif len(reason) < 10:
            error = "Reason kam se kam 10 characters ka likhiye."
        elif len(files) > LEAVE_MAX_FILES:
            error = f"Maximum {LEAVE_MAX_FILES} documents upload kar sakte hain."
        else:
            for f in files:
                ext = os.path.splitext(f.filename)[1].lower()
                data = f.read()
                if ext not in LEAVE_EXTENSIONS or not leave_file_is_valid(ext, data):
                    error = "Sirf PDF, JPG, JPEG ya PNG files upload karein."
                    break
                if len(data) > LEAVE_MAX_FILE_BYTES:
                    error = "Har document 5 MB se chhota hona chahiye."
                    break
                prepared.append((os.path.basename(f.filename)[:200], LEAVE_EXTENSIONS[ext], data))
        if error:
            flash(error, "error")
        else:
            conn = db()
            cur = conn.cursor()
            try:
                cur.execute("""INSERT INTO leave_applications(student_id,leave_type,from_date,to_date,reason)
                    VALUES(%s,%s,%s,%s,%s)""", (student["id"], leave_type, from_date, to_date, reason))
                leave_id = cur.lastrowid
                for name, mime, data in prepared:
                    cur.execute("""INSERT INTO leave_documents(leave_id,filename,mime_type,file_size,file_data)
                        VALUES(%s,%s,%s,%s,%s)""", (leave_id, name, mime, len(data), data))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()
            flash("Leave application submit ho gayi. Teacher ki approval ka intezaar karein.", "success")
            return redirect(url_for("student_leave"))
    applications = query("""SELECT l.id,l.leave_type,l.from_date,l.to_date,l.reason,l.status,
        l.teacher_remark,l.created_at,
        (SELECT COUNT(*) FROM leave_documents d WHERE d.leave_id=l.id) doc_count
        FROM leave_applications l WHERE l.student_id=%s ORDER BY l.created_at DESC""", (student["id"],))
    return render_template("student_leave.html", student=student, leave_types=LEAVE_TYPES,
                           applications=applications, max_files=LEAVE_MAX_FILES)


def leave_pdf_response(leave):
    pdf = build_leave_pdf(leave, leave_documents_for(leave["id"]))
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="leave-application-{leave["id"]}.pdf"'})


@app.get("/student/leave/<int:leave_id>/pdf")
@login_required
def student_leave_pdf(leave_id):
    student = current_student()
    if not student:
        return redirect(url_for("dashboard"))
    return leave_pdf_response(load_leave(leave_id, student["id"]))


@app.get("/student/leave/<int:leave_id>/documents/<int:doc_id>")
@login_required
def student_leave_document(leave_id, doc_id):
    student = current_student()
    if not student:
        abort(403)
    return send_leave_document(leave_id, doc_id, student["id"])


@app.get("/leaves")
@login_required
def leave_requests():
    status = request.args.get("status", "Pending")
    if status not in ("Pending", "Approved", "Rejected", "All"):
        status = "Pending"
    where, params = ("", ()) if status == "All" else ("WHERE l.status=%s", (status,))
    rows = query(f"""SELECT l.id,l.leave_type,l.from_date,l.to_date,l.status,l.created_at,
        s.full_name,s.roll_no,s.class_name,s.section,
        (SELECT COUNT(*) FROM leave_documents d WHERE d.leave_id=l.id) doc_count
        FROM leave_applications l JOIN students s ON s.id=l.student_id {where}
        ORDER BY l.created_at DESC""", params)
    return render_template("leave_requests.html", rows=rows, status=status)


@app.route("/leaves/<int:leave_id>", methods=["GET", "POST"])
@login_required
def leave_detail(leave_id):
    leave = load_leave(leave_id)
    if request.method == "POST":
        decision = request.form.get("decision", "")
        remark = request.form.get("teacher_remark", "").strip()[:500]
        if decision not in ("Approved", "Rejected"):
            flash("Approve ya Reject chuniye.", "error")
        else:
            query("""UPDATE leave_applications SET status=%s,teacher_remark=%s,decided_by=%s,decided_at=NOW()
                WHERE id=%s""", (decision, remark or None, session.get("username"), leave_id), write=True)
            flash(f"Leave application {decision.lower()} ho gayi.", "success")
        return redirect(url_for("leave_detail", leave_id=leave_id))
    return render_template("leave_detail.html", leave=leave, documents=leave_documents_for(leave_id))


@app.get("/leaves/<int:leave_id>/pdf")
@login_required
def leave_pdf(leave_id):
    return leave_pdf_response(load_leave(leave_id))


@app.get("/leaves/<int:leave_id>/documents/<int:doc_id>")
@login_required
def leave_document(leave_id, doc_id):
    return send_leave_document(leave_id, doc_id)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
