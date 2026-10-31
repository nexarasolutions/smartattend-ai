from __future__ import annotations

from datetime import date, datetime, timezone


def iso(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def user_record(user):
    return {"id": str(user.id), "open_id": user.open_id, "email": user.email, "display_name": user.display_name, "role": user.role, "status": user.status}


def student_record(student):
    return {"id": str(student.id), "user_id": str(student.user_id), "name": student.user.display_name, "email": student.user.email, "roll_number": student.roll_number, "department": student.department.name, "department_code": student.department.code, "section_id": str(student.section_id), "section": student.section.code, "academic_year": student.academic_year, "status": student.status}


def staff_record(staff):
    return {"id": str(staff.id), "user_id": str(staff.user_id), "name": staff.user.display_name, "email": staff.user.email, "staff_number": staff.staff_number, "department": staff.department.name, "department_code": staff.department.code, "status": staff.status}


def session_record(session):
    return {"id": str(session.id), "subject_id": str(session.subject_id), "subject": session.subject.name, "subject_code": session.subject.code, "section_id": str(session.section_id), "section": session.section.code, "staff_id": str(session.staff_id), "classroom_id": str(session.classroom_id) if session.classroom_id else None, "starts_at": iso(session.starts_at), "ends_at": iso(session.ends_at), "status": session.status}


def attendance_record(record):
    session = record.session
    student = record.student
    return {"id": str(record.id), "session_id": str(record.session_id), "student_id": str(record.student_id), "student": student.user.display_name, "roll_number": student.roll_number, "subject": session.subject.name, "section": session.section.code, "date": iso(session.starts_at), "status": record.status, "source": record.source, "recorded_at": iso(record.recorded_at)}


def device_record(device, offline_after_seconds: int):
    from datetime import datetime, timezone
    last = device.last_heartbeat_at
    now = datetime.now(timezone.utc)
    observed = last if last and last.tzinfo else (last.replace(tzinfo=timezone.utc) if last else None)
    online = bool(device.status == "active" and observed and (now - observed).total_seconds() <= offline_after_seconds)
    return {"id": str(device.id), "device_id": device.device_id, "classroom_id": str(device.classroom_id) if device.classroom_id else None, "classroom": device.classroom.room_code if device.classroom else None, "status": device.status, "connection_status": "online" if online else "offline", "firmware_version": device.firmware_version, "last_heartbeat_at": iso(last), "health": device.last_health or {}}


def prediction_record(prediction):
    confidence = float(prediction.calibrated_confidence) if prediction.calibrated_confidence is not None else None
    return {"id": str(prediction.id), "student_id": str(prediction.student_id), "subject_id": str(prediction.subject_id) if prediction.subject_id else None, "model_version": prediction.model_version, "predicted_percentage": float(prediction.predicted_percentage), "risk_category": prediction.risk_category, "calibrated_confidence": confidence, "feature_attribution": prediction.feature_attribution or {}, "cutoff_at": iso(prediction.cutoff_at), "generated_at": iso(prediction.generated_at)}
