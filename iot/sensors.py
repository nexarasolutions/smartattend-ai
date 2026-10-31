from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AttendanceObservation:
    student_identifier: str
    observed_at: datetime
    status: str = "Present"
    metadata: dict[str, Any] | None = None


class AttendanceSensor(ABC):
    """Adapter contract for a user-selected RFID, QR, biometric or camera sensor."""

    sensor_type: str

    @abstractmethod
    def read_observation(self, timeout_seconds: float = 30.0) -> AttendanceObservation | None:
        """Return one observed student event, or None when no scan is available."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return non-sensitive health metadata for the heartbeat API."""
        raise NotImplementedError
