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
            # First time this Supabase user hits the API: create an active profile
            email = identity.get("email", "")
            display_name = identity.get("name") or (email.split("@", 1)[0] if email else identity["open_id"][:20])
            
            # Determine role: use role from metadata if valid, or Admin for first user, otherwise Student
            assigned_role = identity.get("role")
            if assigned_role not in {"Admin", "Staff", "Student"}:
                has_admin = User.query.filter_by(role="Admin", status="active").first() is not None
                assigned_role = "Admin" if not has_admin else "Student"

            try:
                user = User(
                    open_id=identity["open_id"],
                    email=email.lower() if email else f"{identity['open_id']}@supabase.local",
                    display_name=display_name[:160],
                    role=assigned_role,
                    status="active",
                )
                db.session.add(user)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                user = User.query.filter_by(open_id=identity["open_id"]).one_or_none()
            if user is None:
                return fail("ACCOUNT_CONFLICT", "The account could not be created. Contact an administrator.", 409)
        elif user.role is None or user.status == "pending":
            # Auto-activate pending users
            assigned_role = identity.get("role")
            if assigned_role not in {"Admin", "Staff", "Student"}:
                has_admin = User.query.filter_by(role="Admin", status="active").first() is not None
                assigned_role = "Admin" if not has_admin else "Student"
            user.role = assigned_role
            user.status = "active"
            if identity.get("name"):
                user.display_name = identity["name"][:160]
            db.session.commit()

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
    """
    identity = request_identity()
    if identity is None:
        return fail("UNAUTHENTICATED", "Sign in is required.", 401)

    if not current_app.config.get("SQLALCHEMY_DATABASE_URI"):
        return fail("DATABASE_NOT_CONFIGURED", "The application database is not available.", 503)

    try:
        user = User.query.filter_by(open_id=identity["open_id"]).with_for_update().one_or_none()
        if user is None:
            return fail("ACCOUNT_NOT_FOUND", "Sign in first.", 404)

        user.role = "Admin"
        user.status = "active"
        db.session.commit()
        return success({"provisioned": True, "role": "Admin", "email": user.email})
    except SQLAlchemyError:
        db.session.rollback()
        return fail("DATABASE_UNAVAILABLE", "The application database is not available.", 503)
