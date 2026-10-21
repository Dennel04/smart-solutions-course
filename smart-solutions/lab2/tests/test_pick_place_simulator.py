"""Entirely synthetic positions, feedback and logical times; no hardware data."""

import copy
from dataclasses import replace
import json
import socket
import sqlite3

import pytest
import requests
import serial

from src.ownership_model import CompletionEvidence, Owner, OwnershipModel, State, StepEvidence
from src.pick_place_preflight import PlanStep, PreparationError
from src.pick_place_simulator import (
    PartState, PickPlaceSimulation, SimulatedFailure, SyntheticPartEvidence,
    SyntheticPumpExchange, SyntheticStepObservation,
)
from src.pump_contract import HttpReply


@pytest.fixture(autouse=True)
def forbid_real_transports(monkeypatch):
    attempts = []
    def deny(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Real HTTP/TCP/serial is forbidden")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(requests.sessions.Session, "request", deny)
    monkeypatch.setattr(serial.Serial, "open", deny)
    yield
    assert attempts == []


OWNER = Owner("synthetic-client", "synthetic-session", "synthetic-cycle")
OTHER = Owner("synthetic-other", "other-session", "other-cycle")
FEEDBACK = StepEvidence(True, True, True, True, True)
HELD = SyntheticPartEvidence(True, True, True, True, False)
RELEASED = SyntheticPartEvidence(True, True, False, False, True)
COMPLETE = CompletionEvidence(True, True, True, True, True)


class FakeClock:
    # Logical test units only, not measured vacuum/robot timing.
    def __init__(self):
        self.now = 100.0
    def __call__(self):
        return self.now


@pytest.fixture
def positions():
    # Arbitrary synthetic coordinates, NOT taught robot positions/calibration.
    return {"synthetic": True, "positions": {
        "above_source": {"x": 250, "y": 0, "z": 40, "r": 0},
        "source": {"x": 250, "y": 0, "z": 20, "r": 0},
        "above_finished": {"x": 280, "y": 0, "z": 40, "r": 0},
        "finished": {"x": 280, "y": 0, "z": 20, "r": 0},
    }}


@pytest.fixture
def path(tmp_path, positions):
    result = tmp_path / "synthetic-positions.json"
    result.write_text(json.dumps(positions), encoding="utf-8")
    return result


def model_ready(path, clock):
    model = OwnershipModel(path, clock=clock)
    # Explicit synthetic operator confirmation; the simulator does not do it.
    model.operator_clear(
        expected_token=model.snapshot().token, operator_id="synthetic-operator",
        local_confirmation=True, stopped_confirmed=True, no_pending_commands=True,
        outputs_safe=True,
    )
    return model


@pytest.fixture
def scenario(path, tmp_path):
    clock = FakeClock()
    model = model_ready(tmp_path / "synthetic-ownership.sqlite3", clock)
    simulation = PickPlaceSimulation(path, speed_percent=20, ownership=model, owner=OWNER)
    return simulation, model, clock


def pump_exchange(mode):
    # Mapping is synthetic source-default data, not current physical wiring.
    return SyntheticPumpExchange(
        HttpReply(200, {"suck_do": 2, "blow_do": 1}),
        HttpReply(200, {"ok": True, "errid": 0, "resp": "synthetic ack"}),
        HttpReply(200, {
            "connected": True, "enabled": True, "feedback_ok": True,
            "servo_active": True, "error": False, "stalled": False,
            "pump_mode": mode, "digital_out": 2 if mode == "suck" else 0,
        }),
    )


@pytest.fixture
def observations(scenario):
    simulation, _, _ = scenario
    result = []
    for index, step in enumerate(simulation.plan.steps):
        pump = None
        part = None
        if step.operation == "acquire_part":
            pump = pump_exchange("suck")
        elif step.operation == "release_part":
            pump = pump_exchange("off")
        if 2 <= index <= 5:
            part = HELD
        elif index >= 6:
            part = RELEASED
        result.append(SyntheticStepObservation(step, FEEDBACK, pump, part))
    return result


def start(simulation):
    result = simulation.start(lease_seconds=10, sequence_seconds=60)
    assert result.status == "simulated_in_progress"
    return simulation.grant


def prefix(simulation, observations, count):
    grant = start(simulation)
    for observation in observations[:count]:
        assert simulation.advance(observation, grant=grant).status == "simulated_in_progress"
    return grant


def assert_no_hardware(result):
    assert result.hardware_used is False
    assert result.physical_execution_allowed is False
    assert result.automatic_retry_allowed is False


def test_success_confirms_all_eight_steps_and_separate_grip_release(scenario, observations):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 8)
    result = simulation.finish(COMPLETE, grant=grant)
    assert result.status == "simulated_complete" and result.confirmed_steps == 8
    assert result.owner == OWNER and result.fencing_token == grant.token
    assert result.part_state == PartState.AT_FINISHED
    assert result.ownership_state == "FREE" and model.snapshot().owner is None
    confirmed = [entry for entry in result.trace if entry.outcome == "confirmed"]
    assert len(result.trace) == 16
    assert [entry.step for entry in confirmed] == list(simulation.plan.steps)
    assert [entry.step_number for entry in confirmed] == list(range(1, 9))
    assert all(entry.token == grant.token for entry in result.trace)
    assert [entry.part_state for entry in confirmed] == [
        PartState.AT_SOURCE, PartState.AT_SOURCE, PartState.HELD, PartState.HELD,
        PartState.HELD, PartState.HELD, PartState.AT_FINISHED, PartState.AT_FINISHED,
    ]
    assert_no_hardware(result)
    assert not hasattr(simulation, "ready")
    assert not hasattr(simulation, "execute_pick_place")
    assert simulation.finish(COMPLETE, grant=grant) == result


