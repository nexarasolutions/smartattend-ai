from ..extensions import db
from ..models import Notification


def add_user_notification(user_id, *, kind: str, title: str, body: str) -> Notification:
    """Queue a database-backed in-app notification in the caller's transaction."""
    item = Notification(user_id=user_id, kind=kind, title=title[:160], body=body[:1000])
    db.session.add(item)
    return item
