"""Deterministic SYNTHETIC pick-place transcript checker, not an executor.

No clients, transports, callbacks, robot commands or StationAdapter interface.
Inputs are scripted observations; neither vacuum nor physical safety is tested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import sqlite3

from .ownership_model import (
    CompletionEvidence, Grant, Incident, Owner, OwnershipDenied, OwnershipModel,
    State, StepEvidence,
)
from .pick_place_preflight import LocalPlan, PlanStep, PreparationError, build_local_plan
from .pump_contract import HttpReply, assess_pump_exchange


class PartState(str, Enum):
    AT_SOURCE = "at_source"
    HELD = "held"
    AT_FINISHED = "at_finished"
    UNKNOWN = "unknown"


class SimulatedFailure(str, Enum):
    MOTION_FAILED = "motion_failed"
    UNKNOWN_MOTION = "unknown_motion_result"
    TIMEOUT = "timeout"
    CONNECTION_LOST = "connection_lost"


@dataclass(frozen=True)
class SyntheticPartEvidence:
    calibration_confirmed: bool = False
    sample_fresh: bool = False
    vacuum_detected: bool | None = None
    part_held: bool | None = None
    release_confirmed: bool = False


@dataclass(frozen=True)
class SyntheticPumpExchange:
    config: HttpReply | None = None
    command: HttpReply | None = None
    status: HttpReply | None = None
    transport_failure: str | None = None


@dataclass(frozen=True)
class SyntheticStepObservation:
    step: PlanStep
    feedback: StepEvidence = field(default_factory=StepEvidence)
    pump: SyntheticPumpExchange | None = None
    part: SyntheticPartEvidence | None = None
    failure: SimulatedFailure | None = None


@dataclass(frozen=True)
class TraceEntry:
    step_number: int
    step: PlanStep
    token: int
    outcome: str
    part_state: PartState


@dataclass(frozen=True)
class SimulationResult:
    status: str
    reason: str
    owner: Owner
    fencing_token: int | None
    ownership_state: str
    ownership_reason: str
    confirmed_steps: int
    part_state: PartState
    trace: tuple[TraceEntry, ...]
    hardware_used: bool = field(default=False, init=False)
    physical_execution_allowed: bool = field(default=False, init=False)
    automatic_retry_allowed: bool = field(default=False, init=False)


def load_synthetic_plan(path: str | Path, *, routine: str, speed_percent: float) -> LocalPlan:
    """Require an explicit synthetic file; reuse published position validation.

    The marker prevents accidental use of Lab 1's file, not malicious relabeling.
    No synthetic coordinates or timing/calibration defaults live in this module.
    """
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise PreparationError("synthetic_positions_unavailable") from error
    if not isinstance(document, dict) or document.get("synthetic") is not True:
        raise PreparationError("synthetic_marker_required")
    plan = build_local_plan(path, routine=routine, speed_percent=speed_percent)
    if len(plan.steps) != 8:
        raise PreparationError("unexpected_plan_length")
    return plan


class PickPlaceSimulation:
    """Single-use offline state machine; no ready/execute_pick_place method.

    Supply a simulation-only OwnershipModel with a fake clock/database. Only
    the caller may model operator_clear; this class never releases uncertainty.
    """

    def __init__(
        self, synthetic_positions_path: str | Path, *, speed_percent: float,
        ownership: OwnershipModel, owner: Owner, routine: str = "source_to_finished",
    ):
        self._plan = load_synthetic_plan(
            synthetic_positions_path, routine=routine, speed_percent=speed_percent,
        )
        if type(ownership) is not OwnershipModel or type(owner) is not Owner:
            raise ValueError("simulation ownership model and owner required")
        self._ownership = ownership
        self._owner = owner
        self._grant: Grant | None = None
        self._started = False
        self._terminal: SimulationResult | None = None
        self._cursor = 0
        self._part = PartState.AT_SOURCE
        self._trace: list[TraceEntry] = []

    @property
    def plan(self) -> LocalPlan:
        return self._plan

    @property
    def grant(self) -> Grant | None:
        return self._grant

    def _result(self, status: str, reason: str) -> SimulationResult:
        snapshot = None
        try:
            snapshot = self._ownership.snapshot()
            state, ownership_reason = snapshot.state.value, snapshot.reason
        except (OwnershipDenied, sqlite3.Error) as error:
            state = "unavailable"
            ownership_reason = str(error) if isinstance(error, OwnershipDenied) else "store_error"
        if status == "simulated_in_progress" and (
            snapshot is None or state != State.ACTIVE.value or snapshot.owner != self._owner
            or self._grant is None or snapshot.token != self._grant.token
        ):
            return self._stop("ownership_" + ownership_reason)
        if status == "simulated_complete" and snapshot is None:
            return self._stop("ownership_" + ownership_reason)
        return SimulationResult(
            status, reason, self._owner, None if self._grant is None else self._grant.token,
            state, ownership_reason, self._cursor, self._part, tuple(self._trace),
        )

    def _stop(self, reason: str) -> SimulationResult:
        if self._terminal is not None:
            return self._terminal
        if self._grant is not None:
            self._part = PartState.UNKNOWN
            try:
                self._ownership.report_incident(self._grant, Incident.UNKNOWN_RESULT)
            except (OwnershipDenied, sqlite3.Error):
                # A revoked grant/restarted coordinator cannot be reclaimed here.
                # In particular, never clear or block a competing new owner.
                pass
        self._terminal = self._result("simulated_stopped", reason)
        return self._terminal

    def start(self, *, lease_seconds: float, sequence_seconds: float) -> SimulationResult:
        if self._terminal is not None:
            return self._terminal
        if self._started:
            return self._stop("already_started")
        self._started = True
        try:
            self._grant = self._ownership.reserve(
                self._owner, lease_seconds=lease_seconds, sequence_seconds=sequence_seconds,
            )
            self._ownership.activate(self._grant)
        except (OwnershipDenied, sqlite3.Error) as error:
            reason = str(error) if isinstance(error, OwnershipDenied) else "store_error"
            return self._stop("ownership_" + reason)
        return self._result("simulated_in_progress", "synthetic_cycle_started")

    @staticmethod
    def _part_error(part: SyntheticPartEvidence | None, *, held: bool) -> str | None:
        if type(part) is not SyntheticPartEvidence:
            return "part_confirmation_missing"
        if part.calibration_confirmed is not True:
            return "calibration_unconfirmed"
        if part.sample_fresh is not True:
            return "pressure_sample_stale"
        if held:
            if part.vacuum_detected is not True:
                return "vacuum_unconfirmed"
            if part.part_held is not True or part.release_confirmed is not False:
                return "grip_unconfirmed"
        elif (part.vacuum_detected is not False or part.part_held is not False
              or part.release_confirmed is not True):
            return "release_unconfirmed"
        return None

    def advance(self, observation: SyntheticStepObservation, *, grant: Grant) -> SimulationResult:
        if self._terminal is not None:
            return self._terminal
        if self._grant is None or not self._started:
            return self._stop("not_started")
        if grant != self._grant:
            return self._stop("wrong_simulation_grant")
        if (type(observation) is not SyntheticStepObservation
                or self._cursor >= len(self._plan.steps)
                or observation.step != self._plan.steps[self._cursor]):
            return self._stop("step_order_mismatch")
        step = self._plan.steps[self._cursor]
        step_id = "synthetic-step-" + str(self._cursor + 1)
        try:
            self._ownership.admit_step(grant, step_id)
        except (OwnershipDenied, sqlite3.Error) as error:
            reason = str(error) if isinstance(error, OwnershipDenied) else "store_error"
            return self._stop("ownership_" + reason)
        self._trace.append(TraceEntry(self._cursor + 1, step, grant.token, "admitted", self._part))
        if observation.failure is not None:
            reason = (observation.failure.value if type(observation.failure) is SimulatedFailure
                      else "invalid_failure_observation")
            return self._stop(reason)
        if step.operation in ("acquire_part", "release_part"):
            if type(observation.pump) is not SyntheticPumpExchange:
                return self._stop("pump_exchange_missing")
            exchange = observation.pump
            mode = "suck" if step.operation == "acquire_part" else "off"
            pump = assess_pump_exchange(
                mode, config=exchange.config, command=exchange.command,
                status=exchange.status, transport_failure=exchange.transport_failure,
            )
            if pump.command_acknowledged is not True or pump.outputs_match is not True:
                return self._stop("pump_" + pump.reason)
        elif observation.pump is not None:
            return self._stop("unexpected_pump_exchange")
        # No transfer before a separate grip assertion; no final retreat before
        # separately confirmed release. DO outputs alone never set part state.
        if step.operation == "acquire_part" or self._part == PartState.HELD:
            held = step.operation != "release_part"
            reason = self._part_error(observation.part, held=held)
            if reason:
                return self._stop(reason)
        elif self._part == PartState.AT_FINISHED:
            reason = self._part_error(observation.part, held=False)
            if reason:
                return self._stop(reason)
        elif observation.part is not None:
            return self._stop("unexpected_part_confirmation")
        if step.operation == "release_part" and self._part != PartState.HELD:
            return self._stop("release_without_grip")
        if self._cursor in (3, 4, 5) and self._part != PartState.HELD:
            return self._stop("transfer_without_grip")
        try:
            # Published ownership checks require all feedback facts; HTTP 200
            # or outputs_match is not substituted for a StepEvidence object.
            self._ownership.confirm_step(grant, step_id, observation.feedback)
        except (OwnershipDenied, sqlite3.Error) as error:
            reason = str(error) if isinstance(error, OwnershipDenied) else "store_error"
            return self._stop("ownership_" + reason)
        if step.operation == "acquire_part":
            self._part = PartState.HELD
        elif step.operation == "release_part":
            self._part = PartState.AT_FINISHED
        self._trace.append(TraceEntry(self._cursor + 1, step, grant.token, "confirmed", self._part))
        self._cursor += 1
        return self._result("simulated_in_progress", "synthetic_step_confirmed")

    def finish(self, evidence: CompletionEvidence, *, grant: Grant) -> SimulationResult:
        if self._terminal is not None:
            return self._terminal
        if (self._grant is None or grant != self._grant
                or self._cursor != 8 or self._part != PartState.AT_FINISHED):
            return self._stop("incomplete_or_invalid_cycle")
        try:
            self._ownership.complete(grant, evidence)
        except (OwnershipDenied, sqlite3.Error) as error:
            reason = str(error) if isinstance(error, OwnershipDenied) else "store_error"
            return self._stop("ownership_" + reason)
        self._terminal = self._result("simulated_complete", "synthetic_cycle_confirmed")
        return self._terminal
