from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import Any, cast
from xml.sax.saxutils import escape

from flask import Blueprint, Response, g, request
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import AttendanceRecord, ClassSession, MLPrediction, Staff, Student
from ..security import roles_required
from ..services.access import scoped_session_query, scoped_student_query
from ..services.audit import record_audit
from ..services.http import fail, success
from ..services.serialization import attendance_record


reports_bp = Blueprint("reports", __name__)


def _scoped_attendance():
    sessions = scoped_session_query(g.current_user).with_entities(ClassSession.id)
    query = AttendanceRecord.query.filter(AttendanceRecord.session_id.in_(sessions))
    if request.args.get("department_id"):
        query = query.join(Student).filter(Student.department_id == request.args["department_id"])
    return query.options(
        joinedload(cast(Any, AttendanceRecord.student)).joinedload(cast(Any, Student.user)),
        joinedload(cast(Any, AttendanceRecord.student)).joinedload(cast(Any, Student.department)),
        joinedload(cast(Any, AttendanceRecord.session)).joinedload(cast(Any, ClassSession.subject)),
        joinedload(cast(Any, AttendanceRecord.session)).joinedload(cast(Any, ClassSession.section)),
    )


def _attendance_pct(present: int, total: int) -> float | None:
    return round(present * 100 / total, 2) if total else None


def _records_by_student(rows):
    result = defaultdict(list)
    for row in rows:
        result[row.student_id].append(row)
    return result


@reports_bp.get("/reports/summary")
@roles_required("Admin", "Staff")
def report_summary():
    rows = _scoped_attendance().limit(100000).all()
    totals = {"Present": 0, "Absent": 0, "Late": 0}
    departments = defaultdict(lambda: {"total": 0, "present": 0})
    years = defaultdict(lambda: {"total": 0, "present": 0})
    subjects = defaultdict(lambda: {"total": 0, "present": 0})
    student_counts = defaultdict(lambda: {"name": "", "roll_number": "", "department": "", "percentage": 0.0, "total": 0, "present": 0})
    for row in rows:
        is_present = row.status in {"Present", "Late"}
        totals[row.status] += 1
        department = row.student.department.name
        year = str(row.student.academic_year)
        subject = row.session.subject.name
        for bucket, key in ((departments, department), (years, year), (subjects, subject)):
            bucket[key]["total"] += 1
            bucket[key]["present"] += int(is_present)
        student_item = student_counts[row.student_id]
        student_item.update({"name": row.student.user.display_name, "roll_number": row.student.roll_number, "department": department})
        student_item["total"] += 1
        student_item["present"] += int(is_present)

    department_rows = [{"department": key, "attendance_percentage": _attendance_pct(value["present"], value["total"]), "records": value["total"]} for key, value in sorted(departments.items())]
    year_rows = [{"academic_year": int(key), "attendance_percentage": _attendance_pct(value["present"], value["total"]), "records": value["total"]} for key, value in sorted(years.items(), key=lambda item: int(item[0]))]
    subject_rows = [{"subject": key, "attendance_percentage": _attendance_pct(value["present"], value["total"]), "records": value["total"]} for key, value in sorted(subjects.items())]
    below_threshold = sum(1 for value in student_counts.values() if value["total"] and (value["present"] / value["total"] * 100) < 75)

    scoped_students = scoped_student_query(g.current_user).with_entities(Student.id)
    predictions = MLPrediction.query.filter(MLPrediction.student_id.in_(scoped_students)).all()
    risk_counts = defaultdict(int)
    for prediction in predictions:
        risk_counts[prediction.risk_category] += 1

    result = {
        "total_records": len(rows),
        "present": totals["Present"],
        "absent": totals["Absent"],
        "late": totals["Late"],
        "attendance_percentage": _attendance_pct(totals["Present"] + totals["Late"], len(rows)),
        "scope": "all_departments" if g.current_user.role == "Admin" else "assigned_subjects_only",
        "department_breakdown": department_rows,
        "year_breakdown": year_rows,
        "subject_analytics": subject_rows,
        "low_attendance_students_below_75": below_threshold,
        "prediction_analytics": {"persisted_predictions": len(predictions), "risk_categories": dict(sorted(risk_counts.items()))},
    }
    if g.current_user.role == "Admin":
        result["total_students"] = Student.query.filter_by(status="active").count()
        result["total_staff"] = Staff.query.filter_by(status="active").count()
    return success(result)


