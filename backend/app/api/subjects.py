from __future__ import annotations

from datetime import date

from flask import Blueprint, g, request
from marshmallow import RAISE, fields, validate

from ..extensions import db
from ..models import Department, StaffSubjectAssignment, Subject
from ..security import roles_required
from ..services.access import staff_assignment_query, staff_profile_for, student_profile_for
from ..services.audit import record_audit
from ..services.http import fail, success
from ..schemas import StrictSchema


subjects_bp = Blueprint("subjects", __name__)


class SubjectSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    department_id = fields.UUID(required=True)
    code = fields.String(required=True, validate=validate.Length(min=1, max=32))
    name = fields.String(required=True, validate=validate.Length(min=1, max=160))
    credits = fields.Integer(load_default=0, validate=validate.Range(min=0, max=40))


def serialize_subject(subject):
    return {"id": str(subject.id), "department_id": str(subject.department_id), "department": subject.department.name, "code": subject.code, "name": subject.name, "credits": subject.credits}


@subjects_bp.get("/subjects")
@roles_required("Admin", "Staff", "Student")
def list_subjects():
    query = Subject.query
    if g.current_user.role == "Staff":
        staff = staff_profile_for(g.current_user)
        if not staff:
            return success([])
        assigned_ids = staff_assignment_query(staff.id, date.today()).with_entities(StaffSubjectAssignment.subject_id)
        query = query.filter(Subject.id.in_(assigned_ids))
    elif g.current_user.role == "Student":
        student = student_profile_for(g.current_user)
        if not student:
            return success([])
        assigned_ids = db.session.query(StaffSubjectAssignment.subject_id).filter_by(section_id=student.section_id)
        query = query.filter(Subject.id.in_(assigned_ids))
    return success([serialize_subject(subject) for subject in query.order_by(Subject.code).all()])


@subjects_bp.post("/admin/subjects")
@roles_required("Admin")
def create_subject():
    payload = SubjectSchema().load_object(request.get_json(silent=False) or {})
    if Department.query.filter_by(id=payload["department_id"]).one_or_none() is None:
        return fail("DEPARTMENT_NOT_FOUND", "The department was not found.", 404)
    if Subject.query.filter_by(code=payload["code"]).one_or_none():
        return fail("SUBJECT_CODE_EXISTS", "That subject code is already in use.", 409)
    subject = Subject(**payload)
    db.session.add(subject)
    db.session.flush()
    record_audit("subject_created", "subjects", subject.id, after={"code": subject.code, "name": subject.name})
    db.session.commit()
    return success(serialize_subject(subject), 201)
