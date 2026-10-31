from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from marshmallow import ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..extensions import db
from ..models import AttendanceRecord, Classroom, ClassSession, DeviceCredential, DeviceEnrollmentToken, DeviceEvent, PiDevice, Student, utcnow
from ..schemas import DeviceActivationSchema, DeviceAttendanceSchema, DeviceHeartbeatSchema, DeviceRegisterSchema, DeviceUpdateSchema
from ..security import roles_required
from ..services.audit import record_audit
from ..services.http import fail, success
from ..services.notifications import add_user_notification
from ..services.serialization import attendance_record, device_record, iso


devices_bp = Blueprint("devices", __name__)


def credential_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _require_https():
    if current_app.config.get("REQUIRE_HTTPS", True) and not request.is_secure:
        return fail("HTTPS_REQUIRED", "Raspberry Pi device APIs require HTTPS.", 426)
    return None


def _device_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        secure_response = _require_https()
        if secure_response:
            return secure_response
        authorization = request.headers.get("Authorization", "")
        if not authorization.lower().startswith("bearer "):
            return fail("DEVICE_AUTH_REQUIRED", "A device bearer credential is required.", 401)
        token = authorization[7:].strip()
        if len(token) < 32 or len(token) > 256:
            return fail("DEVICE_AUTH_INVALID", "The device credential is invalid or revoked.", 401)
        try:
            credential = DeviceCredential.query.filter_by(credential_hash=credential_hash(token), revoked_at=None).one_or_none()
        except SQLAlchemyError:
            db.session.rollback()
            return fail("DATABASE_UNAVAILABLE", "Device authentication is temporarily unavailable.", 503)
        if credential is None or credential.device.status != "active":
            return fail("DEVICE_AUTH_INVALID", "The device credential is invalid or revoked.", 401)
        g.current_device = credential.device
        return view(*args, **kwargs)
    return wrapped


def _safe_health(raw: dict) -> dict:
    allowed = {"cpu_pct", "temperature_c", "storage_pct", "memory_pct", "uptime_seconds", "queue_depth"}
    cleaned = {}
    for key in allowed:
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cleaned[key] = max(0, min(float(value), 1_000_000))
    return cleaned


def _timestamp_problem(timestamp: datetime, *, max_age_days: int, allow_future_seconds: int = 300) -> str | None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return "timestamp_timezone_required"
    now = datetime.now(timezone.utc)
    stamp = timestamp.astimezone(timezone.utc)
    if stamp > now + timedelta(seconds=allow_future_seconds):
        return "timestamp_in_future"
    if stamp < now - timedelta(days=max_age_days):
        return "timestamp_too_old"
    return None


def _log_rejected_event(device: PiDevice, payload: dict, event_type: str, failure_code: str):
    request_id = getattr(g, "request_id", "unknown")
    event_id = str(payload.get("event_id") or f"invalid-{request_id}")[:120]
    idempotency_key = str(payload.get("idempotency_key") or event_id)[:120]
    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        timestamp = utcnow()
    event = DeviceEvent(device_id=device.id, event_id=event_id, idempotency_key=idempotency_key, event_type=event_type, processing_status="rejected", occurred_at=timestamp, received_at=utcnow(), payload={"failure_code": failure_code}, failure_code=failure_code)
    db.session.add(event)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    except SQLAlchemyError:
        db.session.rollback()


