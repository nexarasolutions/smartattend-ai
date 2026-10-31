from flask import g

from ..extensions import db
from ..models import AuditLog


def record_audit(action: str, entity_type: str, entity_id=None, before=None, after=None, actor_user_id=None):
    if actor_user_id is None:
        actor = getattr(g, "current_user", None)
        actor_user_id = actor.id if actor is not None else None
    db.session.add(AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before_state=before,
        after_state=after,
        request_id=getattr(g, "request_id", None),
    ))
