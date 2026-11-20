from pathlib import Path
import html

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "screens"
OUT.mkdir(parents=True, exist_ok=True)
APP_CSS = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
MOCK_CSS = r"""
*{box-sizing:border-box}html,body{margin:0;width:1366px;height:900px;overflow:hidden;background:#f8f9fc;color:#20243b;font:13px Arial,sans-serif}
.sidebar{width:225px;padding:21px 14px}.brand{padding:0 7px 28px;font-size:18px}.brand-icon{width:31px;height:31px}.nav-label{font-size:9px}.nav-link{padding:9px 10px;font-size:11px;gap:10px}.nav-link>span{font-size:15px;width:16px}
.main{margin-left:225px;min-height:900px}.topbar{height:72px;padding:13px 28px}.topbar h1{font-size:18px}.eyebrow{font-size:9px}.content{padding:21px 28px;max-width:none}
.welcome-row{margin-bottom:15px}.welcome-row h2{font-size:17px}.muted{font-size:10px}.panel{border-radius:10px;margin-bottom:13px}.panel-head{padding:14px 16px}.panel-head h3{font-size:12px}.panel-head .muted{font-size:9px}
th{padding:9px 12px;font-size:8px}td{padding:10px 12px;font-size:10px}.table-scroll table{min-width:0}.button{font-size:10px;padding:8px 11px}.button.tiny{font-size:9px;padding:6px 9px}
.form-grid{gap:10px}.form-grid label,.filter-bar label,.form-stack label{font-size:9px;gap:5px}.form-grid input,.form-grid select,.filter-bar input,.filter-bar select,.form-stack input{padding:8px 9px;border:1px solid #e9eaf1;border-radius:7px;background:white;color:#20243b;font-size:10px;min-height:31px}.form-stack{gap:11px}.edit-panel{padding:17px}.toolbar{padding:11px 14px}.search-input{font-size:10px;padding:8px}.attendance-tools{padding:11px 14px}.attendance-submit{padding:11px 14px}
.mock-pill{display:inline-flex;align-items:center;gap:6px;background:#f3f1ff;color:#6654d8;border:1px solid #e8e4ff;border-radius:20px;padding:5px 9px;font-size:8px;font-weight:bold;letter-spacing:.4px}.mock-pill:before{content:'';width:6px;height:6px;border-radius:50%;background:#58b68c}.mock-note{position:absolute;right:18px;bottom:12px;font-size:8px;color:#a0a3b2;z-index:20}
.alert-banner{margin:0 0 12px;padding:9px 12px}.alert-banner b{font-size:10px}.alert-banner small{font-size:8px}.empty-state{padding:18px}.stat-card{padding:12px}.stat-value{font-size:22px;margin-top:8px}.stat-icon{width:27px;height:27px;font-size:14px}.stat-tag{font-size:7px}.stat-label{font-size:10px}.stat-foot{font-size:8px;margin-top:5px}.stats-grid{gap:10px;margin-bottom:14px}
.form-grid label input[type=date],.form-grid label input[type=time]{min-height:31px}.badge{font-size:8px;padding:4px 7px}
.main-login{width:1366px;height:900px;min-height:900px;display:grid;place-items:center}.main-login .content{padding:38px;max-width:none}.login-wrap{width:1110px;min-height:660px}.login-card{padding:55px}.login-art{min-height:660px}.login-brand{margin-bottom:34px}
.sample-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:13px}.sample-box{background:white;border:1px solid #ececf2;border-radius:10px;padding:12px}.sample-box b{display:block;font:800 20px Manrope,Arial,sans-serif;margin:6px 0 2px}.sample-box small{color:#9296a8;font-size:8px}.sample-filter{display:flex;gap:10px;padding:12px 14px;align-items:end}.sample-filter label{display:flex;flex-direction:column;gap:5px;color:#666b80;font-size:8px;font-weight:bold;flex:1}.sample-filter input,.sample-filter select{height:30px;padding:6px 8px;border:1px solid #e8e9f0;border-radius:6px;background:white;font-size:9px;color:#4a4e64}
"""

def field(label, value="", kind="text", hint=""):
    extra = f' placeholder="{html.escape(value)}"' if kind == "placeholder" else f' value="{html.escape(value)}"'
    input_kind = "text" if kind == "placeholder" else kind
    return f'<label>{html.escape(label)}<input type="{input_kind}"{extra}>{f"<small>{html.escape(hint)}</small>" if hint else ""}</label>'