def test_same_synthetic_script_is_deterministic(scenario, observations, path, tmp_path):
    first, _, _ = scenario
    grant = prefix(first, observations, 8)
    expected = first.finish(COMPLETE, grant=grant)
    second_model = model_ready(tmp_path / "other-synthetic.sqlite3", FakeClock())
    second = PickPlaceSimulation(path, speed_percent=20, ownership=second_model, owner=OWNER)
    other_grant = prefix(second, observations, 8)
    assert second.finish(COMPLETE, grant=other_grant) == expected


@pytest.mark.parametrize("count,bad_index", [(0, 1), (1, 0), (2, 3), (6, 7)])
def test_skipped_repeated_or_reordered_step_stops_cycle(scenario, observations, count, bad_index):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, count)
    result = simulation.advance(observations[bad_index], grant=grant)
    assert result.reason == "step_order_mismatch"
    assert result.confirmed_steps == count
    assert model.snapshot().state == State.UNCERTAIN
    assert_no_hardware(result)


def test_unknown_plan_operation_is_not_accepted(scenario, observations):
    simulation, model, _ = scenario
    grant = start(simulation)
    result = simulation.advance(
        replace(observations[0], step=PlanStep("arbitrary_motion", "source")), grant=grant,
    )
    assert result.reason == "step_order_mismatch" and result.trace == ()
    assert model.snapshot().state == State.UNCERTAIN


@pytest.mark.parametrize("missing", ["above_source", "source", "above_finished", "finished"])
def test_missing_position_uses_existing_plan_validator(path, positions, scenario, missing):
    _, model, _ = scenario
    del positions["positions"][missing]
    path.write_text(json.dumps(positions), encoding="utf-8")
    with pytest.raises(PreparationError, match="missing_or_invalid_taught_position"):
        PickPlaceSimulation(path, speed_percent=20, ownership=model, owner=OWNER)
    assert model.snapshot().state == State.FREE


def test_identical_source_finished_rejected_before_claim(path, positions, scenario):
    _, model, _ = scenario
    positions["positions"]["finished"] = copy.deepcopy(positions["positions"]["source"])
    path.write_text(json.dumps(positions), encoding="utf-8")
    with pytest.raises(PreparationError, match="source_finished_overlap"):
        PickPlaceSimulation(path, speed_percent=20, ownership=model, owner=OWNER)
    assert model.snapshot().state == State.FREE


def test_only_allowed_routine(path, scenario):
    _, model, _ = scenario
    with pytest.raises(PreparationError, match="invalid_routine"):
        PickPlaceSimulation(path, speed_percent=20, ownership=model, owner=OWNER, routine="other")


def test_unmarked_positions_are_not_accepted_as_synthetic(path, positions, scenario):
    _, model, _ = scenario
    del positions["synthetic"]
    path.write_text(json.dumps(positions), encoding="utf-8")
    with pytest.raises(PreparationError, match="synthetic_marker_required"):
        PickPlaceSimulation(path, speed_percent=20, ownership=model, owner=OWNER)


