"""Synthetic coordinator/clients only. No physical permissions or robot I/O."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
import socket
import sqlite3
import threading

import pytest
import requests

from src.ownership_model import (
    CompletionEvidence, Incident, Owner, OwnershipDenied, OwnershipModel,
    State, StepEvidence,
)
from src.pick_place_preflight import PickPlacePreflightExecutor


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    attempts = []
    def deny(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Real HTTP/TCP is forbidden")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(requests.sessions.Session, "request", deny)
    yield
    assert attempts == []


class FakeClock:
    def __init__(self):
        self.now = 100.0
    def __call__(self):
        return self.now


OWNER = Owner("synthetic-client", "synthetic-session", "synthetic-job")
OTHER = Owner("other-client", "other-session", "other-job")
STEP_CONFIRMED = StepEvidence(True, True, True, True, True)
SEQUENCE_CONFIRMED = CompletionEvidence(True, True, True, True, True)


def clear_by_operator(model, **overrides):
    confirmation = {
        "expected_token": model.snapshot().token, "operator_id": "synthetic-operator",
        "local_confirmation": True, "stopped_confirmed": True,
        "no_pending_commands": True, "outputs_safe": True,
    }
    confirmation.update(overrides)
    model.operator_clear(**confirmation)


@pytest.fixture
def setup(tmp_path):
    clock = FakeClock()
    model = OwnershipModel(tmp_path / "simulation.sqlite3", clock=clock)
    return model, clock


@pytest.fixture
def ready(setup):
    model, clock = setup
    clear_by_operator(model)
    return model, clock


def reserve(model, owner=OWNER, lease=10, sequence=60):
    return model.reserve(owner, lease_seconds=lease, sequence_seconds=sequence)


def active(model):
    grant = reserve(model)
    model.activate(grant)
    return grant


def confirm_one_step(model, grant):
    admission = model.admit_step(grant, "synthetic-step")
    assert admission.physical_execution_allowed is False
    model.confirm_step(grant, admission.step_id, STEP_CONFIRMED)


def test_initial_state_requires_local_operator(setup):
    model, _ = setup
    assert model.snapshot().state == State.BLOCKED
    assert model.snapshot().physical_execution_allowed is False
    with pytest.raises(OwnershipDenied, match="not_free"):
        reserve(model)
    clear_by_operator(model)
    assert model.snapshot().state == State.FREE


def test_two_simultaneous_clients_have_exactly_one_winner(ready):
    model, _ = ready
    barrier = threading.Barrier(2)
    def request(owner):
        barrier.wait(timeout=5)
        try:
            return reserve(model, owner)
        except OwnershipDenied as error:
            return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(request, (OWNER, OTHER)))
    assert results.count("not_free") == 1
    winner = next(result for result in results if result != "not_free")
    assert model.snapshot().owner == winner.owner
    assert model.snapshot().state == State.RESERVED
    assert winner.physical_execution_allowed is False


def test_owner_is_held_across_all_steps_then_released(ready):
    model, _ = ready
    grant = active(model)
    for step in ("synthetic-one", "synthetic-two"):
        model.admit_step(grant, step)
        with pytest.raises(OwnershipDenied, match="not_free"):
            reserve(model, OTHER)
        model.confirm_step(grant, step, STEP_CONFIRMED)
        assert model.snapshot().state == State.ACTIVE
    model.complete(grant, SEQUENCE_CONFIRMED)
    assert model.snapshot().state == State.FREE
    second = reserve(model, OTHER)
    assert second.token > grant.token
    with pytest.raises(OwnershipDenied):
        model.admit_step(grant, "late-step")


@pytest.mark.parametrize("change", [
    {"token": 0}, {"token": True}, {"epoch": 0}, {"epoch": True},
    {"owner": OTHER}, {"owner": replace(OWNER, job_id="wrong-job")},
    {"owner": replace(OWNER, session_id="wrong-session")},
    {"owner": replace(OWNER, client_id="wrong-client")},
])
def test_other_client_wrong_job_and_stale_fence_cannot_dispatch(ready, change):
    model, _ = ready
    grant = active(model)
    forged = replace(grant, **change)
    with pytest.raises(OwnershipDenied):
        model.admit_step(forged, "attempted-bypass")
    assert model.snapshot().owner == OWNER
    assert model.snapshot().pending_step is None
    confirm_one_step(model, grant)


def test_reserved_owner_cannot_admit_step_before_activation(ready):
    model, _ = ready
    with pytest.raises(OwnershipDenied, match="state_forbids"):
        model.admit_step(reserve(model), "too-early")


def test_only_one_inflight_step_and_no_duplicate_step(ready):
    model, _ = ready
    grant = active(model)
    model.admit_step(grant, "step-one")
    with pytest.raises(OwnershipDenied, match="step_pending"):
        model.admit_step(grant, "step-two")
    with pytest.raises(OwnershipDenied, match="wrong_pending_step"):
        model.confirm_step(grant, "step-two", STEP_CONFIRMED)
    model.confirm_step(grant, "step-one", STEP_CONFIRMED)
    with pytest.raises(OwnershipDenied, match="duplicate_step"):
        model.admit_step(grant, "step-one")


def test_duplicate_job_never_reexecutes_even_with_new_session(ready):
    model, _ = ready
    grant = active(model)
    with pytest.raises(OwnershipDenied, match="duplicate_job_id"):
        reserve(model)
    confirm_one_step(model, grant)
    model.complete(grant, SEQUENCE_CONFIRMED)
    with pytest.raises(OwnershipDenied, match="duplicate_job_id"):
        reserve(model, replace(OTHER, job_id=OWNER.job_id))


def test_completed_history_survives_restart(ready):
    model, clock = ready
    grant = active(model)
    confirm_one_step(model, grant)
    model.complete(grant, SEQUENCE_CONFIRMED)
    restarted = OwnershipModel(model.path, clock=clock)
    clear_by_operator(restarted)
    with pytest.raises(OwnershipDenied, match="duplicate_job_id"):
        reserve(restarted)
    assert reserve(restarted, OTHER).token > grant.token


@pytest.mark.parametrize("operation", ["heartbeat", "activate", "confirm", "complete", "incident"])
def test_wrong_owner_cannot_modify_valid_sequence(ready, operation):
    model, _ = ready
    grant = active(model)
    model.admit_step(grant, "pending")
    forged = replace(grant, owner=OTHER)
    with pytest.raises(OwnershipDenied, match="wrong_owner_or_job"):
        if operation == "heartbeat":
            model.heartbeat(forged, lease_seconds=10)
        elif operation == "activate":
            model.activate(forged)
        elif operation == "confirm":
            model.confirm_step(forged, "pending", STEP_CONFIRMED)
        elif operation == "complete":
            model.complete(forged, SEQUENCE_CONFIRMED)
        else:
            model.report_incident(forged, Incident.UNKNOWN_RESULT)
    assert model.snapshot().state == State.ACTIVE
    assert model.snapshot().pending_step == "pending"


@pytest.mark.parametrize("incident", list(Incident))
def test_crash_connection_loss_unknown_result_and_failure_are_uncertain(ready, incident):
    model, _ = ready
    grant = active(model)
    model.admit_step(grant, "pending")
    model.report_incident(grant, incident)
    snapshot = model.snapshot()
    assert snapshot.state == State.UNCERTAIN and snapshot.reason == incident.value
    assert snapshot.token > grant.token
    with pytest.raises(OwnershipDenied):
        model.heartbeat(grant, lease_seconds=10)
    with pytest.raises(OwnershipDenied, match="not_free"):
        reserve(model, OTHER)


@pytest.mark.parametrize("started", [False, True])
def test_lease_expiry_cannot_transfer_ownership_or_be_revived(ready, started):
    model, clock = ready
    grant = reserve(model)
    if started:
        model.activate(grant)
    clock.now += 10  # exact deadline, without a real sleep
    with pytest.raises(OwnershipDenied):
        model.heartbeat(grant, lease_seconds=10)
    # The denied heartbeat must COMMIT the detected expiry, not roll it back.
    assert model.snapshot().state == State.UNCERTAIN
    assert model.snapshot().reason == "heartbeat_lost"
    clock.now += 10000
    with pytest.raises(OwnershipDenied, match="not_free"):
        reserve(model, OTHER)
    clear_by_operator(model)
    assert reserve(model, OTHER).token > grant.token


def test_heartbeat_does_not_extend_absolute_sequence_timeout(ready):
    model, clock = ready
    grant = reserve(model, lease=5, sequence=12)
    model.activate(grant)
    for value in (104, 108):
        clock.now = value
        model.heartbeat(grant, lease_seconds=10)
    clock.now = 112
    with pytest.raises(OwnershipDenied):
        model.admit_step(grant, "too-late")
    assert model.snapshot().reason == "sequence_timeout"
    assert model.snapshot().state == State.UNCERTAIN


@pytest.mark.parametrize("state", ["RESERVED", "ACTIVE", "UNCERTAIN", "FREE"])
def test_restart_revokes_old_instance_and_never_resumes(ready, state):
    model, clock = ready
    grant = None
    if state != "FREE":
        grant = reserve(model)
        if state in ("ACTIVE", "UNCERTAIN"):
            model.activate(grant)
            model.admit_step(grant, "pending")
        if state == "UNCERTAIN":
            model.report_incident(grant, Incident.UNKNOWN_RESULT)
    old_token = model.snapshot().token
    clock.now = 1  # monotonic epoch can reset after a machine reboot
    restarted = OwnershipModel(model.path, clock=clock)
    assert restarted.snapshot().state == (State.BLOCKED if state == "FREE" else State.UNCERTAIN)
    assert restarted.snapshot().token > old_token
    with pytest.raises(OwnershipDenied, match="coordinator_restarted"):
        model.snapshot()
    if grant:
        with pytest.raises(OwnershipDenied, match="stale_fence"):
            restarted.activate(grant)
    clear_by_operator(restarted)
    if grant:
        with pytest.raises(OwnershipDenied, match="duplicate_job_id"):
            reserve(restarted)
    assert reserve(restarted, OTHER).token > old_token


@pytest.mark.parametrize("field", [
    "local_confirmation", "stopped_confirmed", "no_pending_commands", "outputs_safe",
])
@pytest.mark.parametrize("value", [False, None, 1, "yes"])
def test_uncertain_requires_all_explicit_operator_confirmations(ready, field, value):
    model, _ = ready
    model.report_incident(active(model), Incident.OWNER_CRASH)
    with pytest.raises(OwnershipDenied, match="operator_confirmation_required"):
        clear_by_operator(model, **{field: value})
    assert model.snapshot().state == State.UNCERTAIN


def test_stale_operator_confirmation_cannot_clear_new_incident(ready):
    model, _ = ready
    model.report_incident(active(model), Incident.OWNER_CRASH)
    previous = model.snapshot().token
    model.block(expected_token=previous)
    with pytest.raises(OwnershipDenied, match="stale_fence"):
        clear_by_operator(model, expected_token=previous)


@pytest.mark.parametrize("field", [item.name for item in fields(StepEvidence)])
def test_step_ack_without_each_feedback_fact_is_unknown(ready, field):
    model, _ = ready
    grant = active(model)
    model.admit_step(grant, "pending")
    with pytest.raises(OwnershipDenied, match="step_result_unconfirmed"):
        model.confirm_step(grant, "pending", replace(STEP_CONFIRMED, **{field: False}))
    assert model.snapshot().state == State.UNCERTAIN


@pytest.mark.parametrize("evidence", [
    {"http_status": 200}, StepEvidence(True), None, replace(STEP_CONFIRMED, no_fault=1),
])
def test_http_200_and_truthy_flags_are_not_step_confirmation(ready, evidence):
    model, _ = ready
    grant = active(model)
    model.admit_step(grant, "pending")
    with pytest.raises(OwnershipDenied, match="step_result_unconfirmed"):
        model.confirm_step(grant, "pending", evidence)


@pytest.mark.parametrize("field", [item.name for item in fields(CompletionEvidence)])
def test_unconfirmed_completion_never_frees_owner(ready, field):
    model, _ = ready
    grant = active(model)
    confirm_one_step(model, grant)
    with pytest.raises(OwnershipDenied, match="completion_unconfirmed"):
        model.complete(grant, replace(SEQUENCE_CONFIRMED, **{field: False}))
    assert model.snapshot().state == State.UNCERTAIN


@pytest.mark.parametrize("pending", [False, True])
def test_completion_requires_confirmed_steps_and_no_pending_step(ready, pending):
    model, _ = ready
    grant = active(model)
    if pending:
        confirm_one_step(model, grant)
        model.admit_step(grant, "next-pending")
    with pytest.raises(OwnershipDenied, match="completion_unconfirmed"):
        model.complete(grant, SEQUENCE_CONFIRMED)
    assert model.snapshot().state == State.UNCERTAIN


def test_operator_cannot_clear_an_active_owner(ready):
    model, _ = ready
    active(model)
    with pytest.raises(OwnershipDenied, match="operator_clear_not_applicable"):
        clear_by_operator(model)


def test_block_and_regressed_clock_inhibit_new_commands(ready):
    model, clock = ready
    grant = active(model)
    clock.now -= 1
    assert model.snapshot().reason == "clock_regressed"
    with pytest.raises(OwnershipDenied):
        model.admit_step(grant, "late")
    clear_by_operator(model)
    model.block(expected_token=model.snapshot().token)
    assert model.snapshot().state == State.BLOCKED


@pytest.mark.parametrize("value", [None, True, -1, float("nan"), float("inf"), 10**400])
def test_invalid_clock_revocation_persists_after_clock_recovers(ready, value):
    model, clock = ready
    grant = active(model)
    clock.now = value
    with pytest.raises(OwnershipDenied, match="invalid_clock"):
        model.snapshot()
    clock.now = 101
    assert model.snapshot().state == State.UNCERTAIN
    assert model.snapshot().reason == "invalid_clock"
    with pytest.raises(OwnershipDenied):
        model.admit_step(grant, "too-late")


@pytest.mark.parametrize("value", [0, -1, 3601, None, True, "10", float("nan"), float("inf")])
def test_invalid_lease_never_claims(ready, value):
    model, _ = ready
    with pytest.raises(OwnershipDenied, match="invalid_duration"):
        reserve(model, lease=value)
    assert model.snapshot().state == State.FREE


@pytest.mark.parametrize("field", ["client_id", "session_id", "job_id"])
@pytest.mark.parametrize("value", ["", "x" * 129, "bad\nname", None])
def test_invalid_identity_never_claims(ready, field, value):
    model, _ = ready
    with pytest.raises(OwnershipDenied, match="invalid_identifier"):
        reserve(model, replace(OWNER, **{field: value}))


def test_uncertain_history_and_pending_step_survive_restart(ready):
    model, clock = ready
    grant = active(model)
    model.admit_step(grant, "pending")
    restarted = OwnershipModel(model.path, clock=clock)
    clear_by_operator(restarted)
    with sqlite3.connect(model.path) as connection:
        assert connection.execute("SELECT state FROM ownership_jobs").fetchone()[0] == "UNCERTAIN"
        assert connection.execute("SELECT state FROM ownership_steps").fetchone()[0] == "UNCERTAIN"


def test_separate_databases_are_not_a_global_robot_lock(ready, tmp_path):
    model, _ = ready
    second = OwnershipModel(tmp_path / "other-simulation.sqlite3")
    clear_by_operator(second)
    first_grant = reserve(model)
    second_grant = reserve(second, OTHER)
    assert first_grant.physical_execution_allowed is False
    assert second_grant.physical_execution_allowed is False


def test_model_does_not_unblock_pick_place_preflight(ready):
    model, _ = ready
    grant = active(model)
    confirm_one_step(model, grant)
    model.complete(grant, SEQUENCE_CONFIRMED)
    preflight = PickPlacePreflightExecutor()
    assert preflight.execute_pick_place(
        "source_to_finished", "synthetic-job", session="synthetic", seq=1, atom_sent_ms=None,
    ).status == "refused"
    assert preflight.last_report.physical_execution_allowed is False
