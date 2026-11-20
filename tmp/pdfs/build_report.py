from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Image, Table, TableStyle, KeepTogether, HRFlowable)
from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image as PILImage, ImageDraw, ImageFont
import pdfplumber
import re

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
SCREEN_DIR = WORK / "screens"
OUT_DIR = ROOT / "output" / "pdf"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PDF_PATH = OUT_DIR / "AttendEase_Minor_Project_Report.pdf"
LOGO_PATH = WORK / "kcc_logo.png"
ARCH_PATH = WORK / "architecture.png"
FLOW_PATH = WORK / "attendance_flow.png"
ER_PATH = WORK / "data_model.png"

INK = colors.HexColor("#20243b")
MUTED = colors.HexColor("#697087")
PURPLE = colors.HexColor("#6957dc")
PALE = colors.HexColor("#f4f2ff")
LINE = colors.HexColor("#e5e6ed")
TEAL = colors.HexColor("#21956c")
LIGHT = colors.HexColor("#f7f8fc")

members = [
    ("Gaurav Singh", "Team Leader"),
    ("Abhishek Kumar Bishawakarma", "Member 2"),
    ("Anish Pal", "Member 3"),
    ("Mayank Srivastav", "Member 4"),
    ("Abhay Kumar Gupta", "Member 5"),
]

screens = [
    ("01_landing.png", "Public landing page and role selection"),
    ("02_teacher_login.png", "Teacher sign-in page"),
    ("03_student_login.png", "Student sign-in page"),
    ("04_overview.png", "Teacher overview with timetable reminder and low-attendance panel"),
    ("05_classes.png", "Create a class section and review saved sections"),
    ("06_bulk_students.png", "Bulk student entry fields for class and section"),
    ("07_student_profile.png", "Edit student profile and student portal account controls"),
    ("08_teachers.png", "Teacher directory and add-teacher fields"),
    ("09_subjects.png", "Assign a class subject to a teacher"),
    ("10_timetable.png", "Class timetable fields including lecture number and lunch break"),
    ("11_attendance.png", "Attendance filters and Present, Absent, Late choices"),
    ("12_change_history.png", "Teacher-only attendance change history"),
    ("13_reports.png", "Date, class, subject and student report filters with CSV export"),
    ("14_notifications.png", "Email alert status and recent delivery attempts"),
    ("15_student_portal.png", "Student's read-only attendance and class timetable"),
    ("16_student_password.png", "Student first-login password change fields"),
    ("17_student_directory.png", "Student directory search and profile actions"),
    ("18_class_detail.png", "Class-section subjects and student roster"),
]

figures = [
    ("Figure 1. Three-tier AttendEase deployment and service architecture", "Three-tier AttendEase deployment and service architecture"),
    ("Figure 2. Teacher attendance marking and notification workflow", "Teacher attendance marking and notification workflow"),
    ("Figure 3. Main database entities and relationships", "Main database entities and relationships"),
] + [(f"Figure {i + 4}. {caption} (illustrative screen with sample values)", caption)
     for i, (_, caption) in enumerate(screens)]

tables_list = [
    "Table 1. Comparison of attendance management approaches",
    "Table 2. Software and hardware specifications",
    "Table 3. Core database entities and purpose",
    "Table 4. User roles and access matrix",
    "Table 5. Modules, inputs and outputs",
    "Table 6. Functional demonstration scenarios and expected results",
    "Table 7. Proposed team responsibilities",
]

toc_items = [
    ("Chapter 1 - Introduction", "CHAPTER 1 - INTRODUCTION", 0),
    ("1.1 Background of the problem", "1.1 Background of the Problem", 1),
    ("1.2 Problem statement", "1.2 Problem Statement", 1),
    ("1.3 Objectives", "1.3 Objectives", 1),
    ("1.4 Scope and assumptions", "1.4 Scope and Assumptions", 1),
    ("Chapter 2 - Literature Review", "CHAPTER 2 - LITERATURE REVIEW", 0),
    ("2.1 Review of existing research work", "2.1 Review of Existing Research Work", 1),
    ("2.2 Comparison and research gap", "2.2 Comparison and Research Gap Identification", 1),
    ("2.3 Relevance to AttendEase", "2.3 Relevance to AttendEase", 1),
    ("Chapter 3 - Methodology", "CHAPTER 3 - METHODOLOGY", 0),
    ("3.1 System architecture and workflow", "3.1 System Architecture and Workflow", 1),
    ("3.2 Hardware and software specifications", "3.2 Hardware and Software Specifications", 1),
    ("3.3 Database design", "3.3 Database Design", 1),
    ("3.4 Methodology and techniques", "3.4 Methodology and Techniques", 1),
    ("3.5 Security and privacy", "3.5 Security and Privacy", 1),
    ("Chapter 4 - Modules and Functionality", "CHAPTER 4 - MODULES AND FUNCTIONALITY", 0),
    ("4.1 Roles and authentication", "4.1 Roles and Authentication", 1),
    ("4.2 Student and class management", "4.2 Student and Class Management", 1),
    ("4.3 Teachers, subjects and timetable", "4.3 Teachers, Subjects and Timetable", 1),
    ("4.4 Attendance and audit history", "4.4 Attendance and Audit History", 1),
    ("4.5 Reports, alerts and student portal", "4.5 Reports, Alerts and Student Portal", 1),
    ("4.6 System screenshots", "4.6 System Screenshots", 1),
    ("Results and Discussion", "RESULTS AND DISCUSSION", 0),
    ("Conclusion", "CONCLUSION", 0),
    ("Future Scope", "FUTURE SCOPE", 0),
    ("References (IEEE format)", "REFERENCES", 0),
]

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodyReport", parent=styles["BodyText"], fontName="Times-Roman",
    fontSize=10.7, leading=15.5, alignment=TA_JUSTIFY, textColor=INK, spaceAfter=7, splitLongWords=1))
styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyText"], fontName="Times-Roman",
    fontSize=9.2, leading=12.4, alignment=TA_JUSTIFY, textColor=INK, spaceAfter=5, splitLongWords=1))
styles.add(ParagraphStyle(name="ChapterTitle", fontName="Times-Bold", fontSize=16, leading=21,
    alignment=TA_CENTER, textColor=INK, spaceBefore=4, spaceAfter=21, keepWithNext=True))
styles.add(ParagraphStyle(name="SectionTitle", fontName="Times-Bold", fontSize=12.4, leading=16,
    textColor=PURPLE, spaceBefore=11, spaceAfter=6, keepWithNext=True))
styles.add(ParagraphStyle(name="SubsectionTitle", fontName="Times-Bold", fontSize=10.8, leading=14,
    textColor=INK, spaceBefore=7, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name="FrontTitle", fontName="Times-Bold", fontSize=15, leading=20,
    alignment=TA_CENTER, textColor=INK, spaceAfter=20))
styles.add(ParagraphStyle(name="CoverTitle", fontName="Times-Bold", fontSize=24, leading=30,
    alignment=TA_CENTER, textColor=INK, spaceAfter=8))
styles.add(ParagraphStyle(name="CoverSub", fontName="Times-Roman", fontSize=13, leading=19,
    alignment=TA_CENTER, textColor=MUTED, spaceAfter=8))
styles.add(ParagraphStyle(name="Centered", fontName="Times-Roman", fontSize=11, leading=16,
    alignment=TA_CENTER, textColor=INK, spaceAfter=4))
styles.add(ParagraphStyle(name="CaptionReport", fontName="Times-Italic", fontSize=8.8, leading=11,
    alignment=TA_CENTER, textColor=MUTED, spaceBefore=4, spaceAfter=12))
styles.add(ParagraphStyle(name="TableCaption", fontName="Times-Bold", fontSize=9.4, leading=12,
    alignment=TA_CENTER, textColor=INK, spaceBefore=8, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name="TableCell", fontName="Times-Roman", fontSize=8.2, leading=10.5,
    textColor=INK, spaceAfter=0, splitLongWords=1))
styles.add(ParagraphStyle(name="TableHeader", fontName="Times-Bold", fontSize=8.2, leading=10.5,
    textColor=colors.white, alignment=TA_LEFT, spaceAfter=0))
styles.add(ParagraphStyle(name="TOCEntry", fontName="Times-Roman", fontSize=9.1, leading=12.1,
    textColor=INK, spaceAfter=0, splitLongWords=1))
styles.add(ParagraphStyle(name="TOCChapter", fontName="Times-Bold", fontSize=9.2, leading=12.1,
    textColor=INK, spaceAfter=0))
styles.add(ParagraphStyle(name="Reference", fontName="Times-Roman", fontSize=9.4, leading=13.1,
    leftIndent=20, firstLineIndent=-20, textColor=INK, spaceAfter=8, splitLongWords=1))
styles.add(ParagraphStyle(name="SmallNote", fontName="Times-Italic", fontSize=8.6, leading=11,
    textColor=MUTED, spaceAfter=6))

def P(text, style="BodyReport"):
    return Paragraph(text, styles[style])

def H(text):
    return Paragraph(text, styles["SectionTitle"])

def H2(text):
    return Paragraph(text, styles["SubsectionTitle"])

def chapter(number, title):
    return Paragraph(f"CHAPTER {number} - {title.upper()}", styles["ChapterTitle"])

def bullets(items, small=False):
    out = []
    for item in items:
        out.append(P(f"- {item}", "BodySmall" if small else "BodyReport"))
    return out

