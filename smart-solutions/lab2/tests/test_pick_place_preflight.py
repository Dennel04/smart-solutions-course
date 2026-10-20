"""Synthetic positions and injected clients only. No physical results."""

import copy
import importlib.util
import json
from pathlib import Path
import socket

import pytest
import requests

from src.models import parse_atom_message
from src.pick_place_preflight import (
    DEFAULT_POSITIONS, PickPlacePreflightExecutor, PreparationError, build_local_plan,
)
from src.station_adapter import StationAdapter
from src.station_store import StationJobStore


# Exercise the REAL Lab 1 status/check contract, but replace its entire transport.
# Importing this module constructs no client and opens no network connection.
spec = importlib.util.spec_from_file_location(
    "lab1_pick_preflight_contract", Path(__file__).resolve().parents[2] / "lab1/src/mg400_client.py"
)
lab1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab1)


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    attempted = []
    def deny(*args, **kwargs):
        attempted.append(True)
        raise AssertionError("A real network request was attempted")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(requests.sessions.Session, "request", deny)
    yield
    assert not attempted


@pytest.fixture
def positions():
    # Arbitrary synthetic fixture coordinates, NOT lab calibration or measurements.
    return {"positions": {
        "above_source": {"x": 250, "y": 0, "z": 40, "r": 0},
        "source": {"x": 250, "y": 0, "z": 20, "r": 0},
        "above_finished": {"x": 280, "y": 0, "z": 40, "r": 0},
        "finished": {"x": 280, "y": 0, "z": 20, "r": 0},
    }}


def write_positions(tmp_path, document):
    path = tmp_path / "synthetic-positions.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


class Response:
    status_code = 200
    def __init__(self, body):
        self.body = body
    def raise_for_status(self):
        pass
    def json(self):
        return self.body


class FakeSession:
    def __init__(self, **overrides):
        self.status = {
            "connected": True, "enabled": True, "pose": [250, 0, 40, 0],
            "feedback_ok": True, "servo_active": True, "error": False,
            "stalled": False,
        }
        self.status.update(overrides)
        self.calls = []
        self.reachable = True
        self.failure = None
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.failure:
            raise self.failure
        if method == "GET" and url.endswith("/api/status"):
            return Response(self.status)
        if method == "POST" and url.endswith("/api/check"):
            return Response({"reachable": self.reachable})
        raise AssertionError("No motion/pump/enable/stop request is permitted")


@pytest.fixture
def prepared(tmp_path, positions):
    transport = FakeSession()
    executor = PickPlacePreflightExecutor(
        client=lab1.MG400Client(session=transport),
        positions_path=write_positions(tmp_path, positions),
        speed_percent=20, calibration_confirmed=True,
        preflight_enabled=True,
    )
    return executor, transport


def payload(job_id="synthetic-pick-1", seq=1):
    return {"job": "pick_place", "routine": "source_to_finished", "job_id": job_id,
            "session": "synthetic-preflight", "seq": seq, "atom_sent_ms": 1234}


def test_candidate_sequence_uses_only_local_taught_positions(tmp_path, positions):
    plan = build_local_plan(write_positions(tmp_path, positions), speed_percent=20)
    assert [(step.operation, step.position) for step in plan.steps] == [
        ("move_to_taught", "above_source"), ("move_to_taught", "source"),
        ("acquire_part", None), ("move_to_taught", "above_source"),
        ("move_to_taught", "above_finished"), ("move_to_taught", "finished"),
        ("release_part", None), ("move_to_taught", "above_finished"),
    ]
    assert dict(plan.positions)["source"] == (250, 0, 20, 0)


def test_only_whitelisted_routine_is_accepted(prepared):
    executor, transport = prepared
    outcome = executor.execute_pick_place(
        "other", "synthetic-1", session="test", seq=1, atom_sent_ms=None
    )
    assert outcome.reason == "invalid_routine" and transport.calls == []


@pytest.mark.parametrize("name", ["above_source", "source", "above_finished", "finished"])
def test_each_taught_position_is_required(tmp_path, positions, name):
    del positions["positions"][name]
    with pytest.raises(PreparationError, match="missing_or_invalid"):
        build_local_plan(write_positions(tmp_path, positions), speed_percent=20)


@pytest.mark.parametrize("value", [None, True, "250", float("nan"), float("inf")])
def test_invalid_or_nonfinite_coordinates_refused(tmp_path, positions, value):
    positions["positions"]["source"]["x"] = value
    with pytest.raises(PreparationError):
        build_local_plan(write_positions(tmp_path, positions), speed_percent=20)


