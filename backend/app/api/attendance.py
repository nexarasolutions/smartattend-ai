from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, g, request
from marshmallow import RAISE, fields, validate

from ..extensions import db
from ..models import AttendanceCorrection, AttendanceRecord, ClassSession, Student, Subject, ClassSection, Staff, Classroom, utcnow
from ..security import roles_required
from ..services.access import scoped_session_query, staff_can_access_session, staff_profile_for, staff_assignment_query
from ..services.audit import record_audit
from ..services.http import fail, success
from ..services.notifications import add_user_notification
from ..services.serialization import attendance_record, session_record
from ..schemas import AttendanceMarkSchema, CorrectionRequestSchema, CorrectionReviewSchema, StrictSchema


attendance_bp = Blueprint("attendance", __name__)


class SessionSchema(StrictSchema):
    class Meta:
        unknown = RAISE
    subject_id = fields.UUID(required=True)
    section_id = fields.UUID(required=True)
    staff_id = fields.UUID(load_default=None, allow_none=True)
    classroom_id = fields.UUID(load_default=None, allow_none=True)
    starts_at = fields.DateTime(required=True)
    ends_at = fields.DateTime(required=True)
    status = fields.String(load_default="scheduled", validate=validate.OneOf(["scheduled", "open", "closed", "cancelled"]))


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


@attendance_bp.get("/attendance")
@roles_required("Admin", "Staff", "Student")
def list_attendance():
    sessions = scoped_session_query(g.current_user).with_entities(ClassSession.id)
    query = AttendanceRecord.query.filter(AttendanceRecord.session_id.in_(sessions))
    if g.current_user.role == "Student":
        student = Student.query.filter_by(user_id=g.current_user.id, status="active").one_or_none()
        if student is None:
            return success([])
        query = query.filter_by(student_id=student.id)
    elif request.args.get("student_id"):
        query = query.filter_by(student_id=request.args["student_id"])
    if request.args.get("subject_id"):
        query = query.join(ClassSession).filter(ClassSession.subject_id == request.args["subject_id"])
    if request.args.get("status") in {"Present", "Absent", "Late"}:
        query = query.filter_by(status=request.args["status"])
    if request.args.get("from"):
        query = query.join(ClassSession, AttendanceRecord.session_id == ClassSession.id).filter(ClassSession.starts_at >= request.args["from"])
    rows = query.order_by(AttendanceRecord.recorded_at.desc()).limit(1000).all()
    return success([attendance_record(row) for row in rows])


@attendance_bp.get("/attendance/sessions")
@roles_required("Admin", "Staff", "Student")
def list_sessions():
    query = scoped_session_query(g.current_user).order_by(ClassSession.starts_at.desc())
    return success([session_record(item) for item in query.limit(500).all()])


@attendance_bp.post("/attendance/sessions")
@roles_required("Admin", "Staff")
def create_session():
    payload = SessionSchema().load_object(request.get_json(silent=False) or {})
    if not _aware(payload["starts_at"]) or not _aware(payload["ends_at"]) or payload["ends_at"] <= payload["starts_at"]:
        return fail("INVALID_SESSION_TIME", "Session start/end must include a timezone and end after start.", 400)
    subject = Subject.query.filter_by(id=payload["subject_id"]).one_or_none()
    section = ClassSection.query.filter_by(id=payload["section_id"]).one_or_none()
    if not subject or not section or subject.department_id != section.department_id:
        return fail("SESSION_SCOPE_MISMATCH", "The selected subject and section do not form a valid department scope.", 400)
    staff_id = payload.get("staff_id")
    if g.current_user.role == "Staff":
        staff = staff_profile_for(g.current_user)
        assignment = staff_assignment_query(staff.id, payload["starts_at"].astimezone(timezone.utc).date()).filter_by(subject_id=subject.id, section_id=section.id).first() if staff else None
        if staff is None or assignment is None:
            return fail("ASSIGNMENT_REQUIRED", "Staff can create sessions only for assigned subjects and sections.", 403)
        staff_id = staff.id
    elif staff_id is None:
        staff = Staff.query.filter_by(user_id=g.current_user.id, status="active").one_or_none()
        staff_id = staff.id if staff else None
    staff_record = Staff.query.filter_by(id=staff_id, status="active").one_or_none() if staff_id else None
    if staff_record is None:
        return fail("STAFF_REQUIRED", "A valid session instructor is required.", 400)
    classroom_id = payload.get("classroom_id") or section.classroom_id
    if classroom_id and Classroom.query.filter_by(id=classroom_id).one_or_none() is None:
        return fail("CLASSROOM_NOT_FOUND", "The classroom was not found.", 404)
    session = ClassSession(subject_id=subject.id, section_id=section.id, staff_id=staff_record.id, classroom_id=classroom_id, starts_at=payload["starts_at"].astimezone(timezone.utc), ends_at=payload["ends_at"].astimezone(timezone.utc), status=payload["status"])
    db.session.add(session)
    db.session.flush()
    record_audit("class_session_created", "class_sessions", session.id, after={"subject_id": str(subject.id), "section_id": str(section.id), "staff_id": str(staff_record.id)})
    db.session.commit()
    return success(session_record(session), 201)