@pytest.mark.parametrize("text", ["{broken", "[]", '{"synthetic":true,"positions":{}}'])
def test_invalid_synthetic_input_is_rejected_before_claim(path, scenario, text):
    _, model, _ = scenario
    path.write_text(text, encoding="utf-8")
    with pytest.raises(PreparationError):
        PickPlaceSimulation(path, speed_percent=20, ownership=model, owner=OWNER)
    assert model.snapshot().state == State.FREE


@pytest.mark.parametrize("part,reason", [
    (None, "part_confirmation_missing"),
    (replace(HELD, part_held=False), "grip_unconfirmed"),
    (replace(HELD, vacuum_detected=False), "vacuum_unconfirmed"),
    (replace(HELD, sample_fresh=False), "pressure_sample_stale"),
    (replace(HELD, calibration_confirmed=False), "calibration_unconfirmed"),
    (replace(HELD, release_confirmed=True), "grip_unconfirmed"),
    (replace(HELD, part_held=1), "grip_unconfirmed"),
])
def test_digital_outputs_never_substitute_for_grip(scenario, observations, part, reason):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 2)
    result = simulation.advance(replace(observations[2], part=part), grant=grant)
    assert result.reason == reason and result.confirmed_steps == 2
    assert model.snapshot().state == State.UNCERTAIN
    assert result.part_state == PartState.UNKNOWN
    assert_no_hardware(result)


@pytest.mark.parametrize("index", [3, 4, 5])
def test_transfer_requires_continuing_fresh_grip(scenario, observations, index):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, index)
    result = simulation.advance(
        replace(observations[index], part=replace(HELD, sample_fresh=False)), grant=grant,
    )
    assert result.reason == "pressure_sample_stale" and result.confirmed_steps == index
    assert model.snapshot().state == State.UNCERTAIN


@pytest.mark.parametrize("stage,body,reason", [
    ("command", {"ok": False, "error": "synthetic"}, "command_rejected"),
    ("command", {"ok": False, "errid": -1, "resp": "synthetic partial DO"}, "command_rejected"),
    ("command", {"ok": True, "errid": -1, "resp": "synthetic partial DO"}, "command_errid"),
    ("config", {"suck_do": 1, "blow_do": 1}, "overlapping_do_mapping"),
])
@pytest.mark.parametrize("index", [2, 6])
def test_pump_failure_and_partial_do_stop_without_compensation(scenario, observations, stage, body, reason, index):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, index)
    exchange = replace(observations[index].pump, **{stage: HttpReply(200, body)})
    result = simulation.advance(replace(observations[index], pump=exchange), grant=grant)
    assert result.reason == "pump_" + reason
    assert result.confirmed_steps == index and len(result.trace) == 2 * index + 1
    assert model.snapshot().state == State.UNCERTAIN
    assert simulation.advance(observations[index + 1], grant=grant) == result
    assert_no_hardware(result)


@pytest.mark.parametrize("changes,reason", [
    ({"pump_mode": "blow", "digital_out": 1}, "pump_mode_mismatch"),
    ({"pump_mode": "conflict", "digital_out": 3}, "pump_conflict"),
    ({"feedback_ok": False}, "feedback_unhealthy"),
    ({"connected": False}, "connection_lost"),
])
def test_pump_feedback_must_be_healthy_and_match(scenario, observations, changes, reason):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 2)
    exchange = observations[2].pump
    body = dict(exchange.status.body, **changes)
    exchange = replace(exchange, status=HttpReply(200, body))
    result = simulation.advance(replace(observations[2], pump=exchange), grant=grant)
    assert result.reason == "pump_" + reason
    assert model.snapshot().state == State.UNCERTAIN


@pytest.mark.parametrize("failure", list(SimulatedFailure))
def test_motion_error_timeout_and_unknown_result_stop(scenario, observations, failure):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 4)
    result = simulation.advance(replace(observations[4], failure=failure), grant=grant)
    assert result.status == "simulated_stopped" and result.reason == failure.value
    assert result.confirmed_steps == 4 and model.snapshot().state == State.UNCERTAIN
    old_token = model.snapshot().token
    assert simulation.advance(observations[4], grant=grant) == result
    assert simulation.finish(COMPLETE, grant=grant) == result
    assert simulation.start(lease_seconds=10, sequence_seconds=60) == result
    assert model.snapshot().token == old_token
    assert_no_hardware(result)


