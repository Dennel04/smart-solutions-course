"""Strict validation for the high-level post-office protocol."""

import json


class ValidationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _require_object(value, name):
    if not isinstance(value, dict):
        raise ValidationError("invalid_input", "%s must be a JSON object." % name)
    return value


def _reject_extra_fields(value, allowed, name):
    extras = set(value) - set(allowed)
    if extras:
        raise ValidationError(
            "unexpected_field",
            "%s contains unsupported field(s): %s." % (name, ", ".join(sorted(extras))),
        )


def validate_job_request(payload, default_ttl_seconds, max_ttl_seconds):
    payload = _require_object(payload, "request")
    _reject_extra_fields(payload, {"job", "arg", "ttl_seconds"}, "request")

    job_type = payload.get("job")
    if job_type != "letter":
        if job_type == "pick_place":
            raise ValidationError(
                "job_not_enabled",
                "pick_place is hardware-pending and is not enabled on this server.",
            )
        raise ValidationError("unknown_job", "Only the enabled high-level job 'letter' is accepted.")

    argument = _require_object(payload.get("arg"), "arg")
    _reject_extra_fields(argument, {"letter"}, "arg")
    letter = argument.get("letter")
    if not isinstance(letter, str):
        raise ValidationError("invalid_letter", "letter must be a string.")
    letter = letter.strip().upper()
    if len(letter) != 1 or not ("A" <= letter <= "Z"):
        raise ValidationError("invalid_letter", "letter must be exactly one character A-Z.")

    ttl = payload.get("ttl_seconds", default_ttl_seconds)
    if isinstance(ttl, bool) or not isinstance(ttl, int):
        raise ValidationError("invalid_ttl", "ttl_seconds must be an integer.")
    if ttl < 1 or ttl > max_ttl_seconds:
        raise ValidationError(
            "invalid_ttl",
            "ttl_seconds must be between 1 and %d." % max_ttl_seconds,
        )
    return {"job": "letter", "arg": {"letter": letter}, "ttl_seconds": ttl}


def validate_poll(payload):
    payload = _require_object(payload, "request")
    _reject_extra_fields(
        payload,
        {"device_id", "poll_interval_ms", "atom_uptime_ms", "station"},
        "request",
    )
    device_id = payload.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip() or len(device_id) > 80:
        raise ValidationError("invalid_device_id", "device_id must be 1-80 characters.")

    poll_interval = payload.get("poll_interval_ms")
    if isinstance(poll_interval, bool) or not isinstance(poll_interval, int) or poll_interval < 1:
        raise ValidationError("invalid_poll_interval", "poll_interval_ms must be a positive integer.")

    uptime = payload.get("atom_uptime_ms")
    if uptime is not None and (
        isinstance(uptime, bool) or not isinstance(uptime, int) or uptime < 0
    ):
        raise ValidationError("invalid_uptime", "atom_uptime_ms must be a non-negative integer.")

    station = payload.get("station", {})
    station = _require_object(station, "station")
    _reject_extra_fields(station, {"reachable", "robot_state"}, "station")
    reachable = station.get("reachable")
    if reachable is not None and not isinstance(reachable, bool):
        raise ValidationError("invalid_station_status", "station.reachable must be boolean.")
    robot_state = station.get("robot_state", "unknown")
    allowed_states = {
        "unknown",
        "offline",
        "locally_disabled",
        "locally_enabled",
        "busy",
        "fault",
        "mock_only",
    }
    if robot_state not in allowed_states:
        raise ValidationError("invalid_robot_state", "station.robot_state is not recognized.")

    return {
        "device_id": device_id.strip(),
        "poll_interval_ms": poll_interval,
        "atom_uptime_ms": uptime,
        "station": {"reachable": reachable, "robot_state": robot_state},
    }


def validate_result(payload):
    payload = _require_object(payload, "request")
    _reject_extra_fields(payload, {"id", "status", "result", "reason"}, "request")
    job_id = payload.get("id")
    if not isinstance(job_id, str) or not job_id or len(job_id) > 80:
        raise ValidationError("invalid_job_id", "id must be a non-empty job ID.")

    status = payload.get("status")
    if status not in {"done", "refused"}:
        raise ValidationError("invalid_result_status", "status must be 'done' or 'refused'.")

    result = payload.get("result")
    reason = payload.get("reason")
    if result is not None and not isinstance(result, dict):
        raise ValidationError("invalid_result", "result must be an object or null.")
    if len(json.dumps(result, separators=(",", ":"))) > 4096:
        raise ValidationError("result_too_large", "result is too large.")

    if status == "done" and reason is not None:
        raise ValidationError("invalid_result", "A done result must not include reason.")
    if status == "refused":
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 160:
            raise ValidationError(
                "invalid_reason", "A refused result needs a 1-160 character reason."
            )
        reason = reason.strip()
    return {"id": job_id, "status": status, "result": result, "reason": reason}