@devices_bp.post("/device/register")
def register_device():
    secure_response = _require_https()
    if secure_response:
        return secure_response
    supplied = request.headers.get("X-Device-Enrollment-Token", "")
    if not supplied or len(supplied) < 32 or len(supplied) > 256:
        return fail("ENROLLMENT_TOKEN_INVALID", "A valid one-time device enrollment authorization is required.", 401)
    payload = DeviceRegisterSchema().load_object(request.get_json(silent=False) or {})
    enrollment = DeviceEnrollmentToken.query.filter_by(token_hash=credential_hash(supplied)).with_for_update().one_or_none()
    if enrollment is None or not hmac.compare_digest(enrollment.token_hash, credential_hash(supplied)):
        return fail("ENROLLMENT_TOKEN_INVALID", "The one-time device enrollment token is invalid.", 401)
    expiry = enrollment.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if enrollment.redeemed_at is not None or expiry <= utcnow():
        return fail("ENROLLMENT_TOKEN_EXPIRED", "This enrollment token has expired or has already been used.", 401)
    if PiDevice.query.filter_by(device_id=payload["device_id"]).one_or_none():
        return fail("DEVICE_ALREADY_REGISTERED", "This device ID is already registered.", 409)
    classroom = Classroom.query.filter_by(id=enrollment.classroom_id).one_or_none()
    if classroom is None:
        return fail("CLASSROOM_NOT_FOUND", "The classroom assigned to this enrollment token no longer exists.", 409)
    device = PiDevice(device_id=payload["device_id"], classroom_id=classroom.id, firmware_version=payload.get("firmware_version"), status="pending", last_health={})
    raw_credential = secrets.token_urlsafe(48)
    db.session.add(device)
    db.session.flush()
    enrollment.redeemed_at = utcnow()
    enrollment.redeemed_device_id = device.id
    db.session.add(DeviceCredential(device_id=device.id, credential_hash=credential_hash(raw_credential)))
    record_audit("device_registered_pending", "pi_devices", device.id, after={"device_id": device.device_id, "classroom_id": str(device.classroom_id), "enrollment_id": str(enrollment.id)})
    db.session.commit()
    return success({"device_id": device.device_id, "status": "pending", "credential": raw_credential, "credential_notice": "This credential is returned once. Store it on the device in a protected file and never submit it again."}, 201)


@devices_bp.post("/device/heartbeat")
@_device_auth
def heartbeat():
    raw = request.get_json(silent=True) or {}
    try:
        payload = DeviceHeartbeatSchema().load_object(raw)
    except ValidationError as error:
        _log_rejected_event(g.current_device, raw, "heartbeat", "invalid_heartbeat_payload")
        raise error
    problem = _timestamp_problem(payload["timestamp"], max_age_days=1)
    if problem:
        _log_rejected_event(g.current_device, payload, "heartbeat", problem)
        return fail(problem.upper(), "Heartbeat timestamp is outside the accepted time window.", 400)
    device = g.current_device
    existing = DeviceEvent.query.filter_by(device_id=device.id, event_id=payload["event_id"]).one_or_none()
    if existing:
        return success({"device_id": device.device_id, "event_status": "duplicate", "last_heartbeat_at": iso(device.last_heartbeat_at)})
    clean_health = _safe_health(payload.get("health", {}))
    device.last_heartbeat_at = payload["timestamp"].astimezone(timezone.utc)
    device.last_health = clean_health
    if payload.get("firmware_version"):
        device.firmware_version = payload["firmware_version"]
    event = DeviceEvent(device_id=device.id, event_id=payload["event_id"], idempotency_key=payload["event_id"], event_type="heartbeat", processing_status="accepted", occurred_at=payload["timestamp"].astimezone(timezone.utc), received_at=utcnow(), payload={"health": clean_health, "firmware_version": payload.get("firmware_version")})
    db.session.add(event)
    record_audit("device_heartbeat", "pi_devices", device.id, after={"event_id": payload["event_id"], "health": clean_health})
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return success({"device_id": device.device_id, "event_status": "duplicate"})
    return success({"device_id": device.device_id, "event_status": "accepted", "last_heartbeat_at": iso(device.last_heartbeat_at)})


