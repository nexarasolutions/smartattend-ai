from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, g

from ..extensions import db
from ..models import Notification
from ..security import roles_required
from ..services.http import fail, success
from ..services.serialization import iso


notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.get("/notifications")
@roles_required("Admin", "Staff", "Student")
def list_notifications():
    rows = Notification.query.filter_by(user_id=g.current_user.id).order_by(Notification.created_at.desc()).limit(100).all()
    return success([{"id": str(item.id), "kind": item.kind, "title": item.title, "body": item.body, "read_at": iso(item.read_at), "created_at": iso(item.created_at)} for item in rows])


@notifications_bp.patch("/notifications/<uuid:notification_id>/read")
@roles_required("Admin", "Staff", "Student")
def mark_read(notification_id):
    item = Notification.query.filter_by(id=notification_id, user_id=g.current_user.id).one_or_none()
    if item is None:
        return fail("NOTIFICATION_NOT_FOUND", "The notification was not found.", 404)
    if item.read_at is None:
        item.read_at = datetime.now(timezone.utc)
        db.session.commit()
    return success({"id": str(item.id), "read_at": iso(item.read_at)})
