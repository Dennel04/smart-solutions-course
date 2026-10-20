"""Synthetic pump responses only; no robot, calibration or physical results."""

import copy
import socket

import pytest
import requests

from src.pick_place_preflight import PickPlacePreflightExecutor
from src.pump_contract import (
    HttpReply, PumpContractError, PumpWiring, assess_pump_exchange, normalize_config,
    normalize_status,
)


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    attempts = []
    def deny(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Real network access is forbidden")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(requests.sessions.Session, "request", deny)
    yield
    assert attempts == []


@pytest.fixture
def evidence():
    # 2/1 are source defaults, NOT a claim about the current lab wiring.
    return {
        "config": HttpReply(200, {"suck_do": 2, "blow_do": 1}),
        "command": HttpReply(200, {"ok": True, "errid": 0, "resp": "synthetic ack"}),
        "status": HttpReply(200, {
            "connected": True, "enabled": True, "feedback_ok": True,
            "servo_active": True, "error": False, "stalled": False,
            "link_error": None, "servo_error": None, "alarm_ids": [],
            "pump_mode": "suck", "digital_out": 2,
        }),
    }


def assert_blocked(report):
    assert report.vacuum_confirmed is False
    assert report.physical_execution_allowed is False
    assert report.automatic_retry_allowed is False


@pytest.mark.parametrize("mode,bits", [("suck", 2), ("blow", 1), ("off", 0)])
def test_ack_and_matching_outputs_are_not_vacuum_or_motion_permission(evidence, mode, bits):
    evidence["status"].body.update(pump_mode=mode, digital_out=bits)
    report = assess_pump_exchange(mode, **evidence)
    assert report.reason == "outputs_match_grip_unverified"
    assert report.command_acknowledged is True and report.outputs_match is True
    assert_blocked(report)


def test_mapping_comes_from_config_not_hardcoded_do(evidence):
    evidence["config"] = HttpReply(200, {"suck_do": 1, "blow_do": 2, "workspace": {}})
    evidence["status"].body.update(digital_out=1)
    assert assess_pump_exchange("suck", **evidence).outputs_match is True
    evidence["status"].body.update(digital_out=2)
    assert assess_pump_exchange("suck", **evidence).outputs_match is False


@pytest.mark.parametrize("body", [
    {}, [], None, {"suck_do": 2}, {"suck_do": 1, "blow_do": 1},
    {"suck_do": True, "blow_do": 1}, {"suck_do": "2", "blow_do": 1},
    {"suck_do": 2.0, "blow_do": 1}, {"suck_do": 0, "blow_do": 1},
    {"suck_do": 65, "blow_do": 1}, {"suck_do": -2, "blow_do": 1},
    {"suck_do": 2, "blow_do": None}, {"suck_do": 2, "blow_do": 1, "ok": False},
])
def test_invalid_config_rejected(evidence, body):
    evidence["config"] = HttpReply(200, body)
    report = assess_pump_exchange("suck", **evidence)
    assert report.command_acknowledged is False and report.outputs_match is False
    assert_blocked(report)
    with pytest.raises(PumpContractError):
        normalize_config(evidence["config"])


@pytest.mark.parametrize("body,reason", [
    ({"ok": False, "error": "Not connected"}, "command_rejected"),
    ({"ok": False, "errid": -1, "resp": "synthetic partial"}, "command_rejected"),
    ({"ok": True, "errid": -1, "resp": "synthetic partial"}, "command_errid"),
    ({"ok": True, "errid": 1, "resp": "synthetic partial"}, "command_errid"),
    ({"ok": True, "errid": "0", "resp": "synthetic"}, "invalid_errid"),
    ({"ok": True, "errid": False, "resp": "synthetic"}, "invalid_errid"),
    ({"ok": True, "errid": 0.0, "resp": "synthetic"}, "invalid_errid"),
    ({"ok": True, "errid": 0}, "invalid_resp"),
    ({"ok": True, "errid": 0, "resp": {}}, "invalid_resp"),
    ({"ok": True}, "invalid_errid"),
    ({"ok": 1, "errid": 0, "resp": "synthetic"}, "command_rejected"),
    ({"errid": 0, "resp": "synthetic"}, "command_rejected"),
    (None, "command_invalid_body"),
])
def test_http_200_is_not_an_ack(evidence, body, reason):
    evidence["command"] = HttpReply(200, body)
    report = assess_pump_exchange("suck", **evidence)
    assert report.reason == reason
    assert report.command_acknowledged is False and report.outputs_match is False
    assert_blocked(report)


@pytest.mark.parametrize("resp", [
    "blow=synthetic error; suck=synthetic ok",
    "blow=synthetic ok; suck=synthetic error",
])
def test_partial_do_failure_is_not_repaired_by_matching_status(evidence, resp):
    # Either DO can fail. The other may still change; no rollback is promised.
    evidence["command"] = HttpReply(200, {"ok": False, "errid": -1, "resp": resp})
    report = assess_pump_exchange("suck", **evidence)
    assert report.reason == "command_rejected"
    assert report.command_acknowledged is False and report.outputs_match is False
    assert_blocked(report)


def test_resp_is_opaque_not_interpreted_or_executed(evidence):
    evidence["command"].body["resp"] = "not executable: pump('blow'); enable(); move()"
    assert assess_pump_exchange("suck", **evidence).command_acknowledged is True


@pytest.mark.parametrize("field,value,reason", [
    ("connected", False, "connection_lost"), ("connected", None, "connection_lost"),
    ("enabled", False, "robot_disabled"), ("enabled", 1, "robot_disabled"),
    ("feedback_ok", False, "feedback_unhealthy"), ("feedback_ok", None, "feedback_unhealthy"),
    ("servo_active", False, "feedback_unhealthy"),
    ("error", True, "robot_unhealthy"), ("error", None, "robot_unhealthy"),
    ("stalled", True, "robot_unhealthy"), ("fault_kind", "synthetic", "robot_unhealthy"),
    ("fault", True, "robot_unhealthy"), ("fault_label", "synthetic", "robot_unhealthy"),
    ("link_error", "synthetic", "robot_unhealthy"),
    ("servo_error", "synthetic", "robot_unhealthy"), ("alarm_ids", [85], "robot_unhealthy"),
    ("ok", False, "status_rejected"),
    ("pump_mode", "blow", "inconsistent_pump_feedback"),
    ("pump_mode", "unknown", "inconsistent_pump_feedback"),
    ("pump_mode", None, "inconsistent_pump_feedback"),
    ("pump_mode", "conflict", "pump_conflict"),
    ("digital_out", 3, "pump_conflict"),
    ("digital_out", 0, "inconsistent_pump_feedback"),
    ("digital_out", True, "invalid_digital_out"),
    ("digital_out", -1, "invalid_digital_out"),
    ("digital_out", "2", "invalid_digital_out"),
    ("digital_out", 2.0, "invalid_digital_out"),
    ("digital_out", 1 << 64, "invalid_digital_out"),
])
def test_unsafe_or_inconsistent_snapshot_never_confirms_outputs(evidence, field, value, reason):
    evidence["status"].body[field] = value
    report = assess_pump_exchange("suck", **evidence)
    assert report.reason == reason
    assert report.command_acknowledged is True and report.outputs_match is False
    assert_blocked(report)


def test_consistent_but_wrong_mode_is_refused(evidence):
    evidence["status"].body.update(pump_mode="blow", digital_out=1)
    assert assess_pump_exchange("suck", **evidence).reason == "pump_mode_mismatch"


def test_unrelated_output_bits_do_not_change_pump_mode(evidence):
    evidence["status"].body["digital_out"] |= 1 << 10
    assert assess_pump_exchange("suck", **evidence).outputs_match is True


@pytest.mark.parametrize("stage", ["config", "command", "status"])
@pytest.mark.parametrize("http_status", [401, 409, 500, 502, True])
def test_http_errors_and_noninteger_code_refused(evidence, stage, http_status):
    evidence[stage] = HttpReply(http_status, evidence[stage].body)
    report = assess_pump_exchange("suck", **evidence)
    assert report.reason == stage + "_http_error" and report.outputs_match is False
    assert_blocked(report)


@pytest.mark.parametrize("stage", ["config", "command", "status"])
def test_missing_reply_refused(evidence, stage):
    evidence[stage] = None
    assert assess_pump_exchange("suck", **evidence).reason == stage + "_reply_missing"


@pytest.mark.parametrize("body", [None, [], "synthetic", {}, {"ok": True}])
def test_unknown_status_is_not_output_evidence(evidence, body):
    evidence["status"] = HttpReply(200, body)
    report = assess_pump_exchange("suck", **evidence)
    assert report.outputs_match is False
    assert_blocked(report)


@pytest.mark.parametrize("field", [
    "connected", "enabled", "feedback_ok", "servo_active", "error", "stalled",
    "digital_out", "pump_mode",
])
def test_missing_required_status_field_refused(evidence, field):
    del evidence["status"].body[field]
    report = assess_pump_exchange("suck", **evidence)
    assert report.outputs_match is False
    assert_blocked(report)


@pytest.mark.parametrize("wiring", [None, {}, PumpWiring(0, 1), PumpWiring(2, 2)])
def test_direct_status_helper_validates_wiring(evidence, wiring):
    with pytest.raises(PumpContractError):
        normalize_status(evidence["status"], wiring=wiring, requested_mode="suck")


@pytest.mark.parametrize("mode", ["conflict", "SUCK", "", None, {}, 1])
def test_invalid_requested_mode(evidence, mode):
    assert assess_pump_exchange(mode, **evidence).reason == "invalid_mode"


class FakeTransport:
    """A scripted in-memory transport, not a requests Session or MG400 client."""
    def __init__(self, evidence, failing_stage=None, error=None):
        self.evidence = evidence
        self.failing_stage = failing_stage
        self.error = error
        self.calls = []

    def request(self, method, path, *, payload=None):
        self.calls.append((method, path, payload))
        stage = {("GET", "/api/config"): "config", ("POST", "/api/pump"): "command",
                 ("GET", "/api/status"): "status"}[(method, path)]
        if stage == self.failing_stage:
            raise self.error
        if stage == "command":
            assert payload == {"mode": "suck"}
        return self.evidence[stage]


def synthetic_exchange(transport):
    """Test harness only. There is no production function that sends commands."""
    replies = {}
    try:
        replies["config"] = transport.request("GET", "/api/config")
        replies["command"] = transport.request("POST", "/api/pump", payload={"mode": "suck"})
        replies["status"] = transport.request("GET", "/api/status")
    except requests.Timeout:
        return assess_pump_exchange("suck", **replies, transport_failure="timeout")
    except requests.ConnectionError:
        return assess_pump_exchange("suck", **replies, transport_failure="connection_lost")
    return assess_pump_exchange("suck", **replies)


@pytest.mark.parametrize("stage", ["config", "command", "status"])
@pytest.mark.parametrize("error,reason", [
    (requests.Timeout("synthetic"), "timeout"),
    (requests.ConnectionError("synthetic"), "connection_lost"),
])
def test_timeout_and_lost_reply_do_not_retry_or_assume_off(evidence, stage, error, reason):
    transport = FakeTransport(evidence, stage, error)
    report = synthetic_exchange(transport)
    assert report.reason == reason and report.outputs_match is False
    assert report.command_acknowledged is (stage == "status")
    assert_blocked(report)
    assert len(transport.calls) == ("config", "command", "status").index(stage) + 1
    assert sum(method == "POST" for method, _, _ in transport.calls) <= 1


def test_fake_transport_success_still_does_not_authorize_preflight(evidence):
    original = copy.deepcopy(evidence)
    report = synthetic_exchange(FakeTransport(evidence))
    assert report.command_acknowledged and report.outputs_match
    assert_blocked(report)
    assert evidence == original
    preflight = PickPlacePreflightExecutor()
    outcome = preflight.execute_pick_place(
        "source_to_finished", "synthetic-pump-contract", session="test", seq=1,
        atom_sent_ms=None,
    )
    assert outcome.status == "refused"
    assert preflight.last_report.physical_execution_allowed is False


@pytest.mark.parametrize("failure", ["invalid_json", "transport_error", "untrusted text", {}, True])
def test_transport_failures_have_fixed_diagnostics(evidence, failure):
    report = assess_pump_exchange("suck", **evidence, transport_failure=failure)
    assert report.reason in {"invalid_json", "transport_error"}
    assert_blocked(report)