@reports_bp.get("/reports/low-attendance")
@roles_required("Admin", "Staff")
def low_attendance():
    try:
        threshold = float(request.args.get("threshold", "75"))
    except ValueError:
        return fail("INVALID_THRESHOLD", "Threshold must be numeric and between 0 and 100.", 400)
    if not 0 <= threshold <= 100:
        return fail("INVALID_THRESHOLD", "Threshold must be numeric and between 0 and 100.", 400)
    rows = _scoped_attendance().limit(100000).all()
    per_student = _records_by_student(rows)
    result = []
    students = {student.id: student for student in scoped_student_query(g.current_user).all()}
    for student_id, records in per_student.items():
        student = students.get(student_id)
        if student is None:
            continue
        present = sum(record.status in {"Present", "Late"} for record in records)
        percentage = _attendance_pct(present, len(records))
        if percentage is not None and percentage < threshold:
            result.append({"student_id": str(student.id), "name": student.user.display_name, "roll_number": student.roll_number, "department": student.department.name, "attendance_percentage": percentage, "records": len(records)})
    return success(sorted(result, key=lambda item: item["attendance_percentage"]))


def _export_rows():
    rows = _scoped_attendance().order_by(AttendanceRecord.recorded_at.desc()).limit(10000).all()
    result = [attendance_record(record) for record in rows]
    record_audit("attendance_report_exported", "reports", None, after={"format": "csv" if request.path.endswith(".csv") else "pdf", "row_count": len(result), "scope": g.current_user.role})
    db.session.commit()
    return result


@reports_bp.get("/reports/attendance.csv")
@roles_required("Admin", "Staff")
def attendance_csv():
    rows = _export_rows()
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["record_id", "student", "roll_number", "subject", "section", "session_start", "status", "source", "recorded_at"])
    for item in rows:
        writer.writerow([item["id"], item["student"], item["roll_number"], item["subject"], item["section"], item["date"], item["status"], item["source"], item["recorded_at"]])
    response = Response(buffer.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="smartattend-attendance.csv"'
    response.headers["Cache-Control"] = "no-store"
    return response


@reports_bp.get("/reports/attendance.pdf")
@roles_required("Admin", "Staff")
def attendance_pdf():
    rows = _export_rows()
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(letter), leftMargin=0.42 * inch, rightMargin=0.42 * inch, topMargin=0.45 * inch, bottomMargin=0.45 * inch, title="SmartAttend attendance report")
    styles = getSampleStyleSheet()
    story = [Paragraph("SmartAttend AI · Attendance report", styles["Title"]), Paragraph(f"{len(rows)} authorized records · generated from the Manus-managed application database", styles["BodyText"]), Spacer(1, 12)]
    table_rows = [["Student", "Roll number", "Subject", "Section", "Session (UTC)", "Status", "Source"]]
    for item in rows:
        table_rows.append([escape(item["student"]), escape(item["roll_number"]), escape(item["subject"]), escape(item["section"]), escape(item["date"] or ""), escape(item["status"]), escape(item["source"])])
    table = Table(table_rows, repeatRows=1, colWidths=[1.55 * inch, 1.0 * inch, 1.45 * inch, 0.72 * inch, 2.05 * inch, 0.75 * inch, 0.75 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#192d4a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8dfeb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6fb")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    document.build(story)
    response = Response(output.getvalue(), mimetype="application/pdf")
    response.headers["Content-Disposition"] = 'attachment; filename="smartattend-attendance.pdf"'
    response.headers["Cache-Control"] = "no-store"
    return response
