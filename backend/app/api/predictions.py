from __future__ import annotations

from flask import Blueprint, g, request

from ..extensions import db
from ..models import MLPrediction, MLModelVersion, Student
from ..security import roles_required
from ..services.access import scoped_student_query
from ..services.audit import record_audit
from ..services.http import fail, success
from ..services.serialization import prediction_record
from smartattend_ml.prediction_service import generate_current_predictions
from smartattend_ml.training import train_candidate


predictions_bp = Blueprint("predictions", __name__)


def model_record(model: MLModelVersion) -> dict[str, object]:
    return {
        "model_version": model.model_version,
        "algorithm": model.algorithm,
        "state": model.state,
        "feature_names": model.feature_names,
        "evaluation_metrics": model.evaluation_metrics,
        "feature_importance": model.feature_importance,
        "training_rows": model.training_rows,
        "training_cutoff": model.training_cutoff.isoformat(),
        "trained_at": model.trained_at.isoformat(),
    }


@predictions_bp.get("/predictions")
@roles_required("Admin", "Staff", "Student")
def list_predictions():
    students = scoped_student_query(g.current_user).with_entities(Student.id)
    query = MLPrediction.query.filter(MLPrediction.student_id.in_(students))
    if g.current_user.role == "Student":
        own = Student.query.filter_by(user_id=g.current_user.id, status="active").one_or_none()
        if own is None:
            return fail("STUDENT_PROFILE_NOT_FOUND", "Your student profile has not been provisioned.", 404)
        query = query.filter_by(student_id=own.id)
    if request.args.get("subject_id"):
        query = query.filter_by(subject_id=request.args["subject_id"])
    rows = query.order_by(MLPrediction.generated_at.desc()).limit(500).all()
    return success([prediction_record(item) for item in rows])


@predictions_bp.get("/predictions/me")
@roles_required("Student")
def my_predictions():
    student = Student.query.filter_by(user_id=g.current_user.id, status="active").one_or_none()
    if student is None:
        return fail("STUDENT_PROFILE_NOT_FOUND", "Your student profile has not been provisioned.", 404)
    rows = MLPrediction.query.filter_by(student_id=student.id).order_by(MLPrediction.generated_at.desc()).limit(100).all()
    return success([prediction_record(item) for item in rows])


@predictions_bp.get("/predictions/models")
@roles_required("Admin")
def list_models():
    rows = MLModelVersion.query.order_by(MLModelVersion.trained_at.desc()).limit(50).all()
    return success([model_record(row) for row in rows])


@predictions_bp.post("/predictions/train")
@roles_required("Admin")
def train_model():
    try:
        candidate = train_candidate()
    except ValueError as error:
        return fail("MODEL_TRAINING_UNAVAILABLE", str(error), 422)
    record_audit("ml_model_candidate_trained", "ml_model_versions", candidate["model_version"], after={"state": candidate["state"], "metrics": candidate["evaluation_metrics"]})
    db.session.commit()
    return success(candidate, 201)


@predictions_bp.post("/predictions/models/<string:model_version>/activate")
@roles_required("Admin")
def activate_model(model_version: str):
    candidate = MLModelVersion.query.filter_by(model_version=model_version).with_for_update().one_or_none()
    if candidate is None:
        return fail("MODEL_NOT_FOUND", "The model version was not found.", 404)
    if candidate.state not in {"candidate", "active"}:
        return fail("MODEL_STATE_INVALID", "Only a reviewed candidate can be activated.", 409)
    metrics = candidate.evaluation_metrics or {}
    if int(metrics.get("validation_samples", 0)) < 2 or metrics.get("mae_percentage_points") is None:
        return fail("MODEL_EVALUATION_REQUIRED", "The model has no valid chronological holdout evaluation.", 409)
    if candidate.state == "active":
        return success(model_record(candidate))
    MLModelVersion.query.filter_by(state="active").update({"state": "retired"}, synchronize_session=False)
    candidate.state = "active"
    record_audit("ml_model_activated", "ml_model_versions", candidate.model_version, after={"state": "active", "metrics": metrics})
    db.session.commit()
    return success(model_record(candidate))


@predictions_bp.post("/predictions/generate")
@roles_required("Admin")
def generate_predictions():
    try:
        result = generate_current_predictions()
    except ValueError as error:
        return fail("PREDICTION_GENERATION_UNAVAILABLE", str(error), 409)
    record_audit("ml_predictions_generated", "ml_predictions", result["model_version"], after={key: value for key, value in result.items() if key != "generated_at"})
    db.session.commit()
    return success(result)
