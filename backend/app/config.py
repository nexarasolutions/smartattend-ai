from __future__ import annotations

import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300, "pool_size": 2, "max_overflow": 3}
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = 1024 * 1024
    SESSION_COOKIE_NAME = "smartattend_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    JWT_ALGORITHM = "HS256"
    JWT_TTL_SECONDS = 8 * 60 * 60
    ALLOWED_ORIGINS = tuple(origin.strip() for origin in os.getenv("SMARTATTEND_ALLOWED_ORIGINS", "").split(",") if origin.strip())
    DEVICE_HEARTBEAT_OFFLINE_SECONDS = int(os.getenv("SMARTATTEND_HEARTBEAT_OFFLINE_SECONDS", "300"))
    BOOTSTRAP_TOKEN = os.getenv("SMARTATTEND_BOOTSTRAP_TOKEN")
    APP_JWT_SECRET = os.getenv("SMARTATTEND_JWT_SECRET")
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

    @classmethod
    def from_environment(cls) -> dict[str, object]:
        """Read database and auth configuration from environment at runtime only."""
        secure_cookie = os.getenv("SMARTATTEND_COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}
        database_url = os.getenv("DATABASE_URL", "")
        # Supabase / Render use postgres:// but SQLAlchemy needs postgresql+psycopg2://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif database_url.startswith("postgresql://") and "+psycopg2" not in database_url:
            database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        raw_origins = [origin.strip() for origin in os.getenv("SMARTATTEND_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
        # Always allow Vercel domains and local development
        default_origins = [
            "https://smartattend-ai.vercel.app",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
        ]
        for o in default_origins:
            if o not in raw_origins:
                raw_origins.append(o)

        return {
            "SESSION_COOKIE_NAME": "smartattend_session",
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SECURE": secure_cookie,
            "SESSION_COOKIE_SAMESITE": "None" if secure_cookie else "Lax",
            "APP_JWT_SECRET": os.getenv("SMARTATTEND_JWT_SECRET"),
            "SUPABASE_JWT_SECRET": os.getenv("SUPABASE_JWT_SECRET"),
            "SUPABASE_URL": os.getenv("SUPABASE_URL"),
            "SUPABASE_ANON_KEY": os.getenv("SUPABASE_ANON_KEY"),
            "SQLALCHEMY_DATABASE_URI": database_url if database_url else None,
            "BOOTSTRAP_TOKEN": os.getenv("SMARTATTEND_BOOTSTRAP_TOKEN"),
            "REQUIRE_HTTPS": os.getenv("SMARTATTEND_REQUIRE_HTTPS", "true").lower() not in {"0", "false", "no"},
            "DEVICE_HEARTBEAT_OFFLINE_SECONDS": int(os.getenv("SMARTATTEND_HEARTBEAT_OFFLINE_SECONDS", "300")),
            "ALLOWED_ORIGINS": tuple(raw_origins),
        }
