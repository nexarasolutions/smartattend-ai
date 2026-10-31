from __future__ import annotations

from pathlib import Path

import pytest

from iot.client import DeviceAPIError, DeviceClient
from iot.offline_queue import OfflineEventQueue


class FakeResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeSession:
    verify = True

    def __init__(self, response: FakeResponse):
        self.response = response
        self.last = None

    def request(self, method, url, **kwargs):
        self.last = (method, url, kwargs)
        return self.response


def test_queue_deduplicates_retries_and_records_permanent_failures(tmp_path: Path):
    queue = OfflineEventQueue(tmp_path / "queue.sqlite3")
    payload = {"event_id": "event-1", "idempotency_key": "idem-1", "status": "Present"}
    queue.enqueue(payload, error="offline")
    queue.enqueue(payload, error="still offline")
    assert queue.counts() == {"pending": 1, "failed": 0}
    assert len(queue.pending()) == 1
    queue.retryable_failure("event-1", "retry later")
    assert queue.counts() == {"pending": 1, "failed": 0}
    assert queue.pending() == []
    queue.terminal_failure("event-1", "STUDENT_NOT_FOUND", 404)
    assert queue.counts() == {"pending": 0, "failed": 1}
    with queue._connect() as connection:
        failure = connection.execute("SELECT event_id,error_code,http_status FROM event_failures").fetchone()
    assert tuple(failure) == ("event-1", "STUDENT_NOT_FOUND", 404)
    assert (tmp_path / "queue.sqlite3").stat().st_mode & 0o777 == 0o600


def test_device_client_refuses_plain_http_by_default(tmp_path: Path):
    with pytest.raises(ValueError, match="HTTPS is required"):
        DeviceClient("http://192.0.2.10", "PI-01", state_dir=tmp_path)
    client = DeviceClient("http://127.0.0.1:3000/api", "PI-01", state_dir=tmp_path, allow_insecure_local_http=True)
    assert client.api_root == "http://127.0.0.1:3000/api/"


def test_registration_saves_credential_once_and_does_not_return_it(tmp_path: Path):
    secret = "one-time-device-credential-not-for-logs"
    session = FakeSession(FakeResponse(201, {"data": {"device_id": "PI-01", "status": "pending", "credential": secret}}))
    client = DeviceClient("https://attendance.example.test/api", "PI-01", state_dir=tmp_path, session=session)
    result = client.register("one-time-enrollment-token", "test-1")
    assert result == {"device_id": "PI-01", "status": "pending", "credential_saved": True}
    assert secret not in repr(result)
    assert session.last is not None
    assert session.last[2]["verify"] is True
    assert session.last[2]["allow_redirects"] is False
    saved = tmp_path / "device-credentials.json"
    assert saved.stat().st_mode & 0o777 == 0o600
    assert secret in saved.read_text(encoding="utf-8")


def test_heartbeat_uses_schema_valid_event_id_and_timestamp(tmp_path: Path):
    session = FakeSession(FakeResponse(200, {"data": {"device_id": "PI-01", "event_status": "accepted"}}))
    client = DeviceClient("https://attendance.example.test", "PI-01", credential="long-test-device-credential-value", state_dir=tmp_path, session=session)
    result = client.heartbeat()
    assert result["event_status"] == "accepted"
    assert session.last is not None
    body = session.last[2]["json"]
    assert len(body["event_id"]) >= 8
    assert "T" in body["timestamp"]
    assert "sent_at" not in body
    assert "device_id" not in body


def test_retry_queues_transient_server_error(tmp_path: Path):
    credential = "a-long-test-only-device-credential"
    session = FakeSession(FakeResponse(503, {"error": {"code": "UNAVAILABLE"}}))
    client = DeviceClient("https://attendance.example.test", "PI-01", credential=credential, state_dir=tmp_path, session=session)
    result = client.submit_attendance(session_id="session-1", roll_number="CS-01", sensor_type="unspecified")
    assert result["delivery"] == "queued"
    assert client.queue.counts() == {"pending": 1, "failed": 0}
