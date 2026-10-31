from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

import requests

from iot.offline_queue import OfflineEventQueue, default_state_dir


class DeviceAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HTTPSession(Protocol):
    verify: bool

    def request(self, method: str, url: str, **kwargs: Any) -> Any: ...


class DeviceClient:
    """Sensor-neutral Pi client. TLS verification is always on for HTTPS connections."""

    def __init__(
        self,
        api_url: str,
        device_id: str,
        *,
        credential: str | None = None,
        state_dir: str | Path | None = None,
        allow_insecure_local_http: bool = False,
        session: HTTPSession | None = None,
    ) -> None:
        parsed = urlsplit(api_url)
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("SMARTATTEND_API_URL must be an HTTPS origin/path without embedded credentials.")
        if parsed.scheme != "https" and not (allow_insecure_local_http and parsed.scheme == "http"):
            raise ValueError("HTTPS is required for device API traffic. HTTP is allowed only by an explicit local-development override.")
        path = parsed.path.rstrip("/")
        if path.endswith("/api"):
            api_path = path
        elif path:
            raise ValueError("SMARTATTEND_API_URL must be an origin or end in /api.")
        else:
            api_path = "/api"
        self.api_root = f"{parsed.scheme}://{parsed.netloc}{api_path}/"
        self.device_id = device_id
        self.state_dir = Path(state_dir) if state_dir else default_state_dir()
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.credentials_path = self.state_dir / "device-credentials.json"
        self.queue = OfflineEventQueue(self.state_dir / "events.sqlite3")
        self.session = session or requests.Session()
        self.session.verify = True
        self.credential = credential or self._load_credential()

    def _load_credential(self) -> str | None:
        if not self.credentials_path.is_file():
            return None
        try:
            self.credentials_path.chmod(0o600)
            saved = json.loads(self.credentials_path.read_text(encoding="utf-8"))
            if saved.get("device_id") == self.device_id and isinstance(saved.get("credential"), str):
                return saved["credential"]
        except (OSError, ValueError, AttributeError):
            return None
        return None

    def _save_credential(self, credential: str) -> None:
        temporary = self.credentials_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"device_id": self.device_id, "credential": credential}), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.credentials_path)
        self.credential = credential

    def _request(self, method: str, endpoint: str, *, payload: dict[str, Any] | None = None, enrollment_token: str | None = None) -> requests.Response:
        if endpoint not in {"device/register", "device/heartbeat", "device/attendance", "device/status"}:
            raise ValueError("Unsupported device endpoint.")
        headers = {"Accept": "application/json"}
        if self.credential:
            headers["Authorization"] = f"Bearer {self.credential}"
        if enrollment_token:
            headers["X-Device-Enrollment-Token"] = enrollment_token
        try:
            response = self.session.request(
                method,
                self.api_root + endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 20),
                verify=True,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            raise DeviceAPIError("Device API is unreachable; the event may be queued for retry.") from error
        status_code = response.status_code
        if status_code is None:
            raise DeviceAPIError("Device API response did not include a valid HTTP status code.")
        if 300 <= status_code < 400:
            raise DeviceAPIError("Unexpected API redirect refused to protect device credentials.", status_code=status_code)
        return response

    @staticmethod
    def _data(response: requests.Response) -> dict[str, Any]:
        status_code = response.status_code
        if status_code is None:
            raise DeviceAPIError("Device API response did not include a valid HTTP status code.")
        try:
            body = response.json()
        except ValueError as error:
            raise DeviceAPIError("Device API returned a non-JSON response.", status_code=status_code) from error
        if status_code >= 400:
            error = body.get("error", {}) if isinstance(body, dict) else {}
            code = str(error.get("code", "DEVICE_API_ERROR"))
            raise DeviceAPIError(code, status_code=status_code)
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise DeviceAPIError("Device API response is missing its data object.", status_code=status_code)
        return data

    def register(self, enrollment_token: str, firmware_version: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            "device/register",
            enrollment_token=enrollment_token,
            payload={"device_id": self.device_id, "firmware_version": firmware_version},
        )
        data = self._data(response)
        credential = data.get("credential")
        if not isinstance(credential, str) or len(credential) < 32:
            raise DeviceAPIError("Enrollment succeeded without a usable device credential.", status_code=response.status_code)
        self._save_credential(credential)
        return {key: value for key, value in data.items() if key != "credential"} | {"credential_saved": True}

    def heartbeat(self, health: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.credential:
            raise DeviceAPIError("This device has not completed enrollment.")
        now = datetime.now(timezone.utc)
        response = self._request("POST", "device/heartbeat", payload={
            "event_id": str(uuid.uuid4()),
            "timestamp": now.isoformat(),
            "firmware_version": os.getenv("SMARTATTEND_FIRMWARE_VERSION", "unknown"),
            "health": health or {},
        })
        result = self._data(response)
        result["retry"] = self.retry_pending()
        return result

    def status(self) -> dict[str, Any]:
        if not self.credential:
            raise DeviceAPIError("This device has not completed enrollment.")
        response = self._request("GET", "device/status")
        return self._data(response)

    def submit_attendance(
        self,
        *,
        session_id: str,
        roll_number: str,
        status: str = "Present",
        sensor_type: str = "unspecified",
        observed_at: datetime | None = None,
    ) -> dict[str, Any]:
        if status not in {"Present", "Absent", "Late"}:
            raise ValueError("Attendance status must be Present, Absent or Late.")
        if sensor_type not in {"unspecified", "rfid", "qr", "fingerprint", "camera", "other"}:
            raise ValueError("Sensor type must be one of the hardware-neutral supported values.")
        if not self.credential:
            raise DeviceAPIError("This device has not completed enrollment.")
        timestamp = observed_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Attendance timestamps must include an explicit timezone.")
        payload = {
            "event_id": str(uuid.uuid4()),
            "idempotency_key": str(uuid.uuid4()),
            "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
            "session_id": session_id,
            "roll_number": roll_number,
            "status": status,
            "sensor_type": sensor_type[:80],
        }
        return self._send_attendance(payload, queue_on_failure=True)

    def _send_attendance(self, payload: dict[str, Any], *, queue_on_failure: bool) -> dict[str, Any]:
        event_id = payload["event_id"]
        try:
            response = self._request("POST", "device/attendance", payload=payload)
        except DeviceAPIError as error:
            if queue_on_failure:
                self.queue.enqueue(payload, error=str(error))
                return {"event_id": event_id, "delivery": "queued", "reason": str(error)}
            self.queue.retryable_failure(event_id, str(error))
            return {"event_id": event_id, "delivery": "queued", "reason": str(error)}

        status_code = response.status_code
        if status_code is None or status_code == 429 or status_code >= 500:
            reason = f"retryable_http_{status_code if status_code is not None else 'unknown'}"
            if queue_on_failure:
                self.queue.enqueue(payload, error=reason)
            else:
                self.queue.retryable_failure(event_id, reason)
            return {"event_id": event_id, "delivery": "queued", "reason": reason}
        try:
            result = self._data(response)
        except DeviceAPIError as error:
            if queue_on_failure:
                self.queue.enqueue(payload, error=str(error))
            self.queue.terminal_failure(event_id, str(error), error.status_code)
            return {"event_id": event_id, "delivery": "failed", "reason": str(error), "status_code": error.status_code}
        status = result.get("event_status")
        if status in {"accepted", "duplicate"}:
            self.queue.delivered(event_id)
            return {"event_id": event_id, "delivery": "delivered", "event_status": status}
        self.queue.terminal_failure(event_id, "unexpected_device_event_status", status_code)
        return {"event_id": event_id, "delivery": "failed", "reason": "unexpected_device_event_status"}

    def retry_pending(self, limit: int = 100) -> dict[str, int]:
        delivered = failed = attempted = 0
        for item in self.queue.pending(limit):
            attempted += 1
            result = self._send_attendance(item["payload"], queue_on_failure=False)
            if result["delivery"] == "delivered":
                delivered += 1
            elif result["delivery"] == "failed":
                failed += 1
        return {"attempted": attempted, "delivered": delivered, "failed": failed, **self.queue.counts()}