def make_table(caption, headers, rows, widths, font=8.2):
    story = [P(caption, "TableCaption")]
    data = [[P(str(x), "TableHeader") for x in headers]]
    for row in rows:
        data.append([P(str(x), "TableCell") for x in row])
    tbl = Table(data, colWidths=widths, repeatRows=1, hAlign="CENTER")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PURPLE),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
        ("GRID", (0,0), (-1,-1), 0.35, LINE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story += [tbl, Spacer(1, 8)]
    return story

def make_diagram(path, title, boxes, arrows, size=(1500,760)):
    img = PILImage.new("RGB", size, "#f7f8fc")
    d = ImageDraw.Draw(img)
    regular = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 27)
    bold = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 30)
    small = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 21)
    d.text((55,35), title, fill="#20243b", font=bold)
    coords = {}
    for key, x,y,w,h,heading,lines,color in boxes:
        coords[key]=(x,y,w,h)
    for source,target,label in arrows:
        sx,sy,sw,sh=coords[source]; tx,ty,tw,th=coords[target]
        start=(sx+sw if tx>sx else sx+sw//2, sy+sh//2)
        end=(tx if tx>sx else tx+tw//2, ty+th//2 if abs((ty+th//2)-start[1])<100 else ty)
        d.line([start,end],fill="#8186a0",width=4)
        import math
        ang=math.atan2(end[1]-start[1],end[0]-start[0]); sizea=15
        p1=(end[0]-sizea*math.cos(ang-0.45),end[1]-sizea*math.sin(ang-0.45))
        p2=(end[0]-sizea*math.cos(ang+0.45),end[1]-sizea*math.sin(ang+0.45))
        d.polygon([end,p1,p2],fill="#8186a0")
        if label:
            mx=(start[0]+end[0])//2; my=(start[1]+end[1])//2-22
            d.text((mx-25,my),label,fill="#555a73",font=small)
    for key,x,y,w,h,heading,lines,color in boxes:
        d.rounded_rectangle((x,y,x+w,y+h),radius=22,fill="white",outline=color,width=4)
        d.rounded_rectangle((x,y,x+w,y+58),radius=20,fill=color)
        d.rectangle((x,y+38,x+w,y+58),fill=color)
        d.text((x+18,y+13),heading,fill="white",font=bold)
        yy=y+76
        for line in lines:
            d.text((x+18,yy),line,fill="#3c4159",font=regular); yy+=39
    img.save(path)

def prepare_assets():
    ref = PILImage.open(WORK / "reference" / "ref-1.png").convert("RGB")
    ref.crop((260, 472, 462, 635)).save(LOGO_PATH)
    architecture_boxes = [
      ("client",70,230,330,260,"USER DEVICE",["Modern web browser","HTML and Jinja pages","CSS responsive layout","JavaScript interactions"],"#6957dc"),
      ("server",575,230,355,260,"FLASK APPLICATION",["Routes and sessions","Role-based access","Business rules","Parameterized SQL"],"#3185c9"),
      ("db",1120,230,300,260,"TIDB DATABASE",["MySQL-compatible","Student and class data","Attendance and audit","Timetable and reports"],"#21956c"),
      ("mail",575,535,355,145,"EMAIL PROVIDER",["Apps Script / Resend / SMTP"],"#db8e3d"),
      ("host",575,55,355,120,"RENDER HOSTING",["Gunicorn web service"],"#7564e7"),
    ]
    architecture_arrows=[("client","server","HTTPS"),("server","db","SQL"),("server","mail","email"),("host","server","runs")]
    make_diagram(ARCH_PATH,"AttendEase system architecture",architecture_boxes,architecture_arrows)
    flow_boxes = [
      ("teacher",60,240,250,180,"TEACHER",["Sign in","Choose date and class","Select section and subject"],"#6957dc"),
      ("mark",420,240,260,180,"MARK STATUS",["Students sorted by roll","Present / Absent / Late","Save attendance"],"#3185c9"),
      ("save",790,240,270,180,"SAVE TRANSACTION",["Update attendance row","Write audit event","Commit to database"],"#21956c"),
      ("notify",1160,450,270,170,"OPTIONAL EMAIL",["Absent or Late change","Email student/guardian","Log provider result"],"#db8e3d"),
      ("read",1160,160,270,170,"REVIEW",["Teacher reports/history","Student own attendance","Student class timetable"],"#7564e7"),
    ]
    flow_arrows=[("teacher","mark","selected group"),("mark","save","validated status"),("save","notify","if changed to Absent/Late"),("save","read","saved records")]
    make_diagram(FLOW_PATH,"Attendance marking workflow",flow_boxes,flow_arrows)
    er_boxes = [
      ("users",45,100,320,185,"USERS",["id, username, role","password_hash","student_id"],"#6957dc"),
      ("students",450,80,360,205,"STUDENTS",["id, roll_no, class, section","DOB, email, guardian","active"],"#3185c9"),
      ("teachers",45,470,320,170,"TEACHERS",["id, full_name, email","active"],"#db8e3d"),
      ("subjects",450,450,360,190,"SUBJECTS",["id, class, subject_name","teacher_id"],"#21956c"),
      ("attendance",930,85,500,205,"ATTENDANCE",["student_id, subject_id","date, status, marked_by","unique student/date/subject"],"#7564e7"),
      ("timetable",930,390,500,170,"CLASS_TIMETABLE",["class, section, weekday","lecture number, subject, times"],"#2d91a6"),
      ("audit",450,680,360,75,"AUDIT LOG",["previous/new status, user, time"],"#c26470"),
    ]
    er_arrows=[("users","students","account link"),("teachers","subjects","assigned teacher"),("students","attendance","1 to many"),("subjects","attendance","1 to many"),("students","timetable","class-section match"),("attendance","audit","changes")]
    make_diagram(ER_PATH,"AttendEase data model (simplified)",er_boxes,er_arrows,(1500,800))

def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip().casefold()

def roman(number):
    nums=[(1000,"m"),(900,"cm"),(500,"d"),(400,"cd"),(100,"c"),(90,"xc"),(50,"l"),(40,"xl"),(10,"x"),(9,"ix"),(5,"v"),(4,"iv"),(1,"i")]
    out=""
    for value,symbol in nums:
        while number>=value:
            out+=symbol; number-=value
    return out

def page_footer(canvas, doc):
    page=doc.page
    if page==1: return
    canvas.saveState()
    width,height=A4
    if page>doc.front_pages:
        label=str(page-doc.front_pages)
        canvas.setFont("Times-Roman",8)
        canvas.setFillColor(MUTED)
        canvas.drawString(doc.leftMargin, height-28, "ATTENDEASE | MINOR PROJECT REPORT")
        canvas.setStrokeColor(LINE); canvas.setLineWidth(.45)
        canvas.line(doc.leftMargin,height-34,width-doc.rightMargin,height-34)
    else:
        label=roman(page-1)
    canvas.setFont("Times-Roman",9)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(width/2,25,label)
    canvas.restoreState()

def base_doc(front_pages=6):
    doc=SimpleDocTemplate(str(PDF_PATH),pagesize=A4,leftMargin=.86*inch,rightMargin=.86*inch,
        topMargin=.63*inch,bottomMargin=.58*inch,title="AttendEase Student Attendance Management System - Minor Project Report",
        author="Gaurav Singh, Abhishek Kumar Bishawakarma, Anish Pal, Mayank Srivastav, Abhay Kumar Gupta")
    doc.front_pages=front_pages
    return doc

def title_index_page(title, rows, page_map, width=6.45*inch):
    data=[]
    for row in rows:
        if isinstance(row, str):
            label, search = row, row
        else:
            label, search = row[0], row[1]
        page=page_map.get(search,"-")
        style = "TOCChapter" if label.lower().startswith(("chapter", "results", "conclusion", "future", "references")) else "TOCEntry"
        data.append([P(label,style),P(str(page),"TOCEntry")])
    tbl=Table(data,colWidths=[width-.45*inch,.45*inch],hAlign="CENTER")
    tbl.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(1,0),(1,-1),"RIGHT"),
        ("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LINEBELOW",(0,0),(-1,-1),0.2,colors.HexColor("#eeeeF2")),
    ]))
    return [P(title,"FrontTitle"),tbl]

