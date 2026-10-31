from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.types import JSON, LargeBinary

from .extensions import db

JSON_VALUE = JSON()
# LargeBinary works for both PostgreSQL (bytea) and SQLite (BLOB)
MODEL_ARTIFACT_TYPE = LargeBinary()


class KeywordConstructor:
    """Typed equivalent of SQLAlchemy's dynamic declarative constructor."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if not hasattr(type(self), key):
                raise TypeError(f"{type(self).__name__} has no mapped field {key!r}")
            setattr(self, key, value)


class BootstrapState(KeywordConstructor, db.Model):
    __tablename__ = "bootstrap_state"
    id = db.Column(db.String(32), primary_key=True)
    consumed_by_user_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    consumed_at = db.Column(db.DateTime(timezone=True), nullable=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin(KeywordConstructor):
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class User(TimestampMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    open_id = db.Column(db.String(255), nullable=False, unique=True, index=True)
    email = db.Column(db.String(320), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(160), nullable=False)
    role = db.Column(db.String(16), nullable=True, index=True)
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    __table_args__ = (
        CheckConstraint("role IS NULL OR role IN ('Student', 'Staff', 'Admin')", name="user_role"),
        CheckConstraint("status IN ('pending', 'active', 'disabled')", name="user_status"),
    )


class Department(TimestampMixin, db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = db.Column(db.String(24), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False, unique=True)


class Student(TimestampMixin, db.Model):
    __tablename__ = "students"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True)
    department_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    section_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("class_sections.id", ondelete="RESTRICT"), nullable=False, index=True)
    roll_number = db.Column(db.String(48), nullable=False, unique=True, index=True)
    academic_year = db.Column(db.SmallInteger, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="active")
    user = db.relationship("User", backref=db.backref("student_profile", uselist=False))
    department = db.relationship("Department")
    section = db.relationship("ClassSection")
    __table_args__ = (CheckConstraint("academic_year > 0", name="student_academic_year_positive"),)


class Staff(TimestampMixin, db.Model):
    __tablename__ = "staff"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True)
    department_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    staff_number = db.Column(db.String(48), nullable=False, unique=True, index=True)
    status = db.Column(db.String(16), nullable=False, default="active")
    user = db.relationship("User", backref=db.backref("staff_profile", uselist=False))
    department = db.relationship("Department")


class Subject(TimestampMixin, db.Model):
    __tablename__ = "subjects"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    code = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(160), nullable=False)
    credits = db.Column(db.SmallInteger, nullable=False, default=0)
    department = db.relationship("Department")
    __table_args__ = (CheckConstraint("credits >= 0", name="subject_credits_nonnegative"),)


class Classroom(TimestampMixin, db.Model):
    __tablename__ = "classrooms"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    building = db.Column(db.String(100), nullable=False)
    room_code = db.Column(db.String(32), nullable=False, unique=True)
    description = db.Column(db.String(200), nullable=True)


class ClassSection(TimestampMixin, db.Model):
    __tablename__ = "class_sections"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    classroom_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("classrooms.id", ondelete="SET NULL"), nullable=True, index=True)
    code = db.Column(db.String(32), nullable=False)
    academic_year = db.Column(db.SmallInteger, nullable=False)
    term = db.Column(db.String(32), nullable=False)
    department = db.relationship("Department")
    classroom = db.relationship("Classroom")
    __table_args__ = (
        UniqueConstraint("department_id", "code", "academic_year", "term", name="uq_section_scope"),
        CheckConstraint("academic_year > 0", name="section_academic_year_positive"),
    )


class StaffSubjectAssignment(TimestampMixin, db.Model):
    __tablename__ = "staff_subject_assignments"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False, index=True)
    subject_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True)
    section_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("class_sections.id", ondelete="RESTRICT"), nullable=False, index=True)
    valid_from = db.Column(db.Date, nullable=True)
    valid_to = db.Column(db.Date, nullable=True)
    staff = db.relationship("Staff")
    subject = db.relationship("Subject")
    section = db.relationship("ClassSection")
    __table_args__ = (UniqueConstraint("staff_id", "subject_id", "section_id", name="uq_staff_subject_section"),)


class ClassSession(TimestampMixin, db.Model):
    __tablename__ = "class_sessions"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True)
    section_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("class_sections.id", ondelete="RESTRICT"), nullable=False, index=True)
    staff_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False, index=True)
    classroom_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("classrooms.id", ondelete="SET NULL"), nullable=True, index=True)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="scheduled")
    subject = db.relationship("Subject")
    section = db.relationship("ClassSection")
    staff = db.relationship("Staff")
    classroom = db.relationship("Classroom")
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="session_end_after_start"),
        CheckConstraint("status IN ('scheduled', 'open', 'closed', 'cancelled')", name="session_status"),
    )


class PiDevice(TimestampMixin, db.Model):
    __tablename__ = "pi_devices"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = db.Column(db.String(80), nullable=False, unique=True, index=True)
    classroom_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("classrooms.id", ondelete="SET NULL"), nullable=True, index=True)
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    firmware_version = db.Column(db.String(48), nullable=True)
    last_heartbeat_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    last_health = db.Column(JSON_VALUE, nullable=False, default=dict)
    classroom = db.relationship("Classroom")
    __table_args__ = (CheckConstraint("status IN ('pending', 'active', 'revoked')", name="device_status"),)


class DeviceEnrollmentToken(TimestampMixin, db.Model):
    __tablename__ = "device_enrollment_tokens"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    classroom_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("classrooms.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_user_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    redeemed_device_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("pi_devices.id", ondelete="SET NULL"), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    redeemed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    classroom = db.relationship("Classroom")
    created_by = db.relationship("User")
    redeemed_device = db.relationship("PiDevice")


class DeviceCredential(TimestampMixin, db.Model):
    __tablename__ = "device_credentials"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("pi_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_hash = db.Column(db.String(64), nullable=False, unique=True)
    issued_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    device = db.relationship("PiDevice", backref=db.backref("credentials", lazy="select"))


class DeviceEvent(TimestampMixin, db.Model):
    __tablename__ = "device_events"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("pi_devices.id", ondelete="RESTRICT"), nullable=False, index=True)
    session_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("class_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    student_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
    event_id = db.Column(db.String(120), nullable=False)
    idempotency_key = db.Column(db.String(120), nullable=False)
    event_type = db.Column(db.String(24), nullable=False)
    processing_status = db.Column(db.String(16), nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False)
    received_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    payload = db.Column(JSON_VALUE, nullable=False, default=dict)
    failure_code = db.Column(db.String(80), nullable=True)
    __table_args__ = (
        UniqueConstraint("device_id", "event_id", name="uq_device_event_identity"),
        UniqueConstraint("device_id", "idempotency_key", name="uq_device_idempotency"),
        CheckConstraint("event_type IN ('heartbeat', 'attendance')", name="device_event_type"),
        CheckConstraint("processing_status IN ('received', 'accepted', 'duplicate', 'rejected')", name="device_event_status"),
        Index("ix_device_events_status_received", "processing_status", "received_at"),
    )


class AttendanceRecord(TimestampMixin, db.Model):
    __tablename__ = "attendance_records"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("class_sessions.id", ondelete="RESTRICT"), nullable=False, index=True)
    student_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = db.Column(db.String(16), nullable=False)
    source = db.Column(db.String(16), nullable=False)
    device_event_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("device_events.id", ondelete="SET NULL"), nullable=True, unique=True)
    recorded_by_user_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    session = db.relationship("ClassSession")
    student = db.relationship("Student")
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
        CheckConstraint("status IN ('Present', 'Absent', 'Late')", name="attendance_status"),
        CheckConstraint("source IN ('staff', 'device', 'admin')", name="attendance_source"),
    )


class AttendanceCorrection(TimestampMixin, db.Model):
    __tablename__ = "attendance_corrections"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attendance_record_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("attendance_records.id", name="fk_attendance_correction_record", ondelete="RESTRICT"), nullable=False, index=True)
    requested_by_user_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewed_by_user_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    prior_status = db.Column(db.String(16), nullable=False)
    requested_status = db.Column(db.String(16), nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    state = db.Column(db.String(16), nullable=False, default="pending", index=True)
    review_note = db.Column(db.String(500), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    attendance_record = db.relationship("AttendanceRecord")
    requester = db.relationship("User", foreign_keys=[requested_by_user_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_user_id])
    __table_args__ = (CheckConstraint("state IN ('pending', 'approved', 'rejected')", name="correction_state"),)


class MLModelVersion(KeywordConstructor, db.Model):
    __tablename__ = "ml_model_versions"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version = db.Column(db.String(64), nullable=False, unique=True)
    algorithm = db.Column(db.String(80), nullable=False)
    artifact = db.Column(MODEL_ARTIFACT_TYPE, nullable=False)
    artifact_sha256 = db.Column(db.String(64), nullable=False, unique=True)
    feature_names = db.Column(JSON_VALUE, nullable=False, default=list)
    evaluation_metrics = db.Column(JSON_VALUE, nullable=False, default=dict)
    feature_importance = db.Column(JSON_VALUE, nullable=False, default=dict)
    training_rows = db.Column(db.Integer, nullable=False)
    training_cutoff = db.Column(db.DateTime(timezone=True), nullable=False)
    trained_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    state = db.Column(db.String(16), nullable=False, default="candidate", index=True)
    __table_args__ = (CheckConstraint("state IN ('candidate', 'active', 'retired', 'rejected')", name="model_version_state"),)


class MLPrediction(TimestampMixin, db.Model):
    __tablename__ = "ml_predictions"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    subject_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    model_version = db.Column(db.String(64), db.ForeignKey("ml_model_versions.model_version", ondelete="RESTRICT"), nullable=False, index=True)
    predicted_percentage = db.Column(db.Numeric(5, 2), nullable=False)
    risk_category = db.Column(db.String(16), nullable=False)
    calibrated_confidence = db.Column(db.Numeric(5, 4), nullable=True)
    feature_attribution = db.Column(JSON_VALUE, nullable=False, default=dict)
    cutoff_at = db.Column(db.DateTime(timezone=True), nullable=False)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    student = db.relationship("Student")
    subject = db.relationship("Subject")
    model = db.relationship("MLModelVersion")
    __table_args__ = (
        CheckConstraint("predicted_percentage >= 0 AND predicted_percentage <= 100", name="prediction_pct_range"),
        CheckConstraint("calibrated_confidence IS NULL OR (calibrated_confidence >= 0 AND calibrated_confidence <= 1)", name="prediction_confidence_range"),
    )


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(32), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(1000), nullable=False)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)


class AuditLog(KeywordConstructor, db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id = db.Column(db.Uuid(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.String(80), nullable=True)
    before_state = db.Column(JSON_VALUE, nullable=True)
    after_state = db.Column(JSON_VALUE, nullable=True)
    request_id = db.Column(db.String(64), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
