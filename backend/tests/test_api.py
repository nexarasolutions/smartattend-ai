from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models import (
    AttendanceRecord,
    ClassSection,
    ClassSession,
    Classroom,
    Department,
    DeviceCredential,
    DeviceEnrollmentToken,
    Notification,
    PiDevice,
    Staff,
    StaffSubjectAssignment,
    Student,
    Subject,
    User,
    utcnow,
)


APP_SECRET = "test-only-smartattend-signing-secret-do-not-use-in-production"
APP_ID = "test-smartattend-project"


@pytest.fixture

def app():
    application = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "APP_JWT_SECRET": APP_SECRET,
        "MANUS_PROJECT_ID": APP_ID,
        "MANUS_OAUTH_PORTAL_URL": None,
        "MANUS_OAUTH_API_URL": None,
        "BOOTSTRAP_TOKEN": "test-only-bootstrap-token",
        "SESSION_COOKIE_SECURE": False,
        "REQUIRE_HTTPS": False,
        "ALLOWED_ORIGINS": (),
    })
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture

def client(app):
    return app.test_client()


def auth_headers(open_id: str) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": open_id, "iss": "smartattend", "appId": APP_ID, "iat": now, "exp": now + timedelta(hours=1)}, APP_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def seed_academic_scope():
    department = Department(code="CS", name="Computer Science")
    room = Classroom(building="North", room_code="N-204")
    db.session.add_all([department, room])
    db.session.flush()
    section_a = ClassSection(department_id=department.id, classroom_id=room.id, code="CS-A", academic_year=2, term="2026-Fall")
    section_b = ClassSection(department_id=department.id, classroom_id=room.id, code="CS-B", academic_year=2, term="2026-Fall")
    db.session.add_all([section_a, section_b])
    db.session.flush()

    student_user_a = User(open_id="student-a", email="student-a@example.test", display_name="Student A", role="Student", status="active")
    student_user_b = User(open_id="student-b", email="student-b@example.test", display_name="Student B", role="Student", status="active")
    staff_user = User(open_id="staff-a", email="staff-a@example.test", display_name="Staff A", role="Staff", status="active")
    admin_user = User(open_id="admin-a", email="admin-a@example.test", display_name="Admin A", role="Admin", status="active")
    db.session.add_all([student_user_a, student_user_b, staff_user, admin_user])
    db.session.flush()

    student_a = Student(user_id=student_user_a.id, department_id=department.id, section_id=section_a.id, roll_number="CS26-001", academic_year=2, status="active")
    student_b = Student(user_id=student_user_b.id, department_id=department.id, section_id=section_b.id, roll_number="CS26-002", academic_year=2, status="active")
    staff = Staff(user_id=staff_user.id, department_id=department.id, staff_number="FAC-001", status="active")
    subject = Subject(department_id=department.id, code="CS201", name="Data Structures", credits=4)
    db.session.add_all([student_a, student_b, staff, subject])
    db.session.flush()
    assignment = StaffSubjectAssignment(staff_id=staff.id, subject_id=subject.id, section_id=section_a.id)
    session_a = ClassSession(subject_id=subject.id, section_id=section_a.id, staff_id=staff.id, classroom_id=room.id, starts_at=utcnow() - timedelta(minutes=20), ends_at=utcnow() + timedelta(minutes=40), status="open")
    session_b = ClassSession(subject_id=subject.id, section_id=section_b.id, staff_id=staff.id, classroom_id=room.id, starts_at=utcnow() - timedelta(minutes=20), ends_at=utcnow() + timedelta(minutes=40), status="open")
    db.session.add_all([assignment, session_a, session_b])
    db.session.flush()
    record_a = AttendanceRecord(session_id=session_a.id, student_id=student_a.id, status="Present", source="staff", recorded_by_user_id=staff_user.id)
    record_b = AttendanceRecord(session_id=session_b.id, student_id=student_b.id, status="Absent", source="staff", recorded_by_user_id=staff_user.id)
    db.session.add_all([record_a, record_b])
    db.session.commit()
    return {
        "department": department,
        "classroom": room,
        "section_a": section_a,
        "section_b": section_b,
        "student_user_a": student_user_a,
        "student_user_b": student_user_b,
        "staff_user": staff_user,
        "admin_user": admin_user,
        "student_a": student_a,
        "student_b": student_b,
        "staff": staff,
        "subject": subject,
        "session_a": session_a,
        "session_b": session_b,
        "record_a": record_a,
    }