@devices_bp.post("/device/attendance")
@_device_auth
def submit_attendance_event():
    raw = request.get_json(silent=True) or {}
    try:
        payload = DeviceAttendanceSchema().load_object(raw)
    except ValidationError as error:
        _log_rejected_event(g.current_device, raw, "attendance", "invalid_attendance_payload")
        raise error
    problem = _timestamp_problem(payload["timestamp"], max_age_days=30)
    if problem:
        _log_rejected_event(g.current_device, payload, "attendance", problem)
        return fail(problem.upper(), "Attendance event timestamp is outside the accepted time window.", 400)

    device = g.current_device
    existing_event = DeviceEvent.query.filter_by(device_id=device.id).filter(or_(DeviceEvent.event_id == payload["event_id"], DeviceEvent.idempotency_key == payload["idempotency_key"])).first()
    if existing_event:
        return success({"event_id": existing_event.event_id, "event_status": "duplicate", "attendance_record_id": None})

    session = ClassSession.query.filter_by(id=payload["session_id"]).one_or_none()
    student = Student.query.filter_by(roll_number=payload["roll_number"], status="active").one_or_none()
    failure_code = None
    if session is None:
        failure_code = "session_not_found"
    elif student is None:
        failure_code = "student_not_found"
    elif session.status not in {"open", "closed"}:
        failure_code = "session_not_open"
    elif student.section_id != session.section_id:
        failure_code = "student_section_mismatch"
    elif device.classroom_id is None or session.classroom_id != device.classroom_id:
        failure_code = "device_classroom_mismatch"
    else:
        stamp = payload["timestamp"].astimezone(timezone.utc)
        starts_at = session.starts_at if session.starts_at.tzinfo else session.starts_at.replace(tzinfo=timezone.utc)
        ends_at = session.ends_at if session.ends_at.tzinfo else session.ends_at.replace(tzinfo=timezone.utc)
        if stamp < starts_at - timedelta(minutes=15) or stamp > ends_at + timedelta(hours=24):
            failure_code = "event_outside_session_window"

    event = DeviceEvent(device_id=device.id, session_id=session.id if session is not None else None, student_id=student.id if student is not None else None, event_id=payload["event_id"], idempotency_key=payload["idempotency_key"], event_type="attendance", processing_status="rejected" if failure_code else "received", occurred_at=payload["timestamp"].astimezone(timezone.utc), received_at=utcnow(), payload={"sensor_type": payload["sensor_type"], "sensor_reference": payload.get("sensor_reference")}, failure_code=failure_code)
    db.session.add(event)
    db.session.flush()
    if failure_code:
        record_audit("device_attendance_rejected", "device_events", event.id, after={"device_id": device.device_id, "event_id": payload["event_id"], "failure_code": failure_code})
        db.session.commit()
        return fail(failure_code.upper(), "The attendance event was logged and rejected.", 422)

    assert session is not None and student is not None

    existing_attendance = AttendanceRecord.query.filter_by(session_id=session.id, student_id=student.id).one_or_none()
    if existing_attendance:
        event.processing_status = "duplicate"
        event.failure_code = "attendance_already_recorded"
        record_audit("device_attendance_duplicate", "device_events", event.id, after={"attendance_record_id": str(existing_attendance.id)})
        db.session.commit()
        return success({"event_id": payload["event_id"], "event_status": "duplicate", "attendance_record_id": str(existing_attendance.id)})

    record = AttendanceRecord(session_id=session.id, student_id=student.id, status=payload["status"], source="device", device_event_id=event.id, recorded_at=event.occurred_at)
    event.processing_status = "accepted"
    db.session.add(record)
    db.session.flush()
    add_user_notification(student.user_id, kind="attendance", title="Attendance recorded", body=f"{session.subject.name} · {record.status} · classroom device {device.device_id}.")
    record_audit("device_attendance_accepted", "attendance_records", record.id, after={"device_id": device.device_id, "event_id": payload["event_id"], "status": record.status})
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = AttendanceRecord.query.filter_by(session_id=session.id, student_id=student.id).one_or_none()
        if existing:
            return success({"event_id": payload["event_id"], "event_status": "duplicate", "attendance_record_id": str(existing.id)})
        return fail("EVENT_CONFLICT", "The event conflicted with an existing device submission.", 409)
    return success({"event_id": payload["event_id"], "event_status": "accepted", "attendance": attendance_record(record)}, 201)


