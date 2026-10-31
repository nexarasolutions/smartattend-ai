from typing import Any, cast

from marshmallow import RAISE, Schema, ValidationError, fields, validate, validates_schema


class StrictSchema(Schema):
    class Meta:
        unknown = RAISE

    def load_object(self, data: Any) -> dict[str, Any]:
        loaded = self.load(data)
        if not isinstance(loaded, dict):
            raise ValidationError("Expected a JSON object.")
        return cast(dict[str, Any], loaded)


class AttendanceMarkSchema(StrictSchema):
    session_id = fields.UUID(required=True)
    student_id = fields.UUID(required=True)
    status = fields.String(required=True, validate=validate.OneOf(["Present", "Absent", "Late"]))
    reason = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=500))


class CorrectionRequestSchema(StrictSchema):
    requested_status = fields.String(required=True, validate=validate.OneOf(["Present", "Absent", "Late"]))
    reason = fields.String(required=True, validate=validate.Length(min=8, max=500))


class CorrectionReviewSchema(StrictSchema):
    decision = fields.String(required=True, validate=validate.OneOf(["approve", "reject"]))
    review_note = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=500))


class DeviceRegisterSchema(StrictSchema):
    device_id = fields.String(required=True, validate=validate.Regexp(r"^[A-Za-z0-9._-]{3,80}$"))
    firmware_version = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=48))


class DeviceActivationSchema(StrictSchema):
    classroom_id = fields.UUID(allow_none=True)


class DeviceUpdateSchema(StrictSchema):
    classroom_id = fields.UUID(allow_none=True)
    status = fields.String(validate=validate.OneOf(["active", "revoked", "pending"]))


class DeviceHeartbeatSchema(StrictSchema):
    event_id = fields.String(required=True, validate=validate.Length(min=8, max=120))
    timestamp = fields.DateTime(required=True)
    firmware_version = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=48))
    health = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=dict)

    @validates_schema
    def validate_health_size(self, data, **kwargs):
        if len(data.get("health", {})) > 24:
            raise ValidationError("health may contain at most 24 keys.", field_name="health")


class DeviceAttendanceSchema(StrictSchema):
    event_id = fields.String(required=True, validate=validate.Length(min=8, max=120))
    idempotency_key = fields.String(required=True, validate=validate.Length(min=8, max=120))
    timestamp = fields.DateTime(required=True)
    session_id = fields.UUID(required=True)
    roll_number = fields.String(required=True, validate=validate.Length(min=1, max=48))
    status = fields.String(load_default="Present", validate=validate.OneOf(["Present", "Absent", "Late"]))
    sensor_type = fields.String(load_default="unspecified", validate=validate.OneOf(["unspecified", "rfid", "qr", "fingerprint", "camera", "other"]))
    sensor_reference = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=120))