def test_motion_ack_without_fresh_feedback_is_not_confirmation(scenario, observations):
    simulation, model, _ = scenario
    grant = start(simulation)
    result = simulation.advance(
        replace(observations[0], feedback=replace(FEEDBACK, feedback_fresh=False)), grant=grant,
    )
    assert result.reason == "ownership_step_result_unconfirmed"
    assert model.snapshot().state == State.UNCERTAIN


def test_unavailable_ownership_readback_cannot_report_in_progress(scenario, monkeypatch):
    simulation, model, _ = scenario
    # Synthetic store outage after reserve/activate. No external callback is
    # accepted by the simulator; monkeypatch affects this test instance only.
    def unavailable():
        raise sqlite3.OperationalError("synthetic store outage")
    monkeypatch.setattr(model, "snapshot", unavailable)
    result = simulation.start(lease_seconds=10, sequence_seconds=60)
    assert result.status == "simulated_stopped" and result.ownership_state == "unavailable"
    assert_no_hardware(result)


def test_lost_final_readback_does_not_report_unconditional_success(scenario, observations, monkeypatch):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 8)
    original_snapshot = model.snapshot
    def unavailable():
        raise sqlite3.OperationalError("synthetic readback failure")
    monkeypatch.setattr(model, "snapshot", unavailable)
    result = simulation.finish(COMPLETE, grant=grant)
    assert result.status == "simulated_stopped" and result.ownership_state == "unavailable"
    # The confirmed completion transaction already committed. Do not pretend
    # rollback/retry is safe; the old job ID remains permanently consumed.
    assert original_snapshot().state == State.FREE
    assert simulation.finish(COMPLETE, grant=grant) == result
    assert_no_hardware(result)


def test_ownership_deadline_expires_during_cycle(scenario, observations):
    simulation, model, clock = scenario
    grant = prefix(simulation, observations, 4)
    clock.now += 10
    result = simulation.advance(observations[4], grant=grant)
    assert result.confirmed_steps == 4 and result.status == "simulated_stopped"
    assert result.ownership_reason == "heartbeat_lost"
    assert model.snapshot().state == State.UNCERTAIN


def test_duplicate_job_is_not_restarted_after_success(scenario, observations, path):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 8)
    simulation.finish(COMPLETE, grant=grant)
    duplicate = PickPlaceSimulation(path, speed_percent=20, ownership=model, owner=OWNER)
    result = duplicate.start(lease_seconds=10, sequence_seconds=60)
    assert result.reason == "ownership_duplicate_job_id"
    assert result.confirmed_steps == 0 and result.trace == ()
    assert model.snapshot().state == State.FREE


def test_competing_owner_is_not_released_by_failed_simulation(scenario):
    simulation, model, _ = scenario
    other = model.reserve(OTHER, lease_seconds=10, sequence_seconds=60)
    model.activate(other)
    result = simulation.start(lease_seconds=10, sequence_seconds=60)
    assert result.reason == "ownership_not_free"
    assert model.snapshot().owner == OTHER and model.snapshot().state == State.ACTIVE


@pytest.mark.parametrize("field,value", [
    ("token", 0), ("owner", OTHER), ("owner", replace(OWNER, job_id="wrong-job")),
])
def test_wrong_owner_job_or_stale_token_halts_cycle(scenario, observations, field, value):
    simulation, model, _ = scenario
    grant = start(simulation)
    result = simulation.advance(observations[0], grant=replace(grant, **{field: value}))
    assert result.reason == "wrong_simulation_grant"
    assert result.confirmed_steps == 0 and model.snapshot().state == State.UNCERTAIN


def test_revoked_token_is_checked_by_ownership_model(scenario, observations):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 3)
    model.block(expected_token=grant.token)
    result = simulation.advance(observations[3], grant=grant)
    assert result.reason == "ownership_stale_fence" and result.confirmed_steps == 3
    assert model.snapshot().state == State.UNCERTAIN


