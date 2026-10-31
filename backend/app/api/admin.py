from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from flask import Blueprint, current_app, g, request
from marshmallow import RAISE, fields, validate
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import AttendanceCorrection, AttendanceRecord, AuditLog, BootstrapState, ClassSection, ClassSession, Classroom, Department, DeviceEnrollmentToken, DeviceEvent, MLPrediction, PiDevice, Staff, Student, User, utcnow
from ..security import request_identity, roles_required
from ..schemas import StrictSchema
from ..services.audit import record_audit
from ..services.http import fail, success
from ..services.serialization import iso, user_record


admin_bp = Blueprint("admin", __name__)


class UserRoleSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    role = fields.String(required=True, validate=validate.OneOf(["Student", "Staff", "Admin"]))
    status = fields.String(load_default="active", validate=validate.OneOf(["active", "disabled", "pending"]))


class DepartmentSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    code = fields.String(required=True, validate=validate.Length(min=2, max=24))
    name = fields.String(required=True, validate=validate.Length(min=2, max=120))


class ClassroomSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    building = fields.String(required=True, validate=validate.Length(min=1, max=100))
    room_code = fields.String(required=True, validate=validate.Length(min=1, max=32))
    description = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=200))


class SectionSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    department_id = fields.UUID(required=True)
    classroom_id = fields.UUID(load_default=None, allow_none=True)
    code = fields.String(required=True, validate=validate.Length(min=1, max=32))
    academic_year = fields.Integer(required=True, validate=validate.Range(min=1, max=12))
    term = fields.String(required=True, validate=validate.Length(min=1, max=32))


class EnrollmentTokenSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    classroom_id = fields.UUID(required=True)
    expires_in_minutes = fields.Integer(load_default=10, validate=validate.Range(min=1, max=60))


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_json():
    return request.get_json(silent=False) or {}


@admin_bp.post("/admin/bootstrap")
def bootstrap_first_admin():
    expected = current_app.config.get("BOOTSTRAP_TOKEN")
    provided = request.headers.get("X-Admin-Bootstrap-Token", "")
    if not expected:
        return fail("BOOTSTRAP_NOT_CONFIGURED", "First-admin provisioning is not configured.", 503)
    if not provided or not hmac.compare_digest(str(expected), provided):
        return fail("BOOTSTRAP_TOKEN_INVALID", "The one-time administrator bootstrap token is invalid.", 401)
    identity = request_identity()
    if identity is None:
        return fail("UNAUTHENTICATED", "Sign in with Manus before first-admin provisioning.", 401)
    if User.query.filter_by(role="Admin", status="active").first() is not None or BootstrapState.query.filter_by(id="initial-admin").first() is not None:
        return fail("BOOTSTRAP_ALREADY_USED", "An active Admin already exists; bootstrap is closed.", 409)
    user = User.query.filter_by(open_id=identity["open_id"]).with_for_update().one_or_none()
    if user is None or user.status != "pending" or user.role is not None:
        return fail("BOOTSTRAP_ACCOUNT_NOT_ELIGIBLE", "Only the signed-in, newly provisioned account can become the first Admin.", 403)
    user.role = "Admin"
    user.status = "active"
    db.session.add(BootstrapState(id="initial-admin", consumed_by_user_id=user.id, consumed_at=utcnow()))
    db.session.add(AuditLog(actor_user_id=user.id, action="first_admin_provisioned", entity_type="users", entity_id=str(user.id), after_state={"role": "Admin", "status": "active"}, request_id=getattr(g, "request_id", None)))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return fail("BOOTSTRAP_ALREADY_USED", "The first-admin bootstrap has already been consumed.", 409)
    return success({"role": "Admin", "status": "active", "display_name": user.display_name})


@admin_bp.get("/admin/summary")
@roles_required("Admin")
def admin_summary():
    by_department = []
    for department in Department.query.order_by(Department.name).all():
        by_department.append({"department": department.name, "students": Student.query.filter_by(department_id=department.id, status="active").count(), "staff": Staff.query.filter_by(department_id=department.id, status="active").count()})
    return success({
        "students": Student.query.filter_by(status="active").count(),
        "staff": Staff.query.filter_by(status="active").count(),
        "class_sessions": ClassSession.query.count(),
        "attendance_records": AttendanceRecord.query.count(),
        "devices": PiDevice.query.count(),
        "pending_corrections": AttendanceCorrection.query.filter_by(state="pending").count(),
        "device_events_rejected": DeviceEvent.query.filter_by(processing_status="rejected").count(),
        "prediction_records": MLPrediction.query.count(),
        "departments": by_department,
    })


