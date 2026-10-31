from flask import Flask

from .admin import admin_bp
from .attendance import attendance_bp
from .auth import auth_bp
from .devices import devices_bp
from .notifications import notifications_bp
from .predictions import predictions_bp
from .reports import reports_bp
from .staff import staff_bp
from .students import students_bp
from .subjects import subjects_bp


def register_blueprints(app: Flask) -> None:
    for blueprint in (auth_bp, admin_bp, students_bp, staff_bp, subjects_bp, attendance_bp, devices_bp, predictions_bp, notifications_bp, reports_bp):
        app.register_blueprint(blueprint, url_prefix="/api")
