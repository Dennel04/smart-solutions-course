"""Pure mg400-base response checks. No transport, pump commands or executor.

Callers supply decoded response snapshots; this module does not fetch them.
Even matching outputs cannot establish freshness, vacuum or a held part.
"""

from __future__ import annotations

from dataclasses import dataclass, field


MODES = ("suck", "blow", "off")
TRANSPORT_FAILURES = ("timeout", "connection_lost", "invalid_json", "transport_error")


class PumpContractError(ValueError):
    """A fixed local diagnostic code, without raw server text or credentials."""


@dataclass(frozen=True)
class HttpReply:
    status_code: int
    body: object


@dataclass(frozen=True)
class PumpWiring:
    suck_do: int
    blow_do: int


@dataclass(frozen=True)
class PumpAssessment:
    reason: str
    command_acknowledged: bool = False
    outputs_match: bool = False
    vacuum_confirmed: bool = field(default=False, init=False)
    physical_execution_allowed: bool = field(default=False, init=False)
    automatic_retry_allowed: bool = field(default=False, init=False)


def _body(reply: HttpReply | None, stage: str) -> dict:
    if not isinstance(reply, HttpReply):
        raise PumpContractError(stage + "_reply_missing")
    if type(reply.status_code) is not int or reply.status_code != 200:
        raise PumpContractError(stage + "_http_error")
    if not isinstance(reply.body, dict):
        raise PumpContractError(stage + "_invalid_body")
    return reply.body


def normalize_config(reply: HttpReply | None) -> PumpWiring:
    body = _body(reply, "config")
    if "ok" in body and body["ok"] is not True:
        raise PumpContractError("config_rejected")
    indices = (body.get("suck_do"), body.get("blow_do"))
    # Feedback encodes digital_out as uint64. This is a representation bound,
    # NOT a claim that the robot has 64 usable physical pump outputs.
    if any(type(index) is not int or not 1 <= index <= 64 for index in indices):
        raise PumpContractError("invalid_do_mapping")
    if indices[0] == indices[1]:
        raise PumpContractError("overlapping_do_mapping")
    return PumpWiring(*indices)


def normalize_command_reply(reply: HttpReply | None) -> None:
    """Require an explicit command ack; resp remains opaque diagnostic text."""
    body = _body(reply, "command")
    if body.get("ok") is not True:
        raise PumpContractError("command_rejected")
    if type(body.get("errid")) is not int:
        raise PumpContractError("invalid_errid")
    if body["errid"] != 0:
        raise PumpContractError("command_errid")
    if not isinstance(body.get("resp"), str):
        raise PumpContractError("invalid_resp")


def normalize_status(
    reply: HttpReply | None, *, wiring: PumpWiring, requested_mode: str,
) -> str:
    """Check a healthy supplied snapshot, not post-command freshness or grip."""
    if type(requested_mode) is not str or requested_mode not in MODES:
        raise PumpContractError("invalid_mode")
    # Recheck even manually constructed PumpWiring instances.
    if not isinstance(wiring, PumpWiring):
        raise PumpContractError("invalid_do_mapping")
    wiring = normalize_config(HttpReply(200, {
        "suck_do": wiring.suck_do, "blow_do": wiring.blow_do,
    }))
    body = _body(reply, "status")
    if "ok" in body and body["ok"] is not True:
        raise PumpContractError("status_rejected")
    if body.get("connected") is not True:
        raise PumpContractError("connection_lost")
    if body.get("enabled") is not True:
        raise PumpContractError("robot_disabled")
    if body.get("feedback_ok") is not True or body.get("servo_active") is not True:
        raise PumpContractError("feedback_unhealthy")
    if body.get("error") is not False or body.get("stalled") is not False:
        raise PumpContractError("robot_unhealthy")
    if any(body.get(name) for name in (
        "fault", "fault_kind", "fault_label", "link_error", "servo_error", "alarm_ids",
    )):
        raise PumpContractError("robot_unhealthy")
    bits = body.get("digital_out")
    if type(bits) is not int or not 0 <= bits < 1 << 64:
        raise PumpContractError("invalid_digital_out")
    suck = bool(bits & (1 << (wiring.suck_do - 1)))
    blow = bool(bits & (1 << (wiring.blow_do - 1)))
    reported = body.get("pump_mode")
    if reported == "conflict" or (suck and blow):
        raise PumpContractError("pump_conflict")
    derived = "suck" if suck else "blow" if blow else "off"
    if type(reported) is not str or reported not in MODES or reported != derived:
        raise PumpContractError("inconsistent_pump_feedback")
    if reported != requested_mode:
        raise PumpContractError("pump_mode_mismatch")
    return reported


def assess_pump_exchange(
    requested_mode: str, *, config: HttpReply | None = None,
    command: HttpReply | None = None, status: HttpReply | None = None,
    transport_failure: str | None = None,
) -> PumpAssessment:
    """Assess supplied evidence without retries, callbacks or any I/O.

    A timeout/lost reply may follow a partially applied command. Do not infer
    off, retry automatically, or resume a job from this result. No result here
    grants physical execution; only a future reviewed owner may send commands.
    """
    acknowledged = False
    try:
        if type(requested_mode) is not str or requested_mode not in MODES:
            raise PumpContractError("invalid_mode")
        if transport_failure is not None:
            # Preserve a known ack when the subsequent status request failed.
            # It still says nothing about partial effects, output state or grip.
            if command is not None:
                try:
                    normalize_command_reply(command)
                    acknowledged = True
                except PumpContractError:
                    pass
            reason = (transport_failure if type(transport_failure) is str
                      and transport_failure in TRANSPORT_FAILURES else "transport_error")
            raise PumpContractError(reason)
        wiring = normalize_config(config)
        normalize_command_reply(command)
        acknowledged = True
        normalize_status(status, wiring=wiring, requested_mode=requested_mode)
    except PumpContractError as error:
        return PumpAssessment(str(error), command_acknowledged=acknowledged)
    return PumpAssessment("outputs_match_grip_unverified", True, True)