def build_story(page_map):
    story=[]
    # Cover page follows the supplied KCC report layout.
    story += [Spacer(1,.16*inch),P("A PROJECT REPORT","FrontTitle"),P("ON","Centered"),Spacer(1,.05*inch),
        P("AttendEase","CoverTitle"),P("Student Attendance Management System","CoverSub"),
        P("Submitted in partial fulfillment of the requirements for the Minor Project","Centered"),
        Spacer(1,.17*inch),P("Submitted by","Centered")]
    for name,role in members:
        story.append(P(f"{name}  (Roll No. __________)" + ("  - Team Leader" if role=="Team Leader" else ""),"Centered"))
    story += [Spacer(1,.14*inch),P("Project Guide","Centered"),P("Mr. Yash Gautam","Centered"),Spacer(1,.18*inch)]
    logo=Image(str(LOGO_PATH),width=1.55*inch,height=1.25*inch)
    logo.hAlign="CENTER"
    story += [logo,Spacer(1,.12*inch),P("Department of Computer Science and Engineering","Centered"),
        P("KCC Institute of Technology and Management","Centered"),P("Greater Noida, Uttar Pradesh","Centered"),
        P("B.Tech - III Semester","Centered"),P("Academic Session: 2026-2027","Centered"),Spacer(1,.1*inch),
        P("Submission Date: ____________________","Centered"),PageBreak()]

    story += [P("ACKNOWLEDGEMENT","FrontTitle"),
        P("We express our sincere gratitude to our project guide, <b>Mr. Yash Gautam</b>, for his guidance, suggestions, and encouragement during the planning and development of AttendEase. His feedback helped us organize the project into clear modules and understand the requirements of an attendance management system."),
        P("We thank the Head of the Department and the faculty members of the Department of Computer Science and Engineering at KCC Institute of Technology and Management for providing academic support and an opportunity to complete this minor project."),
        P("We also thank our classmates, friends, and families for their encouragement. During development, we used AI-assisted coding and writing tools for explanations, code scaffolding, and report drafting. The project team is responsible for reviewing the code, understanding the design, verifying the final application, and following institute rules for acknowledging assistance."),
        Spacer(1,18),P("Gaurav Singh","Centered"),P("Team Leader, on behalf of the project team","Centered"),PageBreak()]

    story += [P("DECLARATION","FrontTitle"),
        P("We hereby declare that this report describes the AttendEase Student Attendance Management System prepared as a B.Tech III Semester minor project in the Department of Computer Science and Engineering at KCC Institute of Technology and Management, Greater Noida. The report is based on the project implementation and the references listed at the end of this document. We have identified external sources and AI-assisted support used during development and writing. We will review the final report, confirm our individual contributions, and make any changes required by institute policy before signing."),
        Spacer(1,14),P("Date: ____________________","BodyReport"),P("Place: Greater Noida","BodyReport"),Spacer(1,8)]
    dec_rows=[[P("Project member","TableHeader"),P("Roll number","TableHeader"),P("Signature","TableHeader")]]
    for name,_ in members: dec_rows.append([P(name,"TableCell"),P("________________","TableCell"),P("________________","TableCell")])
    dec=Table(dec_rows,colWidths=[2.55*inch,1.65*inch,2.0*inch],repeatRows=1)
    dec.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),PURPLE),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,LIGHT]),("GRID",(0,0),(-1,-1),.35,LINE),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story += [dec,Spacer(1,22),P("Guide verification","SubsectionTitle"),P("To the best of my knowledge, the project report has been reviewed under my guidance.","BodyReport"),Spacer(1,22),P("Guide Name and Signature: Mr. Yash Gautam","BodyReport"),P("Department of Computer Science and Engineering","BodyReport"),PageBreak()]

    # Contents and preliminary lists reproduce the sequence in the supplied format.
    story += title_index_page("TABLE OF CONTENTS",toc_items,page_map)+[PageBreak()]
    story += title_index_page("LIST OF FIGURES",[(a,a) for a,b in figures],page_map)+[PageBreak()]
    story += title_index_page("LIST OF TABLES",[(t,t) for t in tables_list],page_map)+[PageBreak()]

    # Chapter 1
    story += [chapter(1,"Introduction"),H("1.1 Background of the Problem"),
        P("Attendance is a routine academic record that influences student follow-up, eligibility checks, and institutional reporting. A paper register can work for a small class, but it requires repeated manual counting and makes it harder to produce class-wise, subject-wise, and date-range reports. A basic digital system can keep these records together and make them available to authorized teachers and students through a browser."),
        P("AttendEase is a responsive web application built with HTML, CSS, JavaScript, Python Flask, and a MySQL-compatible database. Teachers record attendance for a selected date, class, section, and subject. Students sign in separately and see only their own attendance and the timetable for their class section. The application also provides class and subject setup, reports, low-attendance indicators, email alerts, and a history of attendance changes."),
        H("1.2 Problem Statement"),
        P("Institutions that rely on paper registers or disconnected spreadsheets may encounter delayed summaries, inconsistent subject records, duplicate entry, and difficulty tracing corrections. Students may not have a convenient way to review their own records, while teachers need a reliable view of the correct class and subject before marking attendance. The project addresses these operational issues with a centralized browser-based workflow."),
        H("1.3 Objectives")]
    story += bullets([
        "Provide separate teacher and student sign-in paths with role-based access.",
        "Maintain student profiles and organize students by class, section, and roll number.",
        "Let a teacher record Present, Absent, or Late for a selected subject and date.",
        "Show attendance reports, export filtered results to CSV, and highlight rates below 75 percent.",
        "Provide a class-section timetable with lecture numbers, timings, teacher assignments, and lunch breaks.",
        "Show students their own attendance and class timetable in read-only form.",
        "Keep an audit record of new markings and later status changes.",
        "Attempt email alerts to saved student and guardian email addresses when a status changes to Absent or Late.",
    ])
    story += [H("1.4 Scope and Assumptions"),
        P("The system is designed for a small educational institution or a college demonstration. A teacher selects the class, section, subject, and date and manually confirms each student's status. The application does not use biometric, RFID, GPS, or face recognition hardware. It assumes that student and guardian contact information is entered correctly and that the teacher has an internet connection when using the hosted application."),
        P("The student portal is intentionally limited to the signed-in student's own attendance, percentage, and section timetable. Teacher accounts have the complete management interface. The Teachers directory stores teacher names and optional email addresses for subject assignment; the current application does not create separate login accounts for each teacher. Email delivery depends on configuring a provider. SMS sending has been removed from the application."),
        P("The user interface uses a 75 percent threshold for low-attendance warnings. Attendance percentage currently counts only records with status Present in the numerator; Late is included among marked sessions but does not increase the numerator. Institutions should confirm this policy before using the percentage for formal decisions.")]

    # Chapter 2
    story += [PageBreak(),chapter(2,"Literature Review"),H("2.1 Review of Existing Research Work"),
        P("Attendance management research includes manual registers, card-based identification, biometric recognition, mobile applications, and cloud-hosted web systems. Ali et al. review a range of attendance technologies, including RFID, barcode, biometric, and magnetic-stripe approaches, and discuss their application and implementation challenges [1]. This review shows that attendance automation is a broad design space rather than a single technique."),
        P("Khan, Yamazaki, and Sakamura describe an online, cost-conscious attendance approach using smartphones and cloud services [2]. Their work highlights the value of remote access and avoiding dedicated infrastructure, while also recognizing that cost and infrastructure choices involve trade-offs. Ardebili et al. review cloud-based attendance management research and discuss cloud infrastructure as a way to support storage and administrative processing [3]. These studies support the choice of a browser-accessible system for a small project, while leaving identity verification to the workflow chosen by the institution."),
        H("2.2 Comparison and Research Gap Identification"),
        P("Biometric and card-based approaches can automate identity capture, but may require devices, enrolment processes, maintenance, or physical infrastructure. A manually confirmed web workflow is less automated, yet can be implemented with common computers and phones. For this project's educational scope, the gap is not a new identity-recognition algorithm. The practical gap is the integration of class-section workflows, student-only visibility, timetable context, low-attendance summaries, and traceable corrections in one small browser application."),
    ]
    story += make_table("Table 1. Comparison of attendance management approaches",["Approach","Strengths","Constraints relevant to this project"],[
        ("Paper register","Low setup cost; familiar to staff","Manual totals, limited search, and no built-in student portal"),
        ("RFID or smart card","Fast check-in when cards and readers are deployed","Requires cards/readers and operational controls"),
        ("Biometric or face recognition","Automated identity matching can reduce manual entry","Needs sensors, enrolment, privacy safeguards, and error handling"),
        ("Browser-based teacher entry","Uses ordinary browser devices; supports reports and role access","Teacher still confirms attendance; internet and data quality matter"),
    ],[1.35*inch,2.45*inch,2.65*inch])
    story += [H("2.3 Relevance to AttendEase"),
        P("AttendEase follows the browser-based approach. It prioritizes the day-to-day school workflow: select class and section, choose the subject, mark students in roll-number order, and save. A student can then review a personal history without editing any record. Timetables, a low-attendance list, email attempts, and change history are related operational features around the core attendance record. This scope is appropriate for a semester project because each feature can be demonstrated using ordinary devices and sample data."),
        P("The system's cost advantage should be understood as avoiding dedicated attendance hardware. Hosting and database availability still depend on the selected service plans and quotas; a free educational deployment is suitable for a demonstration, not a production guarantee.")]

    # Chapter 3
    story += [PageBreak(),chapter(3,"Methodology"),H("3.1 System Architecture and Workflow"),
        P("The browser renders the user interface using HTML templates, CSS, and JavaScript. Flask handles HTTP requests, login sessions, authorization, validation, database operations, reporting, and optional email-provider calls. MySQL Connector/Python connects Flask to TiDB, which supports the MySQL protocol and common MySQL syntax [7]. The deployed service runs on Render as a Python web service using Gunicorn [8]. Source code is stored in GitHub and deployment is triggered by changes to the configured branch."),
        P("The database connection and email credentials are supplied through environment variables rather than being embedded in source code. The database setup script creates and upgrades tables when the service starts. The architecture is shown in Figure 1."),
        Image(str(ARCH_PATH),width=6.85*inch,height=6.85*inch*760/1500),P(figures[0][0],"CaptionReport"),
        H("3.1.1 Attendance Workflow"),P("The teacher signs in, chooses a date, class, section, and subject, then reviews the roll-number-sorted roster. The application validates the selected group and status values before saving. A new attendance record or a changed status is written to the audit log in the same database transaction. If a status changes to Absent or Late, the application attempts configured email delivery and records the provider result. Figure 2 summarizes this flow."),
        Image(str(FLOW_PATH),width=6.85*inch,height=6.85*inch*760/1500),P(figures[1][0],"CaptionReport"),
        H("3.2 Hardware and Software Specifications")]
    story += make_table("Table 2. Software and hardware specifications",["Layer","Technology or minimum requirement","Purpose"],[
        ("Client","Updated desktop or mobile browser; internet connection","Teacher and student access"),
        ("Frontend","HTML5, CSS, JavaScript, Jinja templates","Pages, forms, responsive layout, and browser interactions"),
        ("Application","Python 3, Flask, Gunicorn","Routes, session handling, validations, and production serving"),
        ("Database","TiDB Cloud Starter with MySQL protocol; MySQL Connector/Python","Persistent student, class, timetable, attendance, and log data"),
        ("Hosting/source","Render Web Service and GitHub repository","Public web deployment and version-controlled source"),
        ("Development machine","Windows 10/11, 4 GB RAM recommended, browser, Python environment","Local editing and browser-based development"),
    ],[1.2*inch,2.75*inch,2.5*inch])
    story += [H("3.3 Database Design"),
        P("The schema separates accounts from student profiles and attendance events. A student has a linked student-role account. Subjects belong to a class and may reference a teacher-directory entry. Attendance records reference a student, subject, date, status, and the user who marked the record. Class timetables store weekday periods for a class-section. Attendance audit rows preserve the previous and new status and the teacher account that changed it. Figure 3 shows the principal entities; Table 3 summarizes their purpose."),
        Image(str(ER_PATH),width=6.85*inch,height=6.85*inch*800/1500),P(figures[2][0],"CaptionReport")]
    story += make_table("Table 3. Core database entities and purpose",["Entity","Selected fields","Purpose"],[
        ("users","username, password_hash, role, student_id","Teacher and student authentication"),
        ("students","roll_no, full_name, class_name, section, date_of_birth, email, guardian_name, guardian_email","Student profile and class-section association"),
        ("teachers","full_name, email, active","Teacher directory used for subject assignment"),
        ("subjects","class_name, subject_name, teacher_id, active","Class subject and assigned teacher"),
        ("attendance","student_id, subject_id, attendance_date, status, marked_by, updated_at","Current status for one student, date, and subject"),
        ("class_timetable","class_name, section, weekday, period_type, lecture_number, subject_name, start_time, end_time, room","Weekly class-section schedule and lunch breaks"),
        ("attendance_audit_log","student_id, subject_id, attendance_date, previous_status, new_status, changed_by, changed_at","History of new markings and later changes"),
        ("notification_logs","student_id, attendance_date, subject_name, channel, recipient, delivery_status, details","Recent email delivery attempts"),
    ],[1.3*inch,3.25*inch,1.9*inch])
    story += [H("3.4 Methodology and Techniques"),
        P("The project uses an incremental module-based method. Requirements were translated into browser pages and Flask routes. The schema was created with migration checks so older databases can gain new columns and tables without intentionally deleting existing attendance. Jinja templates render server data, while JavaScript supports interactive controls such as class/subject selection and form behavior."),
        P("Parameterized SQL statements are used for database values. Passwords are stored as Werkzeug password hashes and checked during sign-in. Teacher and student sessions are separated by role; the request guard redirects student sessions away from teacher-only routes. Attendance writes and audit entries are grouped in a database transaction. Reports aggregate Present, Absent, and Late records for a selected date range and optional class, subject, and student filters."),
        P("Low-attendance percentage is calculated as Present records divided by marked sessions, multiplied by 100. The dashboard uses all available attendance records; the report page uses the selected date range. A student with no marked sessions has no percentage and is not presented as a below-threshold student."),
        H("3.5 Security and Privacy"),
        P("The application uses hashed passwords, session-based role checks, secure-cookie settings in production, and server-side validation for important fields. Environment variables hold database, mail-provider, and Flask secret values. Student routes query by the student identifier stored in the signed-in session rather than accepting a requested student identity from the page. The student interface is read-only."),
        P("The project remains a classroom-scale prototype. It does not currently include CSRF tokens on all forms, login rate limiting, individual accounts for every listed teacher, or a tested disaster-recovery process. Student date of birth and email information are personal data; only demonstration data should be used in screenshots, and real institutional deployment would require an approved privacy and backup plan.")]

    # Chapter 4
    story += [PageBreak(),chapter(4,"Modules and Functionality"),H("4.1 Roles and Authentication"),
        P("The public landing page offers separate teacher and student sign-in pages. The login handler verifies the submitted password against a stored hash and records the account role in the session. A student account is linked to one student profile. On a student's first login, the application can require a password change. The current deployment has one teacher/admin account with system-wide management access; teacher names in the Teachers directory are not separate login accounts."),
    ]
    story += make_table("Table 4. User roles and access matrix",["Capability","Teacher account","Student account"],[
        ("Manage student profiles, classes, sections, subjects, and timetables","Yes","No"),
        ("Mark or update attendance","Yes","No"),
        ("View reports, email attempts, and change history","Yes","No"),
        ("View personal attendance and class-section timetable","Yes","Yes, own account only"),
        ("Change own sign-in password","Yes","Yes"),
    ],[3.15*inch,1.5*inch,1.8*inch])
    story += [H("4.2 Student and Class Management"),
        P("Student profiles include roll number, full name, class, section, date of birth, student email, guardian name, and guardian email. Class sections can be created with a student count and filled using a bulk-entry form. Student lists can be searched, edited, and archived. The class-detail page shows a roster sorted by roll number, login username, subject assignments, and its timetable."),
        P("Student usernames are generated from a normalized student name and date of birth; duplicate names receive a disambiguating suffix. An initial password is created for first sign-in and the student is asked to replace it. The initial credential should be communicated privately and not included in a public report."),
        H("4.3 Teachers, Subjects and Timetable"),
        P("The Teachers page records a teacher's full name and optional email. The Subjects page associates a class and subject name with a teacher-directory entry. The timetable is configured separately for each class and section. Each lecture stores its weekday, lecture number, subject, start time, end time, and optional room. A lunch period uses the same day and time fields but does not require a lecture number or subject."),
        P("The teacher Overview reads the timetable for the current weekday. Each lecture row includes a Mark attendance link that opens the attendance page with date, class, section, and subject preselected. This is an in-application reminder; it does not send a browser push notification or phone alert. Students see a read-only timetable matched to their profile's class and section."),
        H("4.4 Attendance and Audit History"),
        P("The attendance form accepts a date, class, section, and subject. It displays active students in serial roll-number order with a status choice of Present, Absent, or Late. The database prevents duplicate records for the same student, date, and subject. Saving the same status again does not create a new audit event or trigger another absent/late email. A new mark or a changed status creates an audit entry with the prior status, new status, account, and timestamp."),
        P("The Change History page is teacher-only and displays recent events (up to 200). The previous status is shown as Not marked for an initial record. History tracking begins when the audit feature is deployed; it cannot reconstruct earlier changes that were not logged."),
        H("4.5 Reports, Alerts and Student Portal"),
        P("Reports can be filtered by date range, class, subject, and student. Results include present, absent, late, number of marked sessions, and the attendance percentage. A CSV download provides a portable report. Below-75-percent indicators appear in reports and the teacher Overview. A student sees a personal warning when their all-time rate is below the same threshold."),
        P("When a student's status changes to Absent or Late, the application attempts to email the saved guardian and student addresses. If both addresses match, it sends only one message. Provider configuration is optional and uses Google Apps Script, Resend, or SMTP environment variables. The notification page displays whether a provider is configured and recent delivery attempts. A provider acceptance result does not guarantee that the message reached the recipient's inbox."),
        P("The student dashboard shows the student's own attendance summary, class timetable, and attendance history. Students cannot edit attendance, access another student's profile, or open teacher management pages.")]
    story += make_table("Table 5. Modules, inputs and outputs",["Module","Main inputs","User-visible output"],[
        ("Authentication","Username and password","Teacher dashboard or student-only portal"),
        ("Student/class setup","Roll, name, class, section, DOB, email contacts","Class roster and student login"),
        ("Subject setup","Class, subject, assigned teacher","Subject list for attendance and timetable"),
        ("Timetable","Class-section, weekday, period type, lecture number, subject, time, room","Weekly schedule and Overview reminder"),
        ("Attendance","Date, class, section, subject, each student's status","Saved attendance and optional email"),
        ("Reports and history","Date range and report filters","Percentage, low-attendance flags, CSV, audit entries"),
    ],[1.35*inch,2.65*inch,2.45*inch])
    story += [H("4.6 System Screenshots"),P("The following representative screen captures show the project pages and their main fields. Names, email addresses, roll numbers, and attendance values in these illustrations are fictitious sample values. Replace them with institute-approved screenshots from the live application before final printing if the department requires actual deployment evidence.")]
    for idx,(filename,caption) in enumerate(screens):
        path=SCREEN_DIR/filename
        img=Image(str(path),width=6.55*inch,height=6.55*inch*900/1366)
        img.hAlign="CENTER"
        story.append(KeepTogether([img,P(f"Figure {idx+4}. {caption} (sample values)","CaptionReport")]))
        if idx%2==1 and idx<len(screens)-1:
            story.append(PageBreak())

    # Results and discussion
    story += [PageBreak(),Paragraph("RESULTS AND DISCUSSION",styles["ChapterTitle"]),
        P("AttendEase provides an integrated workflow for teacher-confirmed attendance in a browser. The system screens present class and subject context before the teacher saves status values. Reports and CSV output provide a way to review stored records. The timetable reminder opens an attendance form with its class-section and subject preselected. Role checks restrict student sessions to their own attendance and timetable."),
        P("The application combines operational conveniences that are often separated in a simple register: class-section rosters, subject assignment, weekly timetable, low-attendance indicators, email attempts, and audit history. These features support follow-up and make corrections more traceable. The email log records provider results but cannot verify recipient inbox delivery."),
        P("The deployed configuration uses a Render Python web service and a TiDB Cloud database. The Render service can sleep on a free plan when inactive, so the first request after inactivity may take longer. TiDB and hosting quotas or service limits can change. The current setup is suitable for demonstration and educational evaluation; it should not be described as a high-availability production service."),
        P("No load-test throughput, error-rate, or performance benchmark is claimed in this report. The following functional demonstration scenarios describe the expected behavior for a reviewer and should be checked by the project team using its live site before the viva."),
    ]
    story += make_table("Table 6. Functional demonstration scenarios and expected results",["Scenario","Steps","Expected result"],[
        ("Teacher sign-in","Use teacher portal with valid credentials","Teacher Overview appears; teacher navigation is available"),
        ("Student privacy","Sign in as one student and view portal","Only that student's records and section timetable are shown"),
        ("Class and subject","Create a class-section and add a teacher-assigned subject","Section appears in class, subject, and timetable setup"),
        ("Attendance mark","Choose date, class, section, subject; save statuses","Roster is roll-sorted; records appear in report"),
        ("Attendance correction","Change one saved status and open Change History","Prior and new status, account, and time appear"),
        ("Low-attendance report","Open Overview or filtered Reports with sample records","Rates below 75 percent receive a warning"),
        ("Timetable shortcut","Open Overview on a scheduled weekday and click Mark attendance","Attendance form opens with schedule values selected"),
        ("Email attempt","Configure provider and mark a record Absent or Late","Attempt appears in notification log; inbox delivery must be checked separately"),
        ("CSV export","Apply report filters and export","CSV downloads with selected report rows"),
    ],[1.2*inch,2.45*inch,2.8*inch])
    story += make_table("Table 7. Proposed team responsibilities",["Member","Name","Module responsibility"],[
        ("1 - Team Leader","Gaurav Singh","Login and roles; coordination and integration"),
        ("2","Abhishek Kumar Bishawakarma","Student profiles, class sections, and student accounts"),
        ("3","Anish Pal","Attendance marking and change history"),
        ("4","Mayank Srivastav","Teacher directory, subjects, timetable, and reminder"),
        ("5","Abhay Kumar Gupta","Reports, low-attendance alerts, CSV, email, and demo preparation"),
    ],[1.05*inch,2.35*inch,3.05*inch])
    story += [Paragraph("CONCLUSION",styles["ChapterTitle"]),
        P("AttendEase demonstrates a role-based student attendance management system using a browser frontend, Flask application layer, and a MySQL-compatible database. Teachers can manage class data and record attendance by date, subject, class, and section. Students have a restricted view of personal records and the timetable for their own section. Reports, low-attendance warnings, optional email attempts, and audit history extend the core attendance workflow."),
        P("The project meets the scope of a B.Tech third-semester minor project by connecting user-interface design, database schema, server-side validation, role-based access, and hosted deployment. Before institutional use beyond a demonstration, the team should review the security, backup, privacy, account-management, and hosting limitations listed in this report."),
        Paragraph("FUTURE SCOPE",styles["ChapterTitle"]),
    ]
    story += bullets([
        "Create separate teacher accounts with class- and subject-specific permissions.",
        "Add CSRF protection, login throttling, password-reset workflow, and stronger account recovery controls.",
        "Add approved database backups, restore procedures, and migration rollback guidance.",
        "Allow timetable editing, import from a spreadsheet, and term/holiday calendars.",
        "Make the low-attendance threshold configurable and confirm whether Late should count as present for institutional policy.",
        "Add optional browser push reminders or scheduled emails with explicit consent and configurable delivery schedules.",
        "Add report pagination, print-friendly class sheets, and audit-history filters by class, student, subject, and date.",
        "Conduct usability, accessibility, security, and load testing before any real institutional deployment.",
        "Consider QR or RFID check-in only if the institution needs automation and can support the required devices and privacy safeguards.",
    ])
    story += [Paragraph("REFERENCES",styles["ChapterTitle"])]
    refs = [
        "[1] N. S. Ali, A. H. Alhilali, H. D. Rjeib, H. Alsharqi, and B. Al-Sadawi, \"Automated attendance management systems: systematic literature review,\" <i>International Journal of Technology Enhanced Learning</i>, vol. 14, no. 1, pp. 37-65, 2022, doi: 10.1504/IJTEL.2022.120559.",
        "[2] M. F. F. Khan, T. Yamazaki, and K. Sakamura, \"Design and implementation of an online and cost-effective attendance management system using smartphones and cloud services,\" in <i>Proc. 18th EAI International Conference on Mobile and Ubiquitous Systems: Computing, Networking and Services (MobiQuitous 2021)</i>, 2022, doi: 10.1007/978-3-030-94822-1_42.",
        "[3] A. Ardebili, A. Latifian, C. F. Aziz, R. H. BinSaeed, S. M. Alizadeh, and E. V. Kostyrin, \"A comprehensive and systematic literature review on the employee attendance management systems based on cloud computing,\" <i>Journal of Management &amp; Organization</i>, vol. 29, no. 4, pp. 679-696, 2023, doi: 10.1017/jmo.2022.63.",
        "[4] Pallets Projects, \"Quickstart, Flask Documentation,\" online. Available: https://flask.palletsprojects.com/en/stable/quickstart/. Accessed: Nov. 19, 2026.",
        "[5] Python Software Foundation, \"The Python Tutorial,\" online. Available: https://docs.python.org/3/tutorial/. Accessed: Nov. 19, 2026.",
        "[6] Oracle, \"MySQL Connector/Python Developer Guide: Connecting to MySQL Using Connector/Python,\" online. Available: https://dev.mysql.com/doc/connector-python/en/connector-python-example-connecting.html. Accessed: Nov. 19, 2026.",
        "[7] PingCAP, \"MySQL Compatibility, TiDB Documentation,\" online. Available: https://docs.pingcap.com/tidbcloud/mysql-compatibility/. Accessed: Nov. 19, 2026.",
        "[8] Render, \"Deploy a Flask App on Render,\" Render Documentation, online. Available: https://render.com/docs/deploy-flask. Accessed: Nov. 19, 2026.",
    ]
    for ref in refs:
        story.append(P(ref,"Reference"))
    story += [Spacer(1,8),P("Project source code: private GitHub repository maintained by the project team. Public website: https://attendance-management-system-02qd.onrender.com/ . Access to the private source repository requires an invitation.","BodySmall")]
    return story

