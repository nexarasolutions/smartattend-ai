from __future__ import annotations

import hashlib
import io
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd

from backend.app.extensions import db
from backend.app.models import AttendanceRecord, ClassSession, MLPrediction, MLModelVersion, Student
from smartattend_ml.features import FEATURE_NAMES, AttendancePoint, features_from_history
from smartattend_ml.training import fetch_attendance_points


def risk_category(value: float) -> str:
    if value < 65.0:
        return "high"
    if value < 75.0:
        return "moderate"
    return "low"


def generate_current_predictions() -> dict[str, object]:
    active = MLModelVersion.query.filter_by(state="active").one_or_none()
    if active is None:
        raise ValueError("No active, Admin-approved model is available.")
    artifact = bytes(active.artifact)
    if hashlib.sha256(artifact).hexdigest() != active.artifact_sha256:
        raise ValueError("The active model artifact failed its integrity check.")
    bundle = joblib.load(io.BytesIO(artifact))
    model = bundle["model"]
    points = fetch_attendance_points()
    grouped: dict[tuple[object, object], list[AttendancePoint]] = defaultdict(list)
    for point in points:
        grouped[(point.student_id, point.subject_id)].append(point)

    added = updated = skipped = 0
    generated_at = datetime.now(timezone.utc)
    importance = active.feature_importance or {}
    top_features = sorted(importance.items(), key=lambda item: item[1], reverse=True)[:3]
    feature_notes = {name: float(weight) for name, weight in top_features}
    for (student_id, subject_id), history in grouped.items():
        history.sort(key=lambda item: item.session_at)
        features = features_from_history(history)
        if features is None:
            skipped += 1
            continue
        vector = pd.DataFrame([[features[name] for name in FEATURE_NAMES]], columns=cast(Any, list(FEATURE_NAMES)), dtype=float)
        predicted = float(np.clip(model.predict(vector)[0], 0.0, 100.0))
        cutoff = history[-1].session_at
        record = MLPrediction.query.filter_by(student_id=student_id, subject_id=subject_id, model_version=active.model_version, cutoff_at=cutoff).one_or_none()
        if record is None:
            record = MLPrediction(student_id=student_id, subject_id=subject_id, model_version=active.model_version, cutoff_at=cutoff)
            db.session.add(record)
            added += 1
        else:
            updated += 1
        record.predicted_percentage = round(predicted, 2)
        record.risk_category = risk_category(predicted)
        record.calibrated_confidence = None
        record.feature_attribution = {"global_feature_importance": feature_notes, "input_features": features}
        record.generated_at = generated_at
    db.session.commit()
    return {"model_version": active.model_version, "created": added, "updated": updated, "skipped_insufficient_history": skipped, "generated_at": generated_at.isoformat(), "confidence_calibrated": False}