@devices_bp.get("/device/status")
@_device_auth
def device_status():
    device = g.current_device
    return success(device_record(device, current_app.config.get("DEVICE_HEARTBEAT_OFFLINE_SECONDS", 300)))


@devices_bp.get("/admin/devices")
@roles_required("Admin")
def list_devices():
    offline_after = current_app.config.get("DEVICE_HEARTBEAT_OFFLINE_SECONDS", 300)
    devices = PiDevice.query.order_by(PiDevice.created_at.desc()).all()
    return success([device_record(device, offline_after) for device in devices])


@devices_bp.post("/admin/devices/<uuid:device_uuid>/activate")
@roles_required("Admin")
def activate_device(device_uuid):
    device = PiDevice.query.filter_by(id=device_uuid).one_or_none()
    if device is None:
        return fail("DEVICE_NOT_FOUND", "The device was not found.", 404)
    payload = DeviceActivationSchema().load_object(request.get_json(silent=True) or {})
    if payload.get("classroom_id"):
        classroom = Classroom.query.filter_by(id=payload["classroom_id"]).one_or_none()
        if classroom is None:
            return fail("CLASSROOM_NOT_FOUND", "The classroom was not found.", 404)
        device.classroom_id = classroom.id
    if device.classroom_id is None:
        return fail("CLASSROOM_REQUIRED", "Map the device to a classroom before activation.", 400)
    before = {"status": device.status, "classroom_id": str(device.classroom_id) if device.classroom_id else None}
    device.status = "active"
    record_audit("device_activated", "pi_devices", device.id, before=before, after={"status": device.status, "classroom_id": str(device.classroom_id)})
    db.session.commit()
    return success(device_record(device, current_app.config.get("DEVICE_HEARTBEAT_OFFLINE_SECONDS", 300)))


@devices_bp.patch("/admin/devices/<uuid:device_uuid>")
@roles_required("Admin")
def update_device(device_uuid):
    payload = DeviceUpdateSchema().load_object(request.get_json(silent=False) or {})
    device = PiDevice.query.filter_by(id=device_uuid).one_or_none()
    if device is None:
        return fail("DEVICE_NOT_FOUND", "The device was not found.", 404)
    before = {"status": device.status, "classroom_id": str(device.classroom_id) if device.classroom_id else None}
    if "classroom_id" in payload:
        classroom = Classroom.query.filter_by(id=payload["classroom_id"]).one_or_none() if payload["classroom_id"] else None
        if payload["classroom_id"] and classroom is None:
            return fail("CLASSROOM_NOT_FOUND", "The classroom was not found.", 404)
        device.classroom_id = classroom.id if classroom else None
    if "status" in payload:
        if payload["status"] not in {"active", "revoked", "pending"}:
            return fail("INVALID_DEVICE_STATUS", "Status must be active, revoked or pending.", 400)
        device.status = payload["status"]
        if device.status == "revoked":
            for credential in device.credentials:
                credential.revoked_at = utcnow()
    record_audit("device_configuration_updated", "pi_devices", device.id, before=before, after={"status": device.status, "classroom_id": str(device.classroom_id) if device.classroom_id else None})
    db.session.commit()
    return success(device_record(device, current_app.config.get("DEVICE_HEARTBEAT_OFFLINE_SECONDS", 300)))


@devices_bp.post("/admin/devices/<uuid:device_uuid>/rotate-credential")
@roles_required("Admin")
def rotate_device_credential(device_uuid):
    device = PiDevice.query.filter_by(id=device_uuid).one_or_none()
    if device is None:
        return fail("DEVICE_NOT_FOUND", "The device was not found.", 404)
    for credential in device.credentials:
        credential.revoked_at = utcnow()
    new_token = secrets.token_urlsafe(48)
    db.session.add(DeviceCredential(device_id=device.id, credential_hash=credential_hash(new_token)))
    record_audit("device_credential_rotated", "pi_devices", device.id, after={"device_id": device.device_id})
    db.session.commit()
    return success({"device_id": device.device_id, "credential": new_token, "credential_notice": "This credential is shown once. Store it securely on the device."})
