from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from flask import g, jsonify
from marshmallow import ValidationError


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def success(data, status: int = 200):
    response = jsonify(data=data, request_id=getattr(g, "request_id", None))
    return response, status


def fail(code: str, message: str, status: int = 400, details=None):
    body = {"error": {"code": code, "message": message}, "request_id": getattr(g, "request_id", None)}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def load_json(schema, payload=None):
    try:
        return schema.load(payload if payload is not None else __import__("flask").request.get_json(silent=False) or {})
    except ValidationError as error:
        raise error