@attendance_bp.post("/attendance")
@roles_required("Admin", "Staff")
def mark_attendance():
    payload = AttendanceMarkSchema().load_object(request.get_json(silent=False) or {})
    session = ClassSession.query.filter_by(id=payload["session_id"]).one_or_none()
    student = Student.query.filter_by(id=payload["student_id"], status="active").one_or_none()
    if session is None or student is None:
        return fail("REFERENCE_NOT_FOUND", "The class session or student was not found.", 404)
    if student.section_id != session.section_id:
        return fail("STUDENT_SECTION_MISMATCH", "The student is not enrolled in this class section.", 400)
    if not staff_can_access_session(g.current_user, session):
        return fail("ASSIGNMENT_REQUIRED", "Staff can mark attendance only for assigned classes and subjects.", 403)
    existing = AttendanceRecord.query.filter_by(session_id=session.id, student_id=student.id).one_or_none()
    if existing:
        return fail("ATTENDANCE_ALREADY_RECORDED", "An attendance record already exists for this student and session.", 409)
    record = AttendanceRecord(session_id=session.id, student_id=student.id, status=payload["status"], source="staff", recorded_by_user_id=g.current_user.id)
    db.session.add(record)
    db.session.flush()
    add_user_notification(student.user_id, kind="attendance", title="Attendance recorded", body=f"{session.subject.name} · {record.status} · session {session.id}.")
    record_audit("attendance_marked", "attendance_records", record.id, after={"student_id": str(student.id), "session_id": str(session.id), "status": record.status, "source": "manual"})
    db.session.commit()
    return success(attendance_record(record), 201)


@attendance_bp.post("/attendance/<uuid:record_id>/corrections")
@roles_required("Staff")
def request_correction(record_id):
    payload = CorrectionRequestSchema().load_object(request.get_json(silent=False) or {})
    record = AttendanceRecord.query.filter_by(id=record_id).one_or_none()
    if record is None:
        return fail("ATTENDANCE_NOT_FOUND", "The attendance record was not found.", 404)
    if not staff_can_access_session(g.current_user, record.session):
        return fail("ASSIGNMENT_REQUIRED", "Staff can request corrections only for assigned classes and subjects.", 403)
    if payload["requested_status"] == record.status:
        return fail("NO_CHANGE", "The requested status already matches the current record.", 400)
    pending = AttendanceCorrection.query.filter_by(attendance_record_id=record.id, state="pending").first()
    if pending:
        return fail("CORRECTION_PENDING", "A correction request is already awaiting review.", 409)
    correction = AttendanceCorrection(attendance_record_id=record.id, requested_by_user_id=g.current_user.id, prior_status=record.status, requested_status=payload["requested_status"], reason=payload["reason"], state="pending")
    db.session.add(correction)
    db.session.flush()
    record_audit("attendance_correction_requested", "attendance_corrections", correction.id, after={"attendance_record_id": str(record.id), "prior_status": correction.prior_status, "requested_status": correction.requested_status, "reason": correction.reason})
    db.session.commit()
    return success({"id": str(correction.id), "state": correction.state, "prior_status": correction.prior_status, "requested_status": correction.requested_status}, 201)


@attendance_bp.post("/admin/attendance-corrections/<uuid:correction_id>/review")
@roles_required("Admin")
def review_correction(correction_id):
    payload = CorrectionReviewSchema().load_object(request.get_json(silent=False) or {})
    correction = AttendanceCorrection.query.filter_by(id=correction_id).with_for_update().one_or_none()
    if correction is None:
        return fail("CORRECTION_NOT_FOUND", "The correction request was not found.", 404)
    if correction.state != "pending":
        return fail("CORRECTION_ALREADY_REVIEWED", "Only pending correction requests can be reviewed.", 409)
    attendance = correction.attendance_record
    before = {"status": attendance.status, "correction_state": correction.state}
    if payload["decision"] == "approve":
        if attendance.status != correction.prior_status:
            return fail("ATTENDANCE_CHANGED", "The attendance value changed after this correction was requested; re-review the current record.", 409)
        attendance.status = correction.requested_status
        attendance.recorded_by_user_id = g.current_user.id
        correction.state = "approved"
    else:
        correction.state = "rejected"
    correction.review_note = payload.get("review_note")
    correction.reviewed_by_user_id = g.current_user.id
    correction.reviewed_at = utcnow()
    correction_status = "approved" if payload["decision"] == "approve" else "rejected"
    add_user_notification(correction.requester.id, kind="attendance_correction", title="Attendance correction reviewed", body=f"Your correction request for {attendance.session.subject.name} was {correction_status}. {correction.review_note or ''}".strip())
    record_audit("attendance_correction_reviewed", "attendance_corrections", correction.id, before=before, after={"status": attendance.status, "correction_state": correction.state, "review_note": correction.review_note})
    db.session.commit()
    return success({"id": str(correction.id), "state": correction.state, "attendance_record": attendance_record(attendance)})
