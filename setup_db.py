"""Create or safely upgrade the Attendance Management System schema."""
import os
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()
db_name = os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE", "attendance_db")
db_options = dict(
    host=os.getenv("DB_HOST") or os.getenv("MYSQLHOST", "localhost"),
    port=int(os.getenv("DB_PORT") or os.getenv("MYSQLPORT", "3306")),
    user=os.getenv("DB_USER") or os.getenv("MYSQLUSER", "root"),
    password=os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD", ""),
    database=db_name,
)
if os.getenv("DB_SSL_CA"):
    db_options.update(ssl_ca=os.getenv("DB_SSL_CA"), ssl_verify_cert=True, ssl_verify_identity=True)
conn = mysql.connector.connect(**db_options)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'teacher',
  student_id INT NULL,
  must_change_password TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS students (
  id INT AUTO_INCREMENT PRIMARY KEY,
  roll_no VARCHAR(30) NOT NULL UNIQUE,
  full_name VARCHAR(120) NOT NULL,
  class_name VARCHAR(50) NOT NULL,
  section VARCHAR(20) DEFAULT '',
  date_of_birth DATE NULL,
  email VARCHAR(120),
  guardian_name VARCHAR(120),
  guardian_email VARCHAR(120),
  guardian_phone VARCHAR(30),
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS teachers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(120) NOT NULL UNIQUE,
  email VARCHAR(120) DEFAULT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS subjects (
  id INT AUTO_INCREMENT PRIMARY KEY,
  class_name VARCHAR(50) NOT NULL,
  subject_name VARCHAR(80) NOT NULL,
  teacher_id INT NULL,
  teacher_name VARCHAR(120) DEFAULT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY unique_class_subject (class_name, subject_name)
)""")
cur.execute("SHOW COLUMNS FROM subjects LIKE 'teacher_id'")
if not cur.fetchone():
    cur.execute("ALTER TABLE subjects ADD COLUMN teacher_id INT NULL AFTER subject_name")
cur.execute("""SELECT COUNT(*) FROM information_schema.table_constraints
  WHERE constraint_schema=%s AND table_name='subjects' AND constraint_name='fk_subject_teacher'""", (db_name,))
if not cur.fetchone()[0]:
    cur.execute("ALTER TABLE subjects ADD CONSTRAINT fk_subject_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL")
cur.execute("""CREATE TABLE IF NOT EXISTS class_timetable (
  id INT AUTO_INCREMENT PRIMARY KEY,
  class_name VARCHAR(50) NOT NULL,
  section VARCHAR(20) NOT NULL DEFAULT '',
  weekday ENUM('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday') NOT NULL,
  period_type ENUM('lecture','lunch') NOT NULL DEFAULT 'lecture',
  lecture_number INT DEFAULT NULL,
  subject_name VARCHAR(80) DEFAULT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  room VARCHAR(40) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY unique_class_period (class_name,section,weekday,start_time)
)""")
cur.execute("SHOW COLUMNS FROM class_timetable LIKE 'lecture_number'")
if not cur.fetchone():
    cur.execute("ALTER TABLE class_timetable ADD COLUMN lecture_number INT NULL AFTER period_type")
cur.execute("""SELECT id,class_name,section,weekday,start_time FROM class_timetable
  WHERE period_type='lecture' AND lecture_number IS NULL
  ORDER BY class_name,section,weekday,start_time""")
lecture_rows = cur.fetchall()
lecture_counters = {}
for row_id, class_name, section, weekday, _start_time in lecture_rows:
    key = (class_name, section, weekday)
    lecture_counters[key] = lecture_counters.get(key, 0) + 1
    cur.execute("UPDATE class_timetable SET lecture_number=%s WHERE id=%s",
                (lecture_counters[key], row_id))
cur.execute("""SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema=%s AND table_name='class_timetable' AND index_name='unique_class_lecture_number'""", (db_name,))
if not cur.fetchone()[0]:
    cur.execute("ALTER TABLE class_timetable ADD UNIQUE KEY unique_class_lecture_number (class_name,section,weekday,lecture_number)")

# Add role-based accounts to older databases without changing existing teacher logins.
for column_name, column_type in (("role", "VARCHAR(20) NOT NULL DEFAULT 'teacher'"),
                                 ("student_id", "INT NULL"),
                                 ("must_change_password", "TINYINT(1) NOT NULL DEFAULT 0")):
    cur.execute("SHOW COLUMNS FROM users LIKE %s", (column_name,))
    if not cur.fetchone():
        cur.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
cur.execute("""SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema=%s AND table_name='users' AND index_name='unique_student_login'""", (db_name,))
if not cur.fetchone()[0]:
    cur.execute("ALTER TABLE users ADD UNIQUE KEY unique_student_login (student_id)")
cur.execute("""SELECT COUNT(*) FROM information_schema.table_constraints
  WHERE constraint_schema=%s AND table_name='users' AND constraint_name='fk_users_student'""", (db_name,))
if not cur.fetchone()[0]:
    cur.execute("ALTER TABLE users ADD CONSTRAINT fk_users_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL")
cur.execute("SHOW COLUMNS FROM students LIKE 'date_of_birth'")
if not cur.fetchone():
    cur.execute("ALTER TABLE students ADD COLUMN date_of_birth DATE NULL AFTER section")
cur.execute("""CREATE TABLE IF NOT EXISTS attendance (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL,
  subject_id INT NULL,
  attendance_date DATE NOT NULL,
  status ENUM('Present','Absent','Late') NOT NULL DEFAULT 'Absent',
  marked_by INT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY one_record_per_student_date_subject (student_id, attendance_date, subject_id),
  FOREIGN KEY (student_id) REFERENCES students(id),
  CONSTRAINT fk_attendance_subject FOREIGN KEY (subject_id) REFERENCES subjects(id),
  FOREIGN KEY (marked_by) REFERENCES users(id)
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS attendance_audit_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL,
  subject_id INT NOT NULL,
  attendance_date DATE NOT NULL,
  previous_status ENUM('Present','Absent','Late') DEFAULT NULL,
  new_status ENUM('Present','Absent','Late') NOT NULL,
  changed_by INT NOT NULL,
  changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_attendance_audit_changed_at (changed_at),
  INDEX idx_attendance_audit_student_date (student_id,attendance_date),
  FOREIGN KEY (student_id) REFERENCES students(id),
  FOREIGN KEY (subject_id) REFERENCES subjects(id),
  FOREIGN KEY (changed_by) REFERENCES users(id)
)""")

for column_name, column_type in (("guardian_name", "VARCHAR(120) NULL"),
                                 ("guardian_email", "VARCHAR(120) NULL"),
                                 ("guardian_phone", "VARCHAR(30) NULL")):
    cur.execute("SHOW COLUMNS FROM students LIKE %s", (column_name,))
    if not cur.fetchone():
        cur.execute(f"ALTER TABLE students ADD COLUMN {column_name} {column_type}")

cur.execute("""CREATE TABLE IF NOT EXISTS notification_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL,
  attendance_date DATE NOT NULL,
  subject_name VARCHAR(80) NOT NULL,
  channel ENUM('Email','SMS') NOT NULL,
  recipient VARCHAR(255) NOT NULL,
  delivery_status ENUM('Sent','Failed') NOT NULL,
  details VARCHAR(255) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (student_id) REFERENCES students(id)
)""")

# Upgrade an older installation while retaining its students and attendance.
cur.execute("SHOW COLUMNS FROM attendance LIKE 'subject_id'")
if not cur.fetchone():
    cur.execute("ALTER TABLE attendance ADD COLUMN subject_id INT NULL AFTER student_id")
cur.execute("""SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema=%s AND table_name='attendance' AND index_name='one_record_per_student_date_subject'""", (db_name,))
if not cur.fetchone()[0]:
    cur.execute("ALTER TABLE attendance ADD UNIQUE KEY one_record_per_student_date_subject (student_id, attendance_date, subject_id)")
# Add the replacement index first: MySQL needs an index beginning with student_id
# to keep the existing student foreign key valid while the old key is removed.
cur.execute("""SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema=%s AND table_name='attendance' AND index_name='one_record_per_student_per_day'""", (db_name,))
if cur.fetchone()[0]:
    cur.execute("ALTER TABLE attendance DROP INDEX one_record_per_student_per_day")
cur.execute("""SELECT COUNT(*) FROM information_schema.table_constraints
  WHERE constraint_schema=%s AND table_name='attendance' AND constraint_name='fk_attendance_subject'""", (db_name,))
if not cur.fetchone()[0]:
    cur.execute("ALTER TABLE attendance ADD CONSTRAINT fk_attendance_subject FOREIGN KEY (subject_id) REFERENCES subjects(id)")

# Optional teacher-account bootstrap/reset for a hosted deployment. Remove these
# variables from the host after one successful deploy so later restarts do not
# keep resetting the password.
bootstrap_username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
bootstrap_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
if bootstrap_username and len(bootstrap_password) >= 8:
    cur.execute("SELECT id,role FROM users WHERE username=%s", (bootstrap_username,))
    existing_admin = cur.fetchone()
    if not existing_admin:
        cur.execute("INSERT INTO users(username,password_hash) VALUES(%s,%s)",
                    (bootstrap_username, generate_password_hash(bootstrap_password)))
    elif existing_admin[1] == "teacher":
        cur.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                    (generate_password_hash(bootstrap_password), existing_admin[0]))
    else:
        print("Bootstrap password skipped: that username belongs to a student account.")

conn.commit()
cur.close()
conn.close()
print("Database schema is ready.")
