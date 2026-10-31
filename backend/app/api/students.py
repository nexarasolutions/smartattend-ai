from __future__ import annotations

from flask import Blueprint, g, request
from marshmallow import RAISE, fields, validate
from sqlalchemy import case, func

from ..extensions import db
from ..models import AttendanceRecord, ClassSection, ClassSession, Department, Student, Subject, User, utcnow
from ..security import roles_required
from ..services.access import scoped_student_query, student_profile_for
from ..services.audit import record_audit
from ..services.http import fail, success
from ..services.serialization import student_record
from ..schemas import StrictSchema


students_bp = Blueprint("students", __name__)


class StudentProvisionSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    user_id = fields.UUID(required=True)
    department_id = fields.UUID(required=True)
    section_id = fields.UUID(required=True)
    roll_number = fields.String(required=True, validate=validate.Length(min=1, max=48))
    academic_year = fields.Integer(required=True, validate=validate.Range(min=1, max=12))


class StudentUpdateSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    department_id = fields.UUID(load_default=None, allow_none=True)
    section_id = fields.UUID(load_default=None, allow_none=True)
    academic_year = fields.Integer(load_default=None, allow_none=True, validate=validate.Range(min=1, max=12))
    status = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(["active", "inactive"]))


@students_bp.get("/students")
@roles_required("Admin", "Staff", "Student")
def list_students():
    query = scoped_student_query(g.current_user).order_by(Student.roll_number)
    q = request.args.get("q", "").strip()
    if q:
        query = query.join(User).filter(db.or_(Student.roll_number.ilike(f"%{q}%"), User.display_name.ilike(f"%{q}%")))
    department_id = request.args.get("department_id")
    if department_id:
        query = query.filter_by(department_id=department_id)
    rows = query.limit(500).all()
    return success([student_record(row) for row in rows])


@students_bp.get("/students/me")
@roles_required("Student")
def my_student_profile():
    student = student_profile_for(g.current_user)
    if student is None:
        return fail("STUDENT_PROFILE_NOT_FOUND", "Your student profile has not been provisioned.", 404)
    return success(student_record(student))


@students_bp.get("/students/me/attendance-summary")
@roles_required("Student")
def my_attendance_summary():
    student = student_profile_for(g.current_user)
    if student is None:
        return fail("STUDENT_PROFILE_NOT_FOUND", "Your student profile has not been provisioned.", 404)

    attended_count = func.coalesce(
        func.sum(case((AttendanceRecord.status.in_(("Present", "Late")), 1), else_=0)),
        0,
    )
    rows = (
        db.session.query(
            Subject.id,
            Subject.code,
            Subject.name,
            func.count(ClassSession.id).label("classes_held"),
            attended_count.label("classes_attended"),
        )
        .join(ClassSession, ClassSession.subject_id == Subject.id)
        .outerjoin(
            AttendanceRecord,
            db.and_(
                AttendanceRecord.session_id == ClassSession.id,
                AttendanceRecord.student_id == student.id,
            ),
        )
        .filter(
            ClassSession.section_id == student.section_id,
            ClassSession.starts_at <= utcnow(),
            ClassSession.status != "cancelled",
        )
        .group_by(Subject.id, Subject.code, Subject.name)
        .order_by(Subject.code)
        .all()
    )
    subjects = []
    for row in rows:
        held = int(row.classes_held)
        attended = int(row.classes_attended)
        subjects.append({
            "subject_id": str(row.id),
            "subject_code": row.code,
            "subject": row.name,
            "classes_held": held,
            "classes_attended": attended,
            "attendance_percentage": round(attended * 100 / held, 1) if held else None,
        })
    total_held = sum(item["classes_held"] for item in subjects)
    total_attended = sum(item["classes_attended"] for item in subjects)
    return success({
        "subjects": subjects,
        "overall": {
            "classes_held": total_held,
            "classes_attended": total_attended,
            "attendance_percentage": round(total_attended * 100 / total_held, 1) if total_held else None,
        },
    })


@students_bp.get("/students/<uuid:student_id>")
@roles_required("Admin", "Staff", "Student")
def get_student(student_id):
    student = scoped_student_query(g.current_user).filter_by(id=student_id).one_or_none()
    if student is None:
        return fail("STUDENT_NOT_FOUND", "The student is unavailable in your authorized scope.", 404)
    return success(student_record(student))


@students_bp.post("/admin/students")
@roles_required("Admin")
def provision_student():
    payload = StudentProvisionSchema().load_object(request.get_json(silent=False) or {})
    user = User.query.filter_by(id=payload["user_id"]).one_or_none()
    department = Department.query.filter_by(id=payload["department_id"]).one_or_none()
    section = ClassSection.query.filter_by(id=payload["section_id"]).one_or_none()
    if not user or not department or not section:
        return fail("REFERENCE_NOT_FOUND", "A user, department or class section was not found.", 404)
    if section.department_id != department.id or section.academic_year != payload["academic_year"]:
        return fail("SECTION_SCOPE_MISMATCH", "The student department/year must match the selected class section.", 400)
    if user.status == "disabled" or (user.role not in {None, "Student"}):
        return fail("ROLE_CONFLICT", "Only an unassigned or Student account can be provisioned as a student.", 409)
    existing = Student.query.filter(db.or_(Student.user_id == user.id, Student.roll_number == payload["roll_number"])).first()
    if existing:
        return fail("STUDENT_ALREADY_EXISTS", "That account or roll number is already attached to a student profile.", 409)
    student = Student(**payload)
    user.role = "Student"
    user.status = "active"
    db.session.add(student)
    db.session.flush()
    record_audit("student_provisioned", "students", student.id, after={"roll_number": student.roll_number, "section_id": str(student.section_id)})
    db.session.commit()
    return success(student_record(student), 201)


@students_bp.patch("/admin/students/<uuid:student_id>")
@roles_required("Admin")
def update_student(student_id):
    payload = StudentUpdateSchema().load_object(request.get_json(silent=False) or {})
    student = Student.query.filter_by(id=student_id).one_or_none()
    if student is None:
        return fail("STUDENT_NOT_FOUND", "The student was not found.", 404)
    before = {"department_id": str(student.department_id), "section_id": str(student.section_id), "academic_year": student.academic_year, "status": student.status}
    for key, value in payload.items():
        if value is not None:
            setattr(student, key, value)
    section = ClassSection.query.get(student.section_id)
    if section is None or section.department_id != student.department_id or section.academic_year != student.academic_year:
        db.session.rollback()
        return fail("SECTION_SCOPE_MISMATCH", "The student department/year must match the selected class section.", 400)
    record_audit("student_profile_updated", "students", student.id, before=before, after={"department_id": str(student.department_id), "section_id": str(student.section_id), "academic_year": student.academic_year, "status": student.status})
    db.session.commit()
    return success(student_record(student))