@admin_bp.get("/admin/users")
@roles_required("Admin")
def list_users():
    status = request.args.get("status")
    query = User.query.order_by(User.created_at.desc())
    if status in {"pending", "active", "disabled"}:
        query = query.filter_by(status=status)
    return success([user_record(user) for user in query.limit(250).all()])


@admin_bp.patch("/admin/users/<uuid:user_id>")
@roles_required("Admin")
def update_user_role(user_id):
    payload = UserRoleSchema().load_object(_require_json())
    user = User.query.filter_by(id=user_id).one_or_none()
    if user is None:
        return fail("USER_NOT_FOUND", "The account was not found.", 404)
    if payload["role"] == "Admin" and user.role != "Admin":
        return fail("ADMIN_BOOTSTRAP_REQUIRED", "Admin privileges can only be granted through the one-time first-Admin bootstrap.", 409)
    if payload["role"] == "Student" and Student.query.filter_by(user_id=user.id).one_or_none() is None:
        return fail("STUDENT_PROFILE_REQUIRED", "Create the Student profile before assigning the Student role.", 409)
    if payload["role"] == "Staff" and Staff.query.filter_by(user_id=user.id).one_or_none() is None:
        return fail("STAFF_PROFILE_REQUIRED", "Create the Staff profile before assigning the Staff role.", 409)
    if user.id == g.current_user.id and (payload["role"] != "Admin" or payload["status"] != "active"):
        return fail("SELF_LOCKOUT_BLOCKED", "An administrator cannot disable or demote their own active account.", 409)
    if user.role == "Admin" and payload["status"] != "active" and User.query.filter_by(role="Admin", status="active").count() <= 1:
        return fail("LAST_ADMIN_PROTECTED", "The last active Admin account cannot be disabled.", 409)
    before = {"role": user.role, "status": user.status}
    user.role = payload["role"]
    user.status = payload["status"]
    record_audit("user_role_updated", "users", user.id, before=before, after={"role": user.role, "status": user.status})
    db.session.commit()
    return success(user_record(user))


@admin_bp.get("/admin/departments")
@roles_required("Admin")
def list_departments():
    rows = Department.query.order_by(Department.name).all()
    return success([{"id": str(row.id), "code": row.code, "name": row.name} for row in rows])


@admin_bp.post("/admin/departments")
@roles_required("Admin")
def create_department():
    payload = DepartmentSchema().load_object(_require_json())
    if Department.query.filter(db.or_(Department.code == payload["code"], Department.name == payload["name"])).first():
        return fail("DEPARTMENT_ALREADY_EXISTS", "The department code or name is already in use.", 409)
    department = Department(**payload)
    db.session.add(department)
    db.session.flush()
    record_audit("department_created", "departments", department.id, after=payload)
    db.session.commit()
    return success({"id": str(department.id), "code": department.code, "name": department.name}, 201)


@admin_bp.get("/admin/classrooms")
@roles_required("Admin")
def list_classrooms():
    rows = Classroom.query.order_by(Classroom.building, Classroom.room_code).all()
    return success([{"id": str(row.id), "building": row.building, "room_code": row.room_code, "description": row.description} for row in rows])


@admin_bp.post("/admin/classrooms")
@roles_required("Admin")
def create_classroom():
    payload = ClassroomSchema().load_object(_require_json())
    if Classroom.query.filter_by(room_code=payload["room_code"]).first():
        return fail("CLASSROOM_ALREADY_EXISTS", "That classroom code is already in use.", 409)
    classroom = Classroom(**payload)
    db.session.add(classroom)
    db.session.flush()
    record_audit("classroom_created", "classrooms", classroom.id, after={"building": classroom.building, "room_code": classroom.room_code})
    db.session.commit()
    return success({"id": str(classroom.id), "building": classroom.building, "room_code": classroom.room_code, "description": classroom.description}, 201)


