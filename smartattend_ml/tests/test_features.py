from datetime import datetime, timedelta, timezone

from smartattend_ml.features import AttendancePoint, build_training_samples, chronological_split


def make_points(count=36):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        AttendancePoint("student-a", "subject-a", start + timedelta(days=7 * index), "Absent" if index % 5 == 0 else "Present")
        for index in range(count)
    ]


def test_training_features_exclude_future_attendance():
    original = make_points()
    changed_future = [*original[:12], *[
        AttendancePoint(point.student_id, point.subject_id, point.session_at, "Absent") for point in original[12:]
    ]]
    first = build_training_samples(original)
    second = build_training_samples(changed_future)
    cutoff = original[9].session_at
    first_window = next(sample for sample in first if sample["cutoff_at"] == cutoff)
    second_window = next(sample for sample in second if sample["cutoff_at"] == cutoff)
    assert first_window["features"] == second_window["features"]
    assert first_window["target"] != second_window["target"]


def test_chronological_split_purges_training_future_labels():
    samples = build_training_samples(make_points())
    training, validation, split_at = chronological_split(samples, test_fraction=0.2)
    assert training and len(validation) >= 2
    assert max(sample["target_end"] for sample in training) < split_at
    assert min(sample["cutoff_at"] for sample in validation) >= split_at