def select(label, value):
    return f'<label>{html.escape(label)}<select><option>{html.escape(value)}</option></select></label>'

def panel(title, subtitle, content):
    return f'<div class="panel"><div class="panel-head"><div><h3>{title}</h3><p class="muted">{subtitle}</p></div></div>{content}</div>'

def table(headers, rows):
    head = "".join(f"<th>{x}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'

NAV = [
    ("Overview", "▦"), ("Students", "♙"), ("Classes", "▦"), ("Teachers", "♙"),
    ("Timetable", "◷"), ("Subjects", "▣"), ("Mark attendance", "✓"),
    ("Change history", "◷"), ("Reports", "▤"), ("Notifications", "✉")
]

def shell(filename, heading, content, active="Overview", role="teacher"):
    nav = "".join(f'<a class="nav-link {"active" if label==active else ""}" href="#"><span>{icon}</span>{label}</a>' for label, icon in NAV)
    html_doc = f'''<!doctype html><html><head><meta charset="utf-8"><style>{APP_CSS}\n{MOCK_CSS}</style></head><body>
<aside class="sidebar"><div class="brand-row"><a class="brand" href="#"><span class="brand-icon">A</span><span>Attend<span class="brand-light">Ease</span></span></a></div><div class="nav-label">MAIN MENU</div><nav>{nav}</nav><div class="sidebar-bottom"><div class="profile"><span class="avatar">{role[:1].upper()}</span><span><b>{role}.demo</b><small>{role.title()}</small></span></div><a class="logout" href="#">Change password</a><a class="logout" href="#">Sign out ↗</a></div></aside>
<main class="main"><header class="topbar"><div><span class="eyebrow">ATTENDANCE MANAGEMENT</span><h1>{heading}</h1></div><div class="top-date"><span class="date-dot"></span>2026-11-19</div></header><section class="content"><div class="mock-pill">DEMO SCREEN - SAMPLE DATA</div>{content}</section></main><div class="mock-note">AttendEase · Illustrative screen capture</div></body></html>'''
    (OUT / f"{filename}.html").write_text(html_doc, encoding="utf-8")

def login_screen(filename, role=None):
    if not role:
        content = '''<div class="login-wrap landing-wrap"><section class="login-card landing-card"><a class="brand login-brand"><span class="brand-icon">A</span><span>Attend<span class="brand-light">Ease</span></span></a><div class="login-eyebrow"><span class="live-dot"></span> ATTENDANCE MANAGEMENT</div><h1>Attendance,<br><span>made clear.</span></h1><p class="login-lead">Manage class attendance, follow progress, and keep everyone on the same page.</p><div class="role-options"><a class="role-option"><span class="role-option-icon">✦</span><span class="role-option-copy"><b>Teacher login</b><small>Manage classes, attendance and reports</small></span><span class="role-arrow">→</span></a><a class="role-option student-option"><span class="role-option-icon">◉</span><span class="role-option-copy"><b>Student login</b><small>View your own attendance and timetable</small></span><span class="role-arrow">→</span></a></div><div class="login-foot">Students see their own records. Teachers manage the system.</div></section><aside class="login-art landing-art"><div class="art-orbit orbit-one"></div><div class="art-orbit orbit-two"></div><div class="art-orbit orbit-three"></div><div class="overview-card"><div class="overview-card-head"><span class="overview-logo">A</span><span><b>AttendEase</b><small>CLASS OVERVIEW</small></span><span class="overview-menu">···</span></div><div class="overview-heading"><span>Stay on track</span><span class="overview-check">✓</span></div><p class="overview-subtitle">Everything for the school day, together.</p><div class="overview-feature"><span class="feature-icon purple-feature">✓</span><span><b>Attendance</b><small>Mark and review class records</small></span><span class="feature-chevron">›</span></div><div class="overview-feature"><span class="feature-icon blue-feature">◷</span><span><b>Timetable</b><small>Keep each class in rhythm</small></span><span class="feature-chevron">›</span></div><div class="overview-feature"><span class="feature-icon green-feature">▤</span><span><b>Reports</b><small>Understand attendance progress</small></span><span class="feature-chevron">›</span></div><div class="overview-card-footer">One clear view for every school day</div></div><div class="art-caption">Less time searching.<br><b>More time supporting students.</b></div></aside></div>'''
        doc = f'<!doctype html><html><head><meta charset="utf-8"><style>{APP_CSS}\n{MOCK_CSS}</style></head><body><main class="main-login"><section class="content">{content}</section></main></body></html>'
        (OUT / f"{filename}.html").write_text(doc, encoding="utf-8")
        return
    desc = "Manage classes, attendance and reports." if role == "teacher" else "View your attendance and class timetable."
    content = f'''<div class="login-wrap signin-wrap"><section class="login-card signin-card"><a class="brand login-brand"><span class="brand-icon">A</span><span>Attend<span class="brand-light">Ease</span></span></a><div class="login-eyebrow"><span class="live-dot"></span> SECURE {role.upper()} SIGN IN</div><h1>Welcome back,<br><span>{role.title()}.</span></h1><p class="login-lead">{desc}</p><form class="form-stack signin-form"><label>Username<input value="demo.{role}"></label><label>Password<input type="password" value="example-password"></label><button class="button primary full signin-submit">Sign in →</button></form><div class="login-foot">← Choose account type</div></section><aside class="login-art signin-art"><div class="art-orbit orbit-one"></div><div class="art-orbit orbit-two"></div><div class="art-orbit orbit-three"></div><div class="overview-card"><div class="overview-card-head"><span class="overview-logo">A</span><span><b>AttendEase</b><small>{role.upper()} WORKSPACE</small></span></div><div class="overview-heading"><span>{"Your classes, at a glance" if role=="teacher" else "Your school day, in view"}</span><span class="overview-check">✓</span></div><p class="overview-subtitle">{desc}</p></div><div class="art-caption">{desc}</div></aside></div>'''
    doc = f'<!doctype html><html><head><meta charset="utf-8"><style>{APP_CSS}\n{MOCK_CSS}</style></head><body><main class="main-login"><section class="content">{content}</section></main></body></html>'
    (OUT / f"{filename}.html").write_text(doc, encoding="utf-8")

login_screen("01_landing")
login_screen("02_teacher_login", "teacher")
login_screen("03_student_login", "student")

stats = '<div class="sample-stats">' + ''.join(f'<div class="sample-box"><small>{lab}</small><b>{val}</b><small>{cap}</small></div>' for lab,val,cap in [("TOTAL STUDENTS","48","Active roster"),("PRESENT TODAY","42","Marked present"),("ABSENT TODAY","4","Follow-up"),("LOW ATTENDANCE","3","Below 75%")]) + '</div>'
today_table = table(["TIME","CLASS / SECTION","PERIOD","TEACHER","ACTION"], [
    ("09:00-09:45","BTech CSE · A","Lecture 1 · Web Technology","Mr. Yash Gautam",'<span class="button tiny primary">Mark attendance</span>'),
    ("09:45-10:30","BTech CSE · A","Lecture 2 · Mathematics","Ms. Kavya Rao",'<span class="button tiny primary">Mark attendance</span>'),
    ("12:30-13:00","BTech CSE · A","Lunch break","-","-")])
overview = '<div class="welcome-row"><div><h2>Your classroom at a glance</h2><p class="muted">Today\'s attendance and class schedule.</p></div><span class="button primary">＋ Mark attendance</span></div>' + stats + panel("Today's timetable · Wednesday", "Quick access to scheduled attendance", today_table) + '<div class="alert-banner"><span class="alert-icon">!</span><span><b>3 students below 75% attendance</b><small>All-time attendance rate. Open reports for more detail.</small></span></div>'
shell("04_overview","Overview",overview)

class_form = '<form class="form-grid">'+field("Class name *","BTech CSE III Sem")+field("Section *","A")+field("Number of students *","40","number")+'<div class="form-actions wide"><button class="button primary">Continue to student details →</button></div></form>'
class_rows = table(["CLASS","SECTION","STUDENTS","DETAILS"],[("BTech CSE III Sem","A","40",'<span class="text-link">Open class →</span>'),("BTech CSE III Sem","B","36",'<span class="text-link">Open class →</span>')])
shell("05_classes","Classes",'<div class="welcome-row"><div><h2>Class sections</h2><p class="muted">Create a class section and enter students together.</p></div></div>'+panel("Add a class section","Choose the class, section and student count",f'<div class="edit-panel">{class_form}</div>')+panel("Saved class sections","Open a section to manage students and timetable",class_rows),"Classes")

bulk_form = '<form class="form-grid">'+field("Roll number *","301")+field("Full name *","Aarav Mehta")+field("Date of birth *","2005-08-10","date")+field("Student email","aarav.demo@example.edu","email")+field("Guardian name","R. Mehta")+field("Guardian email","guardian.demo@example.com","email")+'<div class="wide"><h3>Student 2</h3></div>'+field("Roll number *","302")+field("Full name *","Siya Rao")+field("Date of birth *","2005-11-02","date")+field("Student email","siya.demo@example.edu","email")+field("Guardian name","P. Rao")+field("Guardian email","parent.demo@example.com","email")+'<div class="form-actions wide"><button class="button primary">Save all students</button></div></form>'
shell("06_bulk_students","Add students to BTech CSE · Section A",'<div class="welcome-row"><div><h2>Enter student details</h2><p class="muted">Student login is created from the student name and date of birth.</p></div></div>'+panel("Student details","Sample values only. Required fields are marked with *.",f'<div class="edit-panel">{bulk_form}</div>'),"Classes")

edit_form = '<form class="form-grid">'+field("Roll number *","301")+field("Full name *","Aarav Mehta")+field("Class *","BTech CSE III Sem")+field("Section","A")+field("Date of birth *","2005-08-10","date")+field("Student email","aarav.demo@example.edu","email")+field("Guardian name","R. Mehta")+field("Guardian email","guardian.demo@example.com","email")+'<div class="wide panel setup-note"><h3>Student portal login</h3><p class="muted">Login username: aaravmehta100805. Reset to initial password is available to the teacher.</p><span class="button secondary">Reset to initial password</span></div><div class="form-actions wide"><span class="button secondary">Cancel</span><button class="button primary">Save changes</button></div></form>'
shell("07_student_profile","Edit student",'<div class="welcome-row"><div><h2>Update student details</h2><p class="muted">Student details and guardian email settings.</p></div><span class="button secondary">← Back to students</span></div>'+panel("Student profile","Sample values only",f'<div class="edit-panel">{edit_form}</div>'),"Students")

teachers_form = '<form class="form-grid">'+field("Teacher full name *","Mr. Yash Gautam")+field("Email (optional)","yash.demo@example.edu","email")+'<div class="form-actions wide"><button class="button primary">Add teacher</button></div></form>'
teachers_rows = table(["TEACHER","EMAIL"],[("Mr. Yash Gautam","yash.demo@example.edu"),("Ms. Kavya Rao","kavya.demo@example.edu")])
shell("08_teachers","Teachers",'<div class="welcome-row"><div><h2>Teachers directory</h2><p class="muted">Add teachers before assigning class subjects.</p></div></div>'+panel("Add a teacher","Teacher names are assigned to subjects",f'<div class="edit-panel">{teachers_form}</div>')+panel("Teachers","Active teacher directory",teachers_rows),"Teachers")

subject_form = '<form class="form-grid">'+select("Class *","BTech CSE III Sem")+field("Subject name *","Web Technology")+select("Teacher *","Mr. Yash Gautam")+'<div class="form-actions wide"><button class="button primary">Save subject</button></div></form>'
subject_rows = table(["SUBJECT","CLASS","TEACHER","ACTIONS"],[("Web Technology","BTech CSE III Sem","Mr. Yash Gautam",'<span class="text-link">Archive</span>'),("Mathematics","BTech CSE III Sem","Ms. Kavya Rao",'<span class="text-link">Archive</span>')])
shell("09_subjects","Subjects",'<div class="welcome-row"><div><h2>Class subjects</h2><p class="muted">Assign every subject to its teacher.</p></div></div>'+panel("Add a subject","Choose a class and assigned teacher",f'<div class="edit-panel">{subject_form}</div>')+panel("Active subjects","Subjects are unique within each class",subject_rows),"Subjects")

timetable_form = '<form class="form-grid">'+select("Day *","Wednesday")+select("Period type *","Lecture")+field("Lecture number *","1","number")+select("Subject *","Web Technology · Mr. Yash Gautam")+field("Start time *","09:00","time")+field("End time *","09:45","time")+field("Room (optional)","Room 204")+'<div class="form-actions wide"><button class="button primary">Add to timetable</button></div></form>'
timetable_rows = table(["DAY","TIME","PERIOD","TEACHER","ROOM","ACTION"],[("Wednesday","09:00-09:45","Lecture 1 · Web Technology","Mr. Yash Gautam","Room 204","Delete"),("Wednesday","12:30-13:00","Lunch break","-","-","Delete")])
shell("10_timetable","Class BTech CSE · Section A",'<div class="welcome-row"><div><h2>Weekly timetable</h2><p class="muted">This timetable is visible to students in this section.</p></div></div>'+panel("Add a lecture or lunch break","Lecture number is required for lectures; lunch breaks have no lecture number",f'<div class="edit-panel">{timetable_form}</div>')+panel("Scheduled periods","Wednesday · Class BTech CSE · Section A",timetable_rows),"Timetable")

attendance_filter = '<div class="sample-filter"><label>Date<input value="2026-11-19"></label><label>Class<select><option>BTech CSE III Sem</option></select></label><label>Section<select><option>A</option></select></label><label>Subject<select><option>Web Technology · Mr. Yash Gautam</option></select></label><button class="button secondary">Show students</button></div>'
attendance_table = table(["STUDENT","ROLL NO.","CLASS","STATUS"],[("Aarav Mehta","301","BTech CSE · A",'<span class="badge present">Present</span>'),("Siya Rao","302","BTech CSE · A",'<span class="badge absent">Absent</span>'),("Kabir Shah","303","BTech CSE · A",'<span class="badge late">Late</span>')])
attendance_content = '<div class="welcome-row"><div><h2>Subject-wise attendance</h2><p class="muted">Select a class and subject, then record each student\'s status.</p></div></div>'+panel("Filters","Date, class, section and subject",attendance_filter)+panel("Student attendance","3 students · 2026-11-19 · sorted by roll number",'<div class="attendance-tools"><b>All present</b><span class="muted">All absent</span></div>'+attendance_table+'<div class="attendance-submit"><button class="button primary">Save attendance</button></div>')
shell("11_attendance","Mark attendance",attendance_content,"Mark attendance")

history_rows = table(["CHANGED AT","STUDENT","CLASS / SECTION","DATE","SUBJECT","PREVIOUS","NEW STATUS","CHANGED BY"],[("2026-11-19 09:52","301 · Aarav Mehta","BTech CSE · A","2026-11-19","Web Technology","Not marked",'<span class="badge absent">Absent</span>',"teacher.demo"),("2026-11-19 10:05","302 · Siya Rao","BTech CSE · A","2026-11-19","Web Technology","Absent",'<span class="badge present">Present</span>',"teacher.demo")])
shell("12_change_history","Attendance history",'<div class="welcome-row"><div><h2>Attendance change history</h2><p class="muted">Recent markings and status changes. Re-saving the same status is not logged.</p></div></div>'+panel("Recent change events","Previous and new status, staff user and timestamp",history_rows),"Change history")

report_filter = '<div class="sample-filter"><label>From<input value="2026-11-01"></label><label>To<input value="2026-11-19"></label><label>Class<select><option>All classes</option></select></label><label>Subject<select><option>All subjects</option></select></label><label>Student<select><option>All students</option></select></label><button class="button secondary">Apply filters</button></div>'
report_rows = table(["STUDENT","CLASS","PRESENT","ABSENT","LATE","SESSIONS","ATTENDANCE"],[("Aarav Mehta · 301","BTech CSE · A","6","3","1","10",'<b>60%</b> <span class="badge low">Low</span>'),("Siya Rao · 302","BTech CSE · A","9","1","0","10","90%"),("Kabir Shah · 303","BTech CSE · A","7","2","1","10","70%")])
shell("13_reports","Reports",'<div class="welcome-row"><div><h2>Attendance reports</h2><p class="muted">Filter records by date, class, subject or student.</p></div><span class="button primary">↓ Export CSV</span></div><div class="alert-banner"><span class="alert-icon">!</span><span><b>2 students below 75%</b><small>Within the selected date range.</small></span></div>'+panel("Report filters","Choose a reporting range and scope",report_filter)+panel("Attendance summary","Attendance percentage is based on marked sessions",report_rows),"Reports")

notification_rows = table(["STUDENT","DATE","SUBJECT","RECIPIENT","RESULT","TIME"],[("Aarav Mehta · 301","2026-11-19","Web Technology","guardian.demo@example.com",'<span class="badge present">Sent</span>',"09:53"),("Aarav Mehta · 301","2026-11-19","Web Technology","aarav.demo@example.edu",'<span class="badge present">Sent</span>',"09:53")])
notifications = '<div class="welcome-row"><div><h2>Student and guardian email alerts</h2><p class="muted">Emails are attempted when attendance changes to Absent or Late.</p></div></div><div class="stats-grid"><article class="stat-card"><div class="stat-top"><span class="stat-icon violet">✉</span><span class="badge present">READY</span></div><div class="stat-label">Email alerts</div><div class="stat-foot">Provider settings configured</div></article></div>'+panel("How email alerts work","Emails go to saved student and guardian contacts",'<div class="edit-panel"><p class="muted">A repeated save with the same status does not send another alert. Provider secrets stay in hosting settings.</p></div>')+panel("Recent email attempts","Latest delivery attempts",notification_rows)
shell("14_notifications","Notifications",notifications,"Notifications")

student_stats = '<div class="stats-grid"><article class="stat-card"><div class="stat-label">MARKED CLASSES</div><div class="stat-value">10</div></article><article class="stat-card"><div class="stat-label">PRESENT</div><div class="stat-value">6</div></article><article class="stat-card"><div class="stat-label">ABSENT</div><div class="stat-value">3</div></article><article class="stat-card"><div class="stat-label">ATTENDANCE</div><div class="stat-value">60%</div></article></div>'
student_table = table(["DAY","TIME","SUBJECT / BREAK","TEACHER","ROOM"],[("Wednesday","09:00-09:45","Lecture 1 · Web Technology","Mr. Yash Gautam","Room 204"),("Wednesday","12:30-13:00","Lunch break","-","-")])
student_history = table(["DATE","SUBJECT","STATUS"],[("2026-11-19","Web Technology",'<span class="badge absent">Absent</span>'),("2026-11-18","Mathematics",'<span class="badge present">Present</span>')])
student_portal = '<div class="welcome-row"><div><h2>Hello, Aarav Mehta</h2><p class="muted">Roll 301 · BTech CSE III Sem · Section A</p></div></div><div class="alert-banner"><span class="alert-icon">!</span><span><b>Your attendance is below 75% (60%)</b><small>Attend upcoming classes regularly and contact your teacher if you need help.</small></span></div>'+student_stats+panel("My class timetable","BTech CSE III Sem · Section A · Read only",student_table)+panel("Attendance history","Only your own records are shown",student_history)
shell("15_student_portal","My attendance",student_portal,"", "student")

password_form = '<form class="form-stack">'+field("New password","At least 8 characters","password")+field("Confirm new password","Re-enter new password","password")+'<button class="button primary">Save new password</button></form>'
shell("16_student_password","Change password",'<div class="welcome-row"><div><h2>Secure your student account</h2><p class="muted">Replace the temporary password before opening the student portal.</p></div></div>'+panel("Change your first-login password","Use at least 8 characters",f'<div class="edit-panel">{password_form}</div>'),"", "student")

# Additional screen: student directory search and class section roster.
directory_rows = table(["STUDENT","ROLL NO.","CLASS / SECTION","EMAIL","ACTIONS"],[("Aarav Mehta","301","BTech CSE · A","aarav.demo@example.edu","Edit · Archive"),("Siya Rao","302","BTech CSE · A","siya.demo@example.edu","Edit · Archive")])
shell("17_student_directory","Students",'<div class="welcome-row"><div><h2>Students directory</h2><p class="muted">Search, update or archive student profiles.</p></div><span class="button primary">＋ Add student</span></div><div class="panel"><div class="toolbar"><input class="search-input" value="Search name, roll no. or class"><button class="button secondary">Search</button></div>'+directory_rows+'<div class="table-footer">2 demonstration student records</div></div>',"Students")

class_roster = table(["ROLL NO.","STUDENT","DOB","LOGIN USERNAME","EMAIL","PROFILE"],[("301","Aarav Mehta","2005-08-10","aaravmehta100805","aarav.demo@example.edu","Edit"),("302","Siya Rao","2005-11-02","siyarao021105","siya.demo@example.edu","Edit")])
class_details = '<div class="welcome-row"><div><h2>Class BTech CSE III Sem · Section A</h2><p class="muted">Students, assigned subjects and this section\'s timetable.</p></div></div>'+panel("Subjects for this class","Each subject is linked to an assigned teacher",table(["SUBJECT","TEACHER"],[("Web Technology","Mr. Yash Gautam"),("Mathematics","Ms. Kavya Rao")]))+panel("Students","2 demonstration records · sorted by roll number",class_roster)
shell("18_class_detail","Class section",class_details,"Classes")

# Full-page HTML snapshots are captured by Playwright/Edge in capture_screens.js.
print(f"Created {len(list(OUT.glob('*.html')))} illustrative screen pages in {OUT}")
