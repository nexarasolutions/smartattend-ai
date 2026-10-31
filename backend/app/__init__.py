from __future__ import annotations

import uuid
import hmac
import os
from pathlib import Path

import click
from flask import Flask, abort, g, jsonify, request, send_from_directory
from flask_cors import CORS
from marshmallow import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import safe_join

from .config import Config
from .extensions import db, migrate


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    app.config.update(Config.from_environment())
    app.config["PUBLIC_DIST_DIRECTORY"] = str(Path(__file__).resolve().parents[2] / "dist")

    test_config = test_config or {}
    app.config.update(test_config)
    if app.config.get("TESTING"):
        app.config.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
        if str(app.config.get("SQLALCHEMY_DATABASE_URI", "")).startswith("sqlite:"):
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)
    app.config["SESSION_COOKIE_NAME"] = "smartattend_session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "None" if app.config.get("SESSION_COOKIE_SECURE", True) else "Lax"

    if app.config.get("SQLALCHEMY_DATABASE_URI"):
        db.init_app(app)
        migrate.init_app(app, db, directory=str(Path(__file__).resolve().parents[1] / "migrations"))
    elif app.config.get("TESTING"):
        db.init_app(app)
        migrate.init_app(app, db, directory=str(Path(__file__).resolve().parents[1] / "migrations"))

    allowed_origins = list(app.config.get("ALLOWED_ORIGINS", ()))
    if allowed_origins:
        CORS(app, resources={r"/api/*": {"origins": allowed_origins, "supports_credentials": True}}, allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key", "X-Device-Enrollment-Token", "X-Admin-Bootstrap-Token", "X-CSRF-Token"])

    @app.before_request
    def assign_request_id():
        g.request_id = str(uuid.uuid4())
        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.cookies.get("smartattend_session") and request.path not in {"/api/auth/logout"}:
            cookie_token = request.cookies.get("smartattend_csrf", "")
            header_token = request.headers.get("X-CSRF-Token", "")
            if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
                return jsonify(error={"code": "CSRF_VALIDATION_FAILED", "message": "Refresh the application security token and retry."}, request_id=g.request_id), 403

    @app.after_request
    def secure_api_headers(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        if request.path.startswith("/api/") or request.path.startswith("/_app/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValidationError)
    def invalid_payload(error):
        return jsonify(error={"code": "VALIDATION_ERROR", "message": "The request did not match the expected schema.", "details": error.messages}, request_id=g.get("request_id")), 400

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        if app.config.get("SQLALCHEMY_DATABASE_URI"):
            db.session.rollback()
        app.logger.error("database operation failed request_id=%s", g.get("request_id"))
        return jsonify(error={"code": "DATABASE_ERROR", "message": "The database operation could not be completed."}, request_id=g.get("request_id")), 503

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error={"code": "REQUEST_TOO_LARGE", "message": "Request body exceeds the configured limit."}, request_id=g.get("request_id")), 413

    @app.get("/_app/health")
    def liveness():
        return jsonify(status="ok", service="smartattend-api", request_id=g.get("request_id")), 200

    @app.get("/api/health/ready")
    def readiness():
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            return jsonify(error={"code": "DATABASE_NOT_CONFIGURED", "message": "The application database is not configured."}, request_id=g.get("request_id")), 503
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(data={"status": "ready", "database": "connected"}, request_id=g.get("request_id")), 200
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify(error={"code": "DATABASE_NOT_READY", "message": "The application database is unavailable."}, request_id=g.get("request_id")), 503

    @app.get("/api/system/status")
    def system_status():
        return jsonify(data={
            "service": "smartattend-api",
            "database_configured": bool(app.config.get("SQLALCHEMY_DATABASE_URI")),
            "database_provider": "supabase" if app.config.get("SQLALCHEMY_DATABASE_URI") else None,
            "authentication_configured": bool(app.config.get("SUPABASE_JWT_SECRET")),
            "first_admin_bootstrap_configured": bool(app.config.get("BOOTSTRAP_TOKEN")),
            "demo_data_is_live": False,
        }, request_id=g.get("request_id"))

    from .api import register_blueprints
    register_blueprints(app)
    _register_cli(app)
    _register_spa(app)
    return app


def _register_cli(app: Flask) -> None:
    @app.cli.command("provision-admin")
    @click.option("--open-id", required=True, help="Supabase user UUID for a user who has already completed sign-in.")
    def provision_admin(open_id: str) -> None:
        """Operator-only fallback that consumes the same one-time first-Admin state as the API."""
        from .models import AuditLog, BootstrapState, User, utcnow

        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            raise click.ClickException("DATABASE_URL is not configured.")
        if User.query.filter_by(role="Admin", status="active").first() or BootstrapState.query.filter_by(id="initial-admin").first():
            raise click.ClickException("First-Admin bootstrap has already been consumed; use Admin user management instead.")
        user = User.query.filter_by(open_id=open_id).with_for_update().one_or_none()
        if user is None or user.status != "pending" or user.role is not None:
            raise click.ClickException("Only a pre-existing pending account with no role is eligible for first-Admin provisioning.")
        user.role = "Admin"
        user.status = "active"
        db.session.add(BootstrapState(id="initial-admin", consumed_by_user_id=user.id, consumed_at=utcnow()))
        db.session.add(AuditLog(actor_user_id=user.id, action="first_admin_provisioned", entity_type="users", entity_id=str(user.id), after_state={"role": "Admin", "status": "active"}))
        try:
            db.session.commit()
        except IntegrityError as error:
            db.session.rollback()
            raise click.ClickException("First-Admin bootstrap was consumed concurrently; no additional Admin was created.") from error
        click.echo(f"Admin role provisioned for {user.email} ({user.id}).")


def _register_spa(app: Flask) -> None:
    @app.get("/")
    def serve_spa():
        return send_from_directory(app.config["PUBLIC_DIST_DIRECTORY"], "index.html")

    @app.get("/<path:requested_path>")
    def serve_static_or_spa(requested_path: str):
        directory = app.config["PUBLIC_DIST_DIRECTORY"]
        if any(requested_path == prefix or requested_path.startswith(prefix + "/") for prefix in ("api", "_app", "__system__")):
            abort(404)
        safe_path = safe_join(directory, requested_path)
        if safe_path and os.path.isfile(safe_path):
            return send_from_directory(directory, requested_path)
        if "." in requested_path.rsplit("/", 1)[-1]:
            abort(404)
        return send_from_directory(directory, "index.html")
