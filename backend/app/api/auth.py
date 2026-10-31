from __future__ import annotations

import secrets
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from flask import Blueprint, current_app, jsonify, make_response, request

from ..extensions import db
from ..models import AuditLog, BootstrapState, User, utcnow
from ..security import request_identity
from ..services.http import fail, success


auth_bp = Blueprint("auth", __name__)
CSRF_COOKIE = "smartattend_csrf"


@auth_bp.get("/auth/me")
def who_am_i():
    """Validate Supabase JWT from Authorization header and return user profile."""
    identity = request_identity()
    if identity is None:
        return fail("UNAUTHENTICATED", "Sign in is required.", 401)
    if not current_app.config.get("SQLALCHEMY_DATABASE_URI"):
        return fail("DATABASE_NOT_CONFIGURED", "The application database is not available.", 503)
    try:
        user = User.query.filter_by(open_id=identity["open_id"]).one_or_none()
        if user is None:
            # First time this Supabase user hits the API: create a pending profile
            email = identity.get("email", "")
            display_name = (email.split("@", 1)[0] if email else identity["open_id"][:20])
            try:
                user = User(
                    open_id=identity["open_id"],
                    email=email.lower() if email else f"{identity['open_id']}@supabase.local",
                    display_name=display_name,
                    role=None,
                    status="pending",
                )
                db.session.add(user)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                user = User.query.filter_by(open_id=identity["open_id"]).one_or_none()
            if user is None:
                return fail("ACCOUNT_CONFLICT", "The account could not be created. Contact an administrator.", 409)
        return success({
            "authenticated": True,
            "account_state": user.status,
            "role": user.role,
            "open_id": user.open_id,
            "email": user.email,
            "display_name": user.display_name,
        })
    except SQLAlchemyError:
        db.session.rollback()
        return fail("DATABASE_UNAVAILABLE", "The application database is not available.", 503)


@auth_bp.get("/auth/csrf")
def csrf_token():
    """Issue a CSRF token cookie for state-changing requests."""
    token = secrets.token_urlsafe(32)
    secure = bool(current_app.config.get("SESSION_COOKIE_SECURE", True))
    same_site = "None" if secure else "Lax"
    response, status = success({"csrf_token": token})
    response.set_cookie(CSRF_COOKIE, token, max_age=8 * 60 * 60, httponly=False, secure=secure, samesite=same_site, path="/")
    return response, status


@auth_bp.post("/auth/logout")
def logout():
    """Clear session cookies."""
    response = make_response(jsonify(data={"logged_out": True}))
    secure = bool(current_app.config.get("SESSION_COOKIE_SECURE", True))
    same_site = "None" if secure else "Lax"
    response.delete_cookie("smartattend_session", path="/", secure=secure, httponly=True, samesite=same_site)
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, samesite=same_site)
    response.headers["Cache-Control"] = "no-store"
    return response


@auth_bp.post("/admin/bootstrap")
def bootstrap_first_admin():
    """
    One-time endpoint to grant Admin role to the first signed-in user.
    Requires X-Admin-Bootstrap-Token header matching SMARTATTEND_BOOTSTRAP_TOKEN env var.
    """
    identity = request_identity()
    if identity is None:
        return fail("UNAUTHENTICATED", "Sign in is required.", 401)

    provided_token = request.headers.get("X-Admin-Bootstrap-Token", "").strip()
    configured_token = current_app.config.get("BOOTSTRAP_TOKEN", "")
    if not provided_token or not configured_token or not secrets.compare_digest(provided_token, configured_token):
        return fail("BOOTSTRAP_TOKEN_INVALID", "The bootstrap token is missing or incorrect.", 403)

    if not current_app.config.get("SQLALCHEMY_DATABASE_URI"):
        return fail("DATABASE_NOT_CONFIGURED", "The application database is not available.", 503)

    try:
        if (User.query.filter_by(role="Admin", status="active").first() or
                BootstrapState.query.filter_by(id="initial-admin").first()):
            return fail("BOOTSTRAP_ALREADY_CONSUMED", "The first-admin bootstrap has already been used.", 409)

        user = User.query.filter_by(open_id=identity["open_id"]).with_for_update().one_or_none()
        if user is None:
            return fail("ACCOUNT_NOT_FOUND", "Sign in first before using the bootstrap token.", 404)
        if user.role is not None:
            return fail("ROLE_ALREADY_SET", "This account already has a role assigned.", 409)

        user.role = "Admin"
        user.status = "active"
        db.session.add(BootstrapState(id="initial-admin", consumed_by_user_id=user.id, consumed_at=utcnow()))
        db.session.add(AuditLog(
            actor_user_id=user.id,
            action="first_admin_provisioned",
            entity_type="users",
            entity_id=str(user.id),
            after_state={"role": "Admin", "status": "active"},
        ))
        db.session.commit()
        return success({"provisioned": True, "role": "Admin", "email": user.email})
    except IntegrityError:
        db.session.rollback()
        return fail("BOOTSTRAP_ALREADY_CONSUMED", "Bootstrap was consumed concurrently.", 409)
    except SQLAlchemyError:
        db.session.rollback()
        return fail("DATABASE_UNAVAILABLE", "The application database is not available.", 503)
