from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from backend.app.extensions import db
from backend.app.models import AttendanceRecord, ClassSession, MLModelVersion, Student
from smartattend_ml.features import FEATURE_NAMES, AttendancePoint, build_training_samples, chronological_split


def fetch_attendance_points() -> list[AttendancePoint]:
    rows = (
        db.session.query(AttendanceRecord.student_id, ClassSession.subject_id, ClassSession.starts_at, AttendanceRecord.status)
        .join(ClassSession, AttendanceRecord.session_id == ClassSession.id)
        .join(Student, AttendanceRecord.student_id == Student.id)
        .filter(Student.status == "active", ClassSession.status != "cancelled")
        .order_by(ClassSession.starts_at.asc(), AttendanceRecord.student_id.asc(), ClassSession.subject_id.asc())
        .all()
    )
    return [AttendancePoint(student_id=row[0], subject_id=row[1], session_at=row[2], status=row[3]) for row in rows]


def train_candidate() -> dict[str, object]:
    """Train a candidate model, score only future data, and leave activation to an Admin."""
    samples = build_training_samples(fetch_attendance_points())
    if len(samples) < 12:
        raise ValueError("At least 12 causally valid rolling training windows are required; no model was created.")
    training, validation, validation_start = chronological_split(samples)
    x_train = pd.DataFrame([sample["features"] for sample in training], columns=cast(Any, list(FEATURE_NAMES)), dtype=float)
    y_train = np.asarray([sample["target"] for sample in training], dtype=float)
    x_validation = pd.DataFrame([sample["features"] for sample in validation], columns=cast(Any, list(FEATURE_NAMES)), dtype=float)
    y_validation = np.asarray([sample["target"] for sample in validation], dtype=float)

    model = RandomForestRegressor(
        n_estimators=300,
        max_features=1.0,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    raw_predictions = model.predict(x_validation)
    evaluated_predictions = np.clip(raw_predictions, 0.0, 100.0)
    baseline_predictions = x_validation["attendance_percentage"].to_numpy(dtype=float)
    mae = float(mean_absolute_error(y_validation, evaluated_predictions))
    rmse = float(np.sqrt(mean_squared_error(y_validation, evaluated_predictions)))
    baseline_mae = float(mean_absolute_error(y_validation, baseline_predictions))
    r2 = float(r2_score(y_validation, evaluated_predictions)) if len(y_validation) > 1 and np.ptp(y_validation) > 0 else None
    metrics = {
        "chronological_split": "purged rolling-origin holdout",
        "validation_start": validation_start.isoformat(),
        "training_samples": int(len(training)),
        "validation_samples": int(len(validation)),
        "mae_percentage_points": round(mae, 4),
        "rmse_percentage_points": round(rmse, 4),
        "r2": round(r2, 4) if r2 is not None else None,
        "persistence_baseline_mae_percentage_points": round(baseline_mae, 4),
        "beats_persistence_baseline": bool(mae < baseline_mae),
        "confidence_calibrated": False,
        "limitations": "Evaluation uses historic rolling windows; confidence intervals are not calibrated. Individual estimates are not guarantees.",
    }
    importance = {name: round(float(value), 6) for name, value in sorted(zip(FEATURE_NAMES, model.feature_importances_), key=lambda pair: pair[1], reverse=True)}
    artifact_buffer = io.BytesIO()
    joblib.dump({"model": model, "feature_names": list(FEATURE_NAMES)}, artifact_buffer, compress=3)
    artifact = artifact_buffer.getvalue()
    digest = hashlib.sha256(artifact).hexdigest()
    trained_at = datetime.now(timezone.utc)
    version = f"rf-attendance-{trained_at.strftime('%Y%m%d%H%M%S')}-{digest[:8]}"
    candidate = MLModelVersion(
        model_version=version,
        algorithm="RandomForestRegressor",
        artifact=artifact,
        artifact_sha256=digest,
        feature_names=list(FEATURE_NAMES),
        evaluation_metrics=metrics,
        feature_importance=importance,
        training_rows=len(training),
        training_cutoff=validation_start,
        state="candidate",
    )
    db.session.add(candidate)
    db.session.commit()
    return {"model_version": version, "state": candidate.state, "algorithm": candidate.algorithm, "training_rows": candidate.training_rows, "feature_names": list(FEATURE_NAMES), "evaluation_metrics": metrics, "feature_importance": importance}