@pytest.mark.parametrize("speed", [None, True, 0, -1, 21, float("nan"), float("inf"), 10**400])
def test_local_speed_must_be_explicit_and_conservative(tmp_path, positions, speed):
    with pytest.raises(PreparationError, match="local_speed"):
        build_local_plan(write_positions(tmp_path, positions), speed_percent=speed)


def test_identical_source_finished_is_rejected(tmp_path, positions):
    positions["positions"]["finished"] = copy.deepcopy(positions["positions"]["source"])
    with pytest.raises(PreparationError, match="source_finished_overlap"):
        build_local_plan(write_positions(tmp_path, positions), speed_percent=20)


def test_current_lab1_in_place_fixture_blocks_transfer(prepared):
    with pytest.raises(PreparationError, match="source_finished_overlap"):
        build_local_plan(DEFAULT_POSITIONS, speed_percent=20)
    executor, transport = prepared
    executor.positions_path = DEFAULT_POSITIONS
    report = executor.inspect()
    assert report.blockers == ("source_finished_overlap",)
    assert report.physical_execution_allowed is False
    assert transport.calls == []


@pytest.mark.parametrize("change", ["low_lift", "diagonal_approach", "different_plane", "out_of_reach"])
def test_unsafe_candidate_geometry_refused(tmp_path, positions, change):
    target = positions["positions"]["above_source"]
    if change == "low_lift":
        target["z"] = 39
    elif change == "diagonal_approach":
        target["x"] = 251
    elif change == "different_plane":
        positions["positions"]["above_finished"]["z"] = 41
    else:
        target["x"] = 500
    with pytest.raises(PreparationError):
        build_local_plan(write_positions(tmp_path, positions), speed_percent=20)


@pytest.mark.parametrize("text", ["{broken", "[]", '{"positions":{},"positions":{}}'])
def test_malformed_local_config_is_refused(tmp_path, text):
    path = tmp_path / "invalid.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(PreparationError):
        build_local_plan(path, speed_percent=20)


def test_missing_file_is_refused(tmp_path):
    with pytest.raises(PreparationError):
        build_local_plan(tmp_path / "missing.json", speed_percent=20)


def test_default_and_unconfirmed_calibration_never_contact_client(prepared):
    executor, transport = prepared
    executor.preflight_enabled = False
    assert executor.inspect().reason == "robot_not_enabled"
    executor.preflight_enabled = True
    executor.calibration_confirmed = False
    assert executor.inspect().blockers == ("calibration_unconfirmed",)
    assert transport.calls == []
    assert PickPlacePreflightExecutor().ready is False


@pytest.mark.parametrize("field,value", [
    ("enabled", False), ("connected", False), ("fault", True),
    ("feedback_ok", False), ("servo_active", False), ("stalled", True),
])
def test_lab1_robot_safety_gate_refuses_unsafe_status(prepared, field, value):
    executor, transport = prepared
    transport.status[field] = value
    report = executor.inspect()
    assert report.physical_execution_allowed is False
    assert len(transport.calls) == 1
    assert report.reason in {"robot_not_enabled", "execution_failed"}


@pytest.mark.parametrize("reply", [False, None, "true"])
def test_reachability_must_be_confirmed_not_assumed(prepared, reply):
    executor, transport = prepared
    transport.reachable = reply
    assert not executor.inspect().physical_execution_allowed
    assert len(transport.calls) == 2


@pytest.mark.parametrize("failure", [
    requests.RequestException("synthetic"), requests.Timeout("synthetic"), TimeoutError()
])
def test_mg400_error_or_timeout_is_terminal_refusal(prepared, tmp_path, failure):
    executor, transport = prepared
    transport.failure = failure
    adapter = StationAdapter(StationJobStore(tmp_path / "jobs.sqlite3"),
                             pick_place_executor=executor, local_execution_enabled=True)
    line = json.dumps(payload())
    first = adapter.handle_line(line)
    assert json.loads(first)["post_office_result"]["reason"] == "execution_failed"
    assert adapter.handle_line(line) == first and len(transport.calls) == 1


def test_unknown_status_result_refuses_before_any_pose_check(prepared):
    executor, transport = prepared
    transport.status = None
    assert "mg400_preflight_failed" in executor.inspect().blockers
    assert len(transport.calls) == 1


@pytest.mark.parametrize("name", ["pump_check", "ownership_check"])
def test_removed_callback_parameters_rejected_without_side_effects(name):
    effects = []
    def side_effect():
        effects.append("called")
        return True
    with pytest.raises(TypeError, match=name):
        PickPlacePreflightExecutor(**{name: side_effect})
    assert effects == []


