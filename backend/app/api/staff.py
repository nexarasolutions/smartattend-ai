from __future__ import annotations

from datetime import date

from flask import Blueprint, g, request
from marshmallow import RAISE, fields, validate

from ..extensions import db
from ..models import ClassSection, Staff, StaffSubjectAssignment, Subject, User
from ..security import roles_required
from ..services.access import staff_assignment_query, staff_profile_for
from ..services.audit import record_audit
from ..services.http import fail, success
from ..services.serialization import staff_record
from ..schemas import StrictSchema


staff_bp = Blueprint("staff", __name__)


class StaffProvisionSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    user_id = fields.UUID(required=True)
    department_id = fields.UUID(required=True)
    staff_number = fields.String(required=True, validate=validate.Length(min=1, max=48))


class AssignmentSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    staff_id = fields.UUID(required=True)
    subject_id = fields.UUID(required=True)
    section_id = fields.UUID(required=True)
    valid_from = fields.Date(load_default=None, allow_none=True)
    valid_to = fields.Date(load_default=None, allow_none=True)


@staff_bp.get("/staff")
@roles_required("Admin", "Staff")
def list_staff():
    if g.current_user.role == "Staff":
        own = staff_profile_for(g.current_user)
        rows = [own] if own else []
    else:
        rows = Staff.query.order_by(Staff.staff_number).limit(500).all()
    return success([staff_record(row) for row in rows])


@staff_bp.get("/staff/me/assignments")
@roles_required("Staff")
def my_assignments():
    staff = staff_profile_for(g.current_user)
    if staff is None:
        return fail("STAFF_PROFILE_NOT_FOUND", "Your staff profile has not been provisioned.", 404)
    rows = staff_assignment_query(staff.id, date.today()).all()
    return success([{"id": str(item.id), "subject_id": str(item.subject_id), "subject": item.subject.name, "subject_code": item.subject.code, "section_id": str(item.section_id), "section": item.section.code, "valid_from": item.valid_from.isoformat() if item.valid_from else None, "valid_to": item.valid_to.isoformat() if item.valid_to else None} for item in rows])


@staff_bp.post("/admin/staff")
@roles_required("Admin")
def provision_staff():
    payload = StaffProvisionSchema().load_object(request.get_json(silent=False) or {})
    user = User.query.filter_by(id=payload["user_id"]).one_or_none()
    if user is None:
        return fail("USER_NOT_FOUND", "The account must sign in before it can be provisioned.", 404)
    if user.status == "disabled" or user.role not in {None, "Staff"}:
        return fail("ROLE_CONFLICT", "Only an unassigned or Staff account can be provisioned as Staff.", 409)
    if Staff.query.filter(db.or_(Staff.user_id == user.id, Staff.staff_number == payload["staff_number"])).first():
        return fail("STAFF_ALREADY_EXISTS", "That account or staff number is already attached to a staff profile.", 409)
    staff = Staff(**payload)
    user.role = "Staff"
    user.status = "active"
    db.session.add(staff)
    db.session.flush()
    record_audit("staff_provisioned", "staff", staff.id, after={"staff_number": staff.staff_number, "department_id": str(staff.department_id)})
    db.session.commit()
    return success(staff_record(staff), 201)


@staff_bp.post("/admin/staff-subject-assignments")
@roles_required("Admin")
def create_assignment():
    payload = AssignmentSchema().load_object(request.get_json(silent=False) or {})
    staff = Staff.query.filter_by(id=payload["staff_id"], status="active").one_or_none()
    subject = Subject.query.filter_by(id=payload["subject_id"]).one_or_none()
    section = ClassSection.query.filter_by(id=payload["section_id"]).one_or_none()
    if not staff or not subject or not section:
        return fail("REFERENCE_NOT_FOUND", "A staff member, subject or section was not found.", 404)
    if staff.department_id != subject.department_id or section.department_id != subject.department_id:
        return fail("ASSIGNMENT_SCOPE_MISMATCH", "Staff, subject and class section must belong to the same department.", 400)
    if payload.get("valid_from") and payload.get("valid_to") and payload["valid_to"] < payload["valid_from"]:
        return fail("INVALID_ASSIGNMENT_DATES", "Assignment end date cannot be before its start date.", 400)
    assignment = StaffSubjectAssignment(**payload)
    db.session.add(assignment)
    db.session.flush()
    record_audit("staff_subject_assignment_created", "staff_subject_assignments", assignment.id, after={"staff_id": str(staff.id), "subject_id": str(subject.id), "section_id": str(section.id)})
    db.session.commit()
    return success({"id": str(assignment.id), "staff_id": str(staff.id), "subject_id": str(subject.id), "section_id": str(section.id)}, 201)