def build_pdf(page_map, front_pages):
    doc=base_doc(front_pages)
    story=build_story(page_map)
    doc.build(story,onFirstPage=page_footer,onLaterPages=page_footer)

def read_pdf_pages():
    with pdfplumber.open(PDF_PATH) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]

def locate_pages(pages, searches, body_start):
    normalized=[normalize(p) for p in pages]
    result={}
    for label,search,_level in searches:
        target=normalize(search)
        physical=next((idx+1 for idx,text in enumerate(normalized) if idx+1 >= body_start and target in text),None)
        result[search]=str(physical-body_start+1) if physical and physical>=body_start else (str(physical) if physical else "-")
    return result

def main():
    prepare_assets()
    # First pass creates the full layout so printed page numbers can be assigned from the PDF itself.
    build_pdf({},6)
    pages=read_pdf_pages()
    norm=[normalize(p) for p in pages]
    body_start=next((i+1 for i,p in enumerate(pages)
                     if any(line.strip().casefold()=="chapter 1 - introduction" for line in p.splitlines())),7)
    toc_map=locate_pages(pages,toc_items,body_start)
    figure_searches=[(label,label.split(" (illustrative screen")[0],0) for label,_ in figures]
    fig_map=locate_pages(pages,figure_searches,body_start)
    # Keep the full list label as the lookup key while locating the rendered caption prefix.
    fig_map.update({label:fig_map.get(search,"-") for label,search,_ in figure_searches})
    table_searches=[(t,t,0) for t in tables_list]
    table_map=locate_pages(pages,table_searches,body_start)
    all_map={**toc_map,**fig_map,**table_map}
    build_pdf(all_map,body_start-1)
    final_pages=read_pdf_pages()
    final_norm=[normalize(p) for p in final_pages]
    final_body=next((i+1 for i,p in enumerate(final_pages)
                     if any(line.strip().casefold()=="chapter 1 - introduction" for line in p.splitlines())),None)
    if final_body is None:
        raise RuntimeError("Could not locate Chapter 1 in the generated report.")
    print(f"Built {PDF_PATH} ({len(final_pages)} pages; body starts on printed page 1, physical page {final_body}).")
    print("Figures:",len(figures),"Tables:",len(tables_list))

if __name__ == "__main__":
    main()