@admin_bp.get("/admin/sections")
@roles_required("Admin")
def list_sections():
    rows = ClassSection.query.order_by(ClassSection.academic_year, ClassSection.code).all()
    return success([{"id": str(row.id), "department_id": str(row.department_id), "department": row.department.name, "classroom_id": str(row.classroom_id) if row.classroom_id else None, "classroom": row.classroom.room_code if row.classroom else None, "code": row.code, "academic_year": row.academic_year, "term": row.term} for row in rows])


@admin_bp.post("/admin/sections")
@roles_required("Admin")
def create_section():
    payload = SectionSchema().load_object(_require_json())
    if Department.query.filter_by(id=payload["department_id"]).one_or_none() is None:
        return fail("DEPARTMENT_NOT_FOUND", "The department was not found.", 404)
    if payload.get("classroom_id") and Classroom.query.filter_by(id=payload["classroom_id"]).one_or_none() is None:
        return fail("CLASSROOM_NOT_FOUND", "The classroom was not found.", 404)
    if ClassSection.query.filter_by(department_id=payload["department_id"], code=payload["code"], academic_year=payload["academic_year"], term=payload["term"]).first():
        return fail("SECTION_ALREADY_EXISTS", "This department, section, year and term combination already exists.", 409)
    section = ClassSection(**payload)
    db.session.add(section)
    db.session.flush()
    record_audit("class_section_created", "class_sections", section.id, after={"code": section.code, "department_id": str(section.department_id), "academic_year": section.academic_year, "term": section.term})
    db.session.commit()
    return success({"id": str(section.id), "code": section.code, "department_id": str(section.department_id), "academic_year": section.academic_year, "term": section.term}, 201)


@admin_bp.post("/admin/device-enrollment-tokens")
@roles_required("Admin")
def create_device_enrollment_token():
    payload = EnrollmentTokenSchema().load_object(_require_json())
    classroom = Classroom.query.filter_by(id=payload["classroom_id"]).one_or_none()
    if classroom is None:
        return fail("CLASSROOM_NOT_FOUND", "The classroom was not found.", 404)
    raw_token = secrets.token_urlsafe(32)
    expires_at = utcnow() + timedelta(minutes=payload["expires_in_minutes"])
    enrollment = DeviceEnrollmentToken(token_hash=_token_hash(raw_token), classroom_id=classroom.id, created_by_user_id=g.current_user.id, expires_at=expires_at)
    db.session.add(enrollment)
    db.session.flush()
    record_audit("device_enrollment_token_created", "device_enrollment_tokens", enrollment.id, after={"classroom_id": str(classroom.id), "expires_at": expires_at.isoformat()})
    db.session.commit()
    return success({"token": raw_token, "classroom": classroom.room_code, "expires_at": expires_at.isoformat(), "usage": "Use once in the X-Device-Enrollment-Token header when calling POST /api/device/register. Copy it now; it cannot be retrieved later."}, 201)


@admin_bp.get("/admin/audit")
@roles_required("Admin")
def list_audit_events():
    items = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return success([{"id": str(item.id), "actor_user_id": str(item.actor_user_id) if item.actor_user_id else None, "action": item.action, "entity_type": item.entity_type, "entity_id": item.entity_id, "before": item.before_state, "after": item.after_state, "request_id": item.request_id, "created_at": iso(item.created_at)} for item in items])


@admin_bp.get("/admin/attendance-corrections")
@roles_required("Admin")
def list_pending_attendance_corrections():
    items = AttendanceCorrection.query.filter_by(state="pending").order_by(AttendanceCorrection.created_at.asc()).limit(500).all()
    rows = []
    for item in items:
        record = item.attendance_record
        rows.append({
            "id": str(item.id),
            "attendance_record_id": str(record.id),
            "student": record.student.user.display_name,
            "roll_number": record.student.roll_number,
            "subject": record.session.subject.name,
            "section": record.session.section.code,
            "session_start": iso(record.session.starts_at),
            "prior_status": item.prior_status,
            "requested_status": item.requested_status,
            "reason": item.reason,
            "requested_by": item.requester.display_name,
            "created_at": iso(item.created_at),
        })
    return success(rows)