def test_successful_client_checks_leave_pump_and_owner_blocked(prepared):
    executor, transport = prepared
    report = executor.inspect()
    assert report.blockers == (
        "pump_interface_missing", "exclusive_owner_interface_missing",
        "live_pump_and_exclusive_control_binding_missing",
    )
    assert report.reason == "executor_busy"
    assert report.physical_execution_allowed is False
    assert len(transport.calls) == 5
    assert {url.rsplit("/", 1)[-1] for _, url, _ in transport.calls} == {"status", "check"}


def test_no_motion_pump_enable_or_side_effect_callback_calls(prepared, monkeypatch):
    executor, transport = prepared
    effects = []
    def side_effect(*args, **kwargs):
        effects.append("unexpected side effect")
        return True
    # Even legacy attributes attached by old calling code must remain inert.
    executor.pump_check = side_effect
    executor.ownership_check = side_effect
    for name in ("move", "move_and_wait", "set_speed", "stop", "pump", "set_pump",
                 "acquire_part", "release_part", "enable", "enable_robot", "set_do"):
        monkeypatch.setattr(executor.client, name, side_effect, raising=False)
    outcome = executor.execute_pick_place(
        "source_to_finished", "synthetic-no-effects", session="test", seq=1, atom_sent_ms=None
    )
    assert outcome.status == "refused"
    assert executor.last_report.physical_execution_allowed is False
    assert "pump_interface_missing" in executor.last_report.blockers
    assert "exclusive_owner_interface_missing" in executor.last_report.blockers
    assert effects == []
    assert [(method, url.rsplit("/", 1)[-1]) for method, url, _ in transport.calls] == [
        ("GET", "status"), ("POST", "check"), ("POST", "check"),
        ("POST", "check"), ("POST", "check"),
    ]


def test_two_separate_station_programs_cannot_authorize_motion(prepared, tmp_path):
    executor, transport = prepared
    for index in range(2):
        # Separate databases cannot provide a shared robot lock. Neither station
        # may turn successful status/reachability checks into permission to move.
        adapter = StationAdapter(StationJobStore(tmp_path / f"station-{index}.sqlite3"),
                                 pick_place_executor=executor, local_execution_enabled=True)
        result = json.loads(adapter.handle_line(json.dumps(payload(seq=index))))["post_office_result"]
        assert result["status"] == "refused"
    assert len(transport.calls) == 10
    assert all(url.endswith(("/api/status", "/api/check")) for _, url, _ in transport.calls)


def test_duplicate_and_restart_do_not_repeat_preflight(prepared, tmp_path):
    executor, transport = prepared
    database = tmp_path / "jobs.sqlite3"
    first = StationAdapter(StationJobStore(database), pick_place_executor=executor,
                           local_execution_enabled=True)
    line = json.dumps(payload())
    expected = first.handle_line(line)
    assert first.handle_line(line) == expected
    assert len(transport.calls) == 5
    restarted = StationAdapter(StationJobStore(database), pick_place_executor=executor,
                               local_execution_enabled=True)
    assert restarted.handle_line(line) == expected
    assert len(transport.calls) == 5


def test_uncertain_interruption_never_resumes(prepared, tmp_path):
    executor, transport = prepared
    database = tmp_path / "jobs.sqlite3"
    StationJobStore(database).claim(parse_atom_message(payload()))
    adapter = StationAdapter(StationJobStore(database), pick_place_executor=executor,
                             local_execution_enabled=True)
    result = json.loads(adapter.handle_line(json.dumps(payload())))["post_office_result"]
    assert result["reason"] == "ambiguous_after_restart" and transport.calls == []


def test_post_office_to_preflight_returns_honest_refusal(
    prepared, tmp_path, client, create_pick_place, atom_headers, user_headers, valid_poll
):
    executor, _ = prepared
    job_id = create_pick_place().get_json()["id"]
    polled = client.post("/api/atom/poll", headers=atom_headers, json=valid_poll).get_json()["job"]
    assert polled["id"] == job_id
    adapter = StationAdapter(StationJobStore(tmp_path / "station.sqlite3"),
                             pick_place_executor=executor, local_execution_enabled=True)
    result = json.loads(adapter.handle_line(json.dumps(payload(job_id))))["post_office_result"]
    assert result["id"] == job_id and result["status"] == "refused"
    assert client.post("/api/atom/result", headers=atom_headers, json=result).status_code == 200
    stored = client.get("/api/jobs/" + job_id, headers=user_headers).get_json()
    assert stored["status"] == "refused"  # Never a fake hardware success.
