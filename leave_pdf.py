import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_leave_pdf(leave, documents):
    """Leave application ka PDF bytes return karta hai."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"Leave application #{leave['id']}", author="AttendEase",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica", fontSize=11, leading=16)
    title = ParagraphStyle("title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=18, spaceAfter=10)

    def para(text):
        return Paragraph(text, body)

    def fmt(d):
        return d.strftime("%d %b %Y") if d else "-"

    days = (leave["to_date"] - leave["from_date"]).days + 1
    reason_html = escape(leave["reason"]).replace("\n", "<br/>")
    section = f" / {escape(leave['section'])}" if leave.get("section") else ""
    docs_text = ", ".join(escape(d["filename"]) for d in documents) if documents else "None"

    story = [
        Paragraph("LEAVE APPLICATION", title),
        para(f"Date: {fmt(leave['created_at'])}<br/>Status: {escape(leave['status'])}"),
        Spacer(1, 10),
        para(f"To,<br/>The Class Teacher / Principal<br/>Class {escape(leave['class_name'])}{section}"),
        Spacer(1, 10),
        para(f"<b>Subject: Application for {escape(leave['leave_type'])}</b>"),
        Spacer(1, 8),
        para("Respected Sir/Madam,"),
        Spacer(1, 6),
        para(f"I, <b>{escape(leave['full_name'])}</b> (Roll No. {escape(leave['roll_no'])}), kindly request you to "
             f"grant leave from <b>{fmt(leave['from_date'])}</b> to <b>{fmt(leave['to_date'])}</b> ({days} day(s))."),
        Spacer(1, 8),
        para("<b>Reason:</b>"),
        Spacer(1, 4),
        para(reason_html),
        Spacer(1, 14),
    ]

    rows = [
        ["Student name", leave["full_name"]],
        ["Roll number", leave["roll_no"]],
        ["Class / Section", leave["class_name"] + (f" / {leave['section']}" if leave.get("section") else "")],
        ["Date of birth", fmt(leave.get("date_of_birth"))],
        ["Parent / Guardian", leave.get("guardian_name") or "-"],
        ["Leave type", leave["leave_type"]],
        ["Duration", f"{fmt(leave['from_date'])} to {fmt(leave['to_date'])}"],
    ]
    table = Table([[Paragraph(f"<b>{escape(k)}</b>", body), Paragraph(escape(str(v)), body)] for k, v in rows],
                  colWidths=[55 * mm, 105 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f3f3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [table, Spacer(1, 12), para(f"Documents attached: {docs_text}")]

    if leave.get("teacher_remark"):
        story += [Spacer(1, 6), para(f"<b>Teacher remark:</b> {escape(leave['teacher_remark'])}")]

    story += [
        Spacer(1, 16),
        para("Thanking you,<br/>Yours faithfully,"),
        Spacer(1, 50),
    ]
    sign = Table([["Student signature", "Parent / Guardian signature", "Teacher / Principal"]],
                 colWidths=[52 * mm, 60 * mm, 52 * mm])
    sign.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(sign)

    doc.build(story)
    return buffer.getvalue()


if __name__ == "__main__":
    sample = {
        "id": 7, "full_name": "Rahul Sharma", "roll_no": "12", "class_name": "10", "section": "A",
        "date_of_birth": datetime(2010, 5, 4).date(), "guardian_name": "Mr. Sharma",
        "leave_type": "Sick leave", "reason": "Fever aur doctor ne rest bataya hai.\nDoctor ka certificate attached hai.",
        "from_date": datetime(2026, 11, 21).date(), "to_date": datetime(2026, 11, 23).date(),
        "status": "Approved", "teacher_remark": "Get well soon & take rest <b>",
        "created_at": datetime(2026, 11, 20, 10, 30),
    }
    docs = [{"filename": "doctor_certificate.pdf"}]
    data = build_leave_pdf(sample, docs)
    open("sample_leave.pdf", "wb").write(data)
    print("bytes:", len(data), data[:5])