def test_health_and_auth_me_use_database_role(client, app):
    with app.app_context():
        user = User(open_id="student", email="student@example.test", display_name="Student", role="Student", status="active")
        db.session.add(user)
        db.session.commit()
        open_id = user.open_id
    liveness = client.get("/_app/health")
    assert liveness.status_code == 200
    assert liveness.get_json()["status"] == "ok"
    assert liveness.get_json()["request_id"]
    readiness = client.get("/api/health/ready")
    assert readiness.status_code == 200
    assert readiness.get_json()["data"] == {"status": "ready", "database": "connected"}
    assert readiness.get_json()["request_id"]
    status = client.get("/api/system/status").get_json()
    assert status["data"]["authentication_configured"] is False
    assert status["data"]["first_admin_bootstrap_configured"] is True
    assert status["request_id"]
    response = client.get("/api/auth/me", headers=auth_headers(open_id))
    assert response.status_code == 200
    assert response.get_json()["data"]["role"] == "Student"


def test_auth_start_accepts_opaque_preview_origin_with_same_origin_fetch_metadata(client):
    preview_origin = "https://smartattend.example.test"
    response = client.post(
        "/api/auth/start",
        headers={"Origin": "null", "Sec-Fetch-Site": "same-origin"},
        json={"origin": preview_origin},
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "AUTH_NOT_CONFIGURED"


def test_auth_start_rejects_explicit_cross_site_origin(client):
    response = client.post(
        "/api/auth/start",
        headers={
            "Origin": "https://attacker.example.test",
            "Referer": "https://attacker.example.test/page",
            "Sec-Fetch-Site": "cross-site",
        },
        json={"origin": "https://smartattend.example.test"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_ORIGIN"


def test_students_are_limited_to_their_own_profile_and_staff_assignments(client, app):
    with app.app_context():
        rows = seed_academic_scope()
        student_a_id = rows["student_a"].id
        student_b_id = rows["student_b"].id
        section_a_id = rows["section_a"].id
        staff_open_id = rows["staff_user"].open_id
        student_open_id = rows["student_user_a"].open_id
        student_token = auth_headers(student_open_id)
        staff_token = auth_headers(staff_open_id)

    student_response = client.get("/api/students", headers=student_token)
    assert student_response.status_code == 200
    assert [item["id"] for item in student_response.get_json()["data"]] == [str(student_a_id)]
    forbidden_profile = client.get(f"/api/students/{student_b_id}", headers=student_token)
    assert forbidden_profile.status_code == 404

    staff_response = client.get("/api/students", headers=staff_token)
    assert staff_response.status_code == 200
    assert [item["id"] for item in staff_response.get_json()["data"]] == [str(student_a_id)]
    staff_attendance = client.get("/api/attendance", headers=staff_token)
    assert staff_attendance.status_code == 200
    assert all(item["section"] == "CS-A" for item in staff_attendance.get_json()["data"])


def test_first_admin_bootstrap_requires_secret_and_current_identity(client, app):
    with app.app_context():
        pending_user = User(open_id="first-admin", email="admin@example.test", display_name="Initial Admin", role=None, status="pending")
        db.session.add(pending_user)
        db.session.commit()
    response = client.post("/api/admin/bootstrap", headers={**auth_headers("first-admin"), "X-Admin-Bootstrap-Token": "test-only-bootstrap-token"}, json={})
    assert response.status_code == 200
    repeated = client.post("/api/admin/bootstrap", headers={**auth_headers("first-admin"), "X-Admin-Bootstrap-Token": "test-only-bootstrap-token"}, json={})
    assert repeated.status_code == 409
    with app.app_context():
        user = User.query.filter_by(open_id="first-admin").one()
        assert user.role == "Admin"
        assert user.status == "active"


def test_admin_user_patch_cannot_escalate_or_skip_profile_provisioning(client, app):
    with app.app_context():
        rows = seed_academic_scope()
        admin_open_id = rows["admin_user"].open_id
        pending_id = User.query.filter_by(open_id="student-a").one().id
        # The second account has no student profile in this fixture.
        unprovisioned = User(open_id="unprovisioned", email="unprovisioned@example.test", display_name="New Account", role=None, status="pending")
        db.session.add(unprovisioned)
        db.session.commit()
        unprovisioned_id = unprovisioned.id
    admin_token = auth_headers(admin_open_id)
    escalation = client.patch(f"/api/admin/users/{unprovisioned_id}", headers=admin_token, json={"role": "Admin", "status": "active"})
    assert escalation.status_code == 409
    missing_profile = client.patch(f"/api/admin/users/{unprovisioned_id}", headers=admin_token, json={"role": "Staff", "status": "active"})
    assert missing_profile.status_code == 409
    with app.app_context():
        user = User.query.filter_by(id=unprovisioned_id).one()
        assert (user.role, user.status) == (None, "pending")
        assert pending_id is not None


def test_device_enrollment_is_single_use_and_credential_is_only_returned_once(client, app):
    with app.app_context():
        rows = seed_academic_scope()
        admin_open_id = rows["admin_user"].open_id
        classroom_id = rows["classroom"].id
    issue = client.post("/api/admin/device-enrollment-tokens", headers=auth_headers(admin_open_id), json={"classroom_id": str(classroom_id), "expires_in_minutes": 10})
    assert issue.status_code == 201
    issued = issue.get_json()["data"]
    enrollment_token = issued["token"]

    registration = client.post("/api/device/register", headers={"X-Device-Enrollment-Token": enrollment_token}, json={"device_id": "PI-TEST-001", "firmware_version": "test-1"})
    assert registration.status_code == 201
    body = registration.get_json()["data"]
    assert body["status"] == "pending"
    assert len(body["credential"]) >= 32

    second_use = client.post("/api/device/register", headers={"X-Device-Enrollment-Token": enrollment_token}, json={"device_id": "PI-TEST-002"})
    assert second_use.status_code == 401
    with app.app_context():
        enrollment = DeviceEnrollmentToken.query.one()
        assert enrollment.redeemed_at is not None
        device = PiDevice.query.filter_by(device_id="PI-TEST-001").one()
        credential = DeviceCredential.query.filter_by(device_id=device.id).one()
        assert credential.credential_hash == hashlib.sha256(body["credential"].encode()).hexdigest()
        assert enrollment_token not in credential.credential_hash


def test_device_attendance_event_is_idempotent(client, app):
    with app.app_context():
        rows = seed_academic_scope()
        device = PiDevice(device_id="PI-TEST-ATTENDANCE", classroom_id=rows["classroom"].id, status="active")
        db.session.add(device)
        db.session.flush()
        credential = "a-long-device-credential-for-tests-only"
        db.session.add(DeviceCredential(device_id=device.id, credential_hash=hashlib.sha256(credential.encode()).hexdigest()))
        new_session = ClassSession(subject_id=rows["subject"].id, section_id=rows["section_a"].id, staff_id=rows["staff"].id, classroom_id=rows["classroom"].id, starts_at=utcnow() - timedelta(minutes=5), ends_at=utcnow() + timedelta(minutes=45), status="open")
        db.session.add(new_session)
        db.session.commit()
        session_id = new_session.id
    payload = {
        "event_id": "evt-attendance-0001",
        "idempotency_key": "idem-attendance-0001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": str(session_id),
        "roll_number": "CS26-001",
        "status": "Present",
        "sensor_type": "unspecified",
    }
    headers = {"Authorization": f"Bearer {credential}"}
    first = client.post("/api/device/attendance", headers=headers, json=payload)
    assert first.status_code == 201
    assert first.get_json()["data"]["event_status"] == "accepted"
    second = client.post("/api/device/attendance", headers=headers, json=payload)
    assert second.status_code == 200
    assert second.get_json()["data"]["event_status"] == "duplicate"
    with app.app_context():
        assert AttendanceRecord.query.filter_by(session_id=session_id, student_id=rows["student_a"].id).count() == 1
        assert Notification.query.filter_by(user_id=rows["student_user_a"].id, kind="attendance").count() == 1


def test_report_pdf_is_generated_from_real_test_database_records(client, app):
    with app.app_context():
        rows = seed_academic_scope()
        admin_open_id = rows["admin_user"].open_id
    response = client.get("/api/reports/attendance.pdf", headers=auth_headers(admin_open_id))
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    assert response.headers["Content-Disposition"].endswith('filename="smartattend-attendance.pdf"')
    assert len(response.data) > 1000


@pytest.mark.parametrize("window", ["expired", "future"])
def test_staff_read_scopes_honor_assignment_validity_dates(client, app, window):
    from datetime import date

    rows = seed_academic_scope()
    with app.app_context():
        assignment = StaffSubjectAssignment.query.filter_by(staff_id=rows["staff"].id).one()
        if window == "expired":
            assignment.valid_to = date.today() - timedelta(days=1)
        else:
            assignment.valid_from = date.today() + timedelta(days=1)
        db.session.commit()

    headers = auth_headers("staff-a")
    for path in ("/api/students", "/api/attendance", "/api/attendance/sessions", "/api/subjects"):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.get_json())
        assert response.get_json()["data"] == [], (path, response.get_json())


def test_student_subject_summary_counts_held_sessions_and_only_own_records(client, app):
    rows = seed_academic_scope()
    with app.app_context():
        unrecorded_session = ClassSession(
            subject_id=rows["subject"].id,
            section_id=rows["section_a"].id,
            staff_id=rows["staff"].id,
            classroom_id=rows["classroom"].id,
            starts_at=utcnow() - timedelta(days=1),
            ends_at=utcnow() - timedelta(days=1) + timedelta(minutes=50),
            status="closed",
        )
        db.session.add(unrecorded_session)
        db.session.commit()

    response = client.get("/api/students/me/attendance-summary", headers=auth_headers("student-a"))
    assert response.status_code == 200
    result = response.get_json()["data"]
    assert result["overall"] == {"classes_held": 2, "classes_attended": 1, "attendance_percentage": 50.0}
    assert result["subjects"] == [{
        "subject_id": str(rows["subject"].id),
        "subject_code": "CS201",
        "subject": "Data Structures",
        "classes_held": 2,
        "classes_attended": 1,
        "attendance_percentage": 50.0,
    }]

    other_student = client.get("/api/students/me/attendance-summary", headers=auth_headers("student-b"))
    assert other_student.status_code == 200
    other_summary = other_student.get_json()["data"]["overall"]
    assert other_summary == {"classes_held": 1, "classes_attended": 0, "attendance_percentage": 0.0}



def test_oauth_state_payload_decodes_signed_flow_state():
    import base64
    import json

    from backend.app.api.auth import _oauth_state_payload

    payload = {"redirectUri": "https://smartattend.example.test/api/auth/manus/callback", "nonce": "one-time-nonce"}
    state = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    assert _oauth_state_payload(state) == payload
    assert _oauth_state_payload("not-valid-base64-json") is None


def test_auth_start_rejects_origin_mismatch_even_with_other_same_site_metadata(client):
    response = client.post(
        "/api/auth/start",
        headers={
            "Origin": "https://attacker.example.test",
            "Referer": "https://smartattend.example.test/login",
            "Sec-Fetch-Site": "same-origin",
        },
        json={"origin": "https://smartattend.example.test"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_ORIGIN"



def test_admin_device_mutation_validates_classroom_and_lifecycle_payloads(client, app):
    rows = seed_academic_scope()
    with app.app_context():
        device = PiDevice(device_id="pi-admin-managed", classroom_id=rows["classroom"].id, status="active")
        db.session.add(device)
        db.session.commit()
        device_id = device.id

    headers = auth_headers("admin-a")
    invalid_classroom = client.patch(
        f"/api/admin/devices/{device_id}",
        headers=headers,
        json={"classroom_id": "not-a-uuid"},
    )
    assert invalid_classroom.status_code == 400
    assert invalid_classroom.get_json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_status = client.patch(
        f"/api/admin/devices/{device_id}",
        headers=headers,
        json={"status": "online"},
    )
    assert invalid_status.status_code == 400
    assert invalid_status.get_json()["error"]["code"] == "VALIDATION_ERROR"

    revoked = client.patch(
        f"/api/admin/devices/{device_id}",
        headers=headers,
        json={"status": "revoked"},
    )
    assert revoked.status_code == 200
    assert revoked.get_json()["data"]["status"] == "revoked"
