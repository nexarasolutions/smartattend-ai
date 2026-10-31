from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, TypedDict

FEATURE_NAMES = (
    "total_classes",
    "present_classes",
    "attendance_percentage",
    "recent_attendance_percentage",
    "attendance_trend",
)
MIN_HISTORY = 3
FUTURE_HORIZON = 3


@dataclass(frozen=True)
class AttendancePoint:
    student_id: object
    subject_id: object
    session_at: datetime
    status: str


class TrainingSample(TypedDict):
    student_id: object
    subject_id: object
    features: dict[str, float]
    target: float
    cutoff_at: datetime
    target_end: datetime


def _present(status: str) -> float:
    return 1.0 if status in {"Present", "Late"} else 0.0


def _trend(values: list[float]) -> float:
    """Least-squares slope over the observed sequence, independent of future rows."""
    if len(values) < 2:
        return 0.0
    center = (len(values) - 1) / 2
    denominator = sum((index - center) ** 2 for index in range(len(values)))
    if denominator == 0:
        return 0.0
    mean = sum(values) / len(values)
    return float(sum((index - center) * (value - mean) for index, value in enumerate(values)) / denominator)


def features_from_history(history: list[AttendancePoint]) -> dict[str, float] | None:
    """Build the feature vector from records available as of the prediction cutoff."""
    if len(history) < MIN_HISTORY:
        return None
    observed = [_present(point.status) for point in history]
    recent = observed[-5:]
    total = len(observed)
    present = sum(observed)
    return {
        "total_classes": float(total),
        "present_classes": float(present),
        "attendance_percentage": 100.0 * present / total,
        "recent_attendance_percentage": 100.0 * sum(recent) / len(recent),
        "attendance_trend": _trend(recent),
    }


def build_training_samples(
    points: Iterable[AttendancePoint], *, min_history: int = MIN_HISTORY, horizon: int = FUTURE_HORIZON
) -> list[TrainingSample]:
    """Create rolling examples. Each feature sees only the past; each label is a later window."""
    if min_history < 2 or horizon < 1:
        raise ValueError("min_history must be at least 2 and horizon must be positive")
    grouped: dict[tuple[object, object], list[AttendancePoint]] = defaultdict(list)
    for point in points:
        grouped[(point.student_id, point.subject_id)].append(point)
    samples: list[TrainingSample] = []
    for (student_id, subject_id), rows in grouped.items():
        rows.sort(key=lambda item: item.session_at)
        for index in range(min_history, len(rows) - horizon + 1):
            past = rows[:index]
            future = rows[index : index + horizon]
            observed_features = features_from_history(past)
            if observed_features is None or not future:
                continue
            samples.append(
                {
                    "student_id": student_id,
                    "subject_id": subject_id,
                    "features": observed_features,
                    "target": 100.0 * sum(_present(item.status) for item in future) / len(future),
                    "cutoff_at": past[-1].session_at,
                    "target_end": future[-1].session_at,
                }
            )
    return sorted(samples, key=lambda sample: (sample["cutoff_at"], str(sample["student_id"]), str(sample["subject_id"])))


def chronological_split(
    samples: list[TrainingSample], *, test_fraction: float = 0.2
) -> tuple[list[TrainingSample], list[TrainingSample], datetime]:
    """Split on time and purge training labels that overlap the validation start."""
    if not 0.05 <= test_fraction < 0.5:
        raise ValueError("test_fraction must be between 0.05 and 0.5")
    cutoffs = sorted({sample["cutoff_at"] for sample in samples})
    if len(cutoffs) < 5:
        raise ValueError("At least five distinct chronological cutoffs are required")
    split_index = min(max(1, int(len(cutoffs) * (1 - test_fraction))), len(cutoffs) - 1)
    validation_start = cutoffs[split_index]
    training = [sample for sample in samples if sample["target_end"] < validation_start]
    validation = [sample for sample in samples if sample["cutoff_at"] >= validation_start]
    if len(training) < 4 or len(validation) < 2:
        raise ValueError("Not enough observations on both sides of the purged chronological split")
    if any(sample["target_end"] >= validation_start for sample in training):
        raise AssertionError("Chronological purge failed: a training target overlaps validation")
    return training, validation, validation_start