def test_old_simulation_does_not_clear_or_block_explicitly_recovered_new_owner(scenario, observations):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 3)
    model.block(expected_token=grant.token)
    model.operator_clear(
        expected_token=model.snapshot().token, operator_id="synthetic-operator",
        local_confirmation=True, stopped_confirmed=True, no_pending_commands=True,
        outputs_safe=True,
    )
    new_grant = model.reserve(OTHER, lease_seconds=10, sequence_seconds=60)
    model.activate(new_grant)
    result = simulation.advance(observations[3], grant=grant)
    assert result.status == "simulated_stopped"
    assert model.snapshot().owner == OTHER and model.snapshot().state == State.ACTIVE
    assert model.snapshot().token == new_grant.token


def test_coordinator_restart_mid_cycle_has_no_automatic_resume(scenario, observations, path):
    simulation, model, clock = scenario
    grant = prefix(simulation, observations, 4)
    restarted = OwnershipModel(model.path, clock=clock)
    result = simulation.advance(observations[4], grant=grant)
    assert result.status == "simulated_stopped" and result.confirmed_steps == 4
    assert result.ownership_state == "unavailable"
    assert restarted.snapshot().state == State.UNCERTAIN
    second = PickPlaceSimulation(path, speed_percent=20, ownership=restarted, owner=OWNER)
    assert second.start(lease_seconds=10, sequence_seconds=60).reason == "ownership_duplicate_job_id"
    assert restarted.snapshot().state == State.UNCERTAIN


@pytest.mark.parametrize("index", [6, 7])
@pytest.mark.parametrize("part", [None, replace(RELEASED, release_confirmed=False), HELD])
def test_unconfirmed_release_prevents_completion(scenario, observations, index, part):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, index)
    result = simulation.advance(replace(observations[index], part=part), grant=grant)
    assert result.status == "simulated_stopped" and result.confirmed_steps == index
    assert simulation.finish(COMPLETE, grant=grant) == result
    assert model.snapshot().state == State.UNCERTAIN


@pytest.mark.parametrize("count", [0, 2, 3, 6, 7])
def test_finish_cannot_skip_remaining_steps(scenario, observations, count):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, count)
    result = simulation.finish(COMPLETE, grant=grant)
    assert result.reason == "incomplete_or_invalid_cycle"
    assert model.snapshot().state == State.UNCERTAIN


def test_invalid_completion_evidence_does_not_free_owner(scenario, observations):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 8)
    result = simulation.finish(CompletionEvidence(sequence_complete=True), grant=grant)
    assert result.reason == "ownership_completion_unconfirmed"
    assert model.snapshot().state == State.UNCERTAIN


@pytest.mark.parametrize("index", [2, 6])
def test_pump_exchange_is_required_at_both_hold_points(scenario, observations, index):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, index)
    result = simulation.advance(replace(observations[index], pump=None), grant=grant)
    assert result.reason == "pump_exchange_missing" and result.confirmed_steps == index
    assert model.snapshot().state == State.UNCERTAIN


def test_no_unscheduled_pump_action_in_motion_step(scenario, observations):
    simulation, model, _ = scenario
    grant = start(simulation)
    result = simulation.advance(replace(observations[0], pump=pump_exchange("suck")), grant=grant)
    assert result.reason == "unexpected_pump_exchange" and result.confirmed_steps == 0
    assert model.snapshot().state == State.UNCERTAIN


def test_extra_ninth_step_is_not_accepted(scenario, observations):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 8)
    result = simulation.advance(observations[7], grant=grant)
    assert result.reason == "step_order_mismatch"
    assert result.confirmed_steps == 8 and model.snapshot().state == State.UNCERTAIN


def test_pump_timeout_is_not_retried(scenario, observations):
    simulation, model, _ = scenario
    grant = prefix(simulation, observations, 2)
    pump = replace(observations[2].pump, transport_failure="timeout")
    result = simulation.advance(replace(observations[2], pump=pump), grant=grant)
    assert result.reason == "pump_timeout"
    assert simulation.advance(observations[2], grant=grant) == result
    assert model.snapshot().state == State.UNCERTAIN


def test_no_live_client_or_transport_injection(scenario, observations, path):
    simulation, model, _ = scenario
    calls = []
    def dangerous_callback():
        calls.append(True)
    with pytest.raises(TypeError):
        PickPlaceSimulation(path, speed_percent=20, ownership=model, owner=OWNER,
                            transport=dangerous_callback)
    assert calls == []
    assert simulation.advance(observations[0], grant=None).reason == "not_started"
