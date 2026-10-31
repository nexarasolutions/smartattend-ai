from __future__ import annotations

from functools import wraps
from typing import Callable

import jwt
from flask import current_app, g, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import User


def request_identity() -> dict | None:
    """Extract and validate JWT from Authorization header or session cookie.

    Tries Supabase JWT first (via SUPABASE_JWT_SECRET), then falls back to
    app-issued JWT (for device auth and other internal tokens).
    """
    token = None
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = request.cookies.get("smartattend_session")
    if not token:
        # Backward-compat: also check the old cookie name used in development
        token = request.cookies.get("webdev_app_session")
    if not token:
        return None

    # 1. Try Supabase JWT (primary auth for web users)
    supabase_secret = current_app.config.get("SUPABASE_JWT_SECRET")
    if supabase_secret:
        try:
            payload = jwt.decode(
                token,
                supabase_secret,
                algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )
            sub = payload.get("sub")
            if sub:
                user_metadata = payload.get("user_metadata") or {}
                return {
                    "open_id": str(sub),
                    "email": payload.get("email"),
                    "name": user_metadata.get("name") or user_metadata.get("full_name"),
                    "role": user_metadata.get("role"),
                    "source": "supabase",
                }
        except jwt.PyJWTError:
            pass

    # 2. Try app-issued JWT (device enrollment, internal service tokens)
    app_secret = current_app.config.get("APP_JWT_SECRET")
    if app_secret:
        try:
            payload = jwt.decode(token, app_secret, algorithms=["HS256"], options={"require": ["exp"]})
            if payload.get("iss") == "smartattend" and payload.get("sub"):
                return {"open_id": payload["sub"], "source": "application"}
        except jwt.PyJWTError:
            pass

    return None


def load_current_user() -> User | None:
    identity = request_identity()
    if identity is None:
        return None
    try:
        user = db.session.query(User).filter_by(open_id=identity["open_id"]).one_or_none()
    except SQLAlchemyError as error:
        db.session.rollback()
        raise RuntimeError("database_unavailable") from error
    if user is not None:
        g.current_user = user
        g.identity_source = identity.get("source")
    return user


def authenticated(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_app.config.get("SQLALCHEMY_DATABASE_URI"):
            return jsonify(error={"code": "DATABASE_NOT_CONFIGURED", "message": "The application database is not configured."}), 503
        try:
            user = load_current_user()
        except RuntimeError:
            return jsonify(error={"code": "DATABASE_UNAVAILABLE", "message": "The application database is not available."}), 503
        if user is None:
            return jsonify(error={"code": "UNAUTHENTICATED", "message": "Sign in is required."}), 401
        if user.status != "active" or user.role is None:
            return jsonify(error={"code": "ACCOUNT_PENDING", "message": "Your account is awaiting administrator provisioning."}), 403
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles: str):
    def decorate(view: Callable):
        @wraps(view)
        @authenticated
        def wrapped(*args, **kwargs):
            user: User = g.current_user
            if user.role not in roles:
                return jsonify(error={"code": "FORBIDDEN", "message": "This role cannot perform that operation."}), 403
            return view(*args, **kwargs)
        return wrapped
    return decorate
