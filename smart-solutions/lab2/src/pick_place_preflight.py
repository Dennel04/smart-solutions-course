"""Non-actuating preparation for Lab 1 integration; no live executor.

Lab 1 exposes status/reachability/motion, but no pump method or cross-program
ownership API. This boundary can be injected into StationAdapter for software
tests. With an explicitly injected client, enabled preflight may send status
and reachability requests. It never calls motion/pump methods, arbitrary
pump/ownership callbacks, or returns done. Keep CLI defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Protocol

from .executor import ExecutionOutcome


DEFAULT_POSITIONS = Path(__file__).resolve().parents[2] / "lab1/data/positions.json"
POSITION_NAMES = ("above_source", "source", "above_finished", "finished")
AXES = ("x", "y", "z", "r")


class PreparationError(ValueError):
    """Local diagnostic code, never an instruction or a new wire reason."""


@dataclass(frozen=True)
class PlanStep:
    operation: str
    position: str | None = None


@dataclass(frozen=True)
class LocalPlan:
    positions: tuple[tuple[str, tuple[float, float, float, float]], ...]
    speed_percent: float
    steps: tuple[PlanStep, ...]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PreparationError("duplicate_config_field")
        result[key] = value
    return result


def build_local_plan(
    positions_path: str | Path = DEFAULT_POSITIONS,
    *,
    routine: str = "source_to_finished",
    speed_percent: float | None = None,
) -> LocalPlan:
    """Validate local data and describe a candidate sequence, not a safe path.

    acquire_part/release_part are conceptual hold points, NOT pump API calls.
    Clearance, initial approach, grip feedback and collision-free paths still
    require a separate hardware-reviewed design.
    """
    if routine != "source_to_finished":
        raise PreparationError("invalid_routine")
    try:
        document = json.loads(
            Path(positions_path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, ValueError, TypeError) as error:
        raise PreparationError("positions_unavailable_or_invalid") from error
    if not isinstance(document, dict) or not isinstance(document.get("positions"), dict):
        raise PreparationError("positions_unavailable_or_invalid")
    positions = {}
    for name in POSITION_NAMES:
        raw = document["positions"].get(name)
        if not isinstance(raw, dict) or set(raw) != set(AXES):
            raise PreparationError("missing_or_invalid_taught_position")
        if any(type(raw[axis]) not in (int, float) for axis in AXES):
            raise PreparationError("non_numeric_taught_position")
        try:
            pose = tuple(float(raw[axis]) for axis in AXES)
        except (ValueError, OverflowError) as error:
            raise PreparationError("non_finite_taught_position") from error
        if not all(math.isfinite(value) for value in pose):
            raise PreparationError("non_finite_taught_position")
        # The 440 mm outer reach is documented in AGENTS, not a collision model.
        if math.hypot(*pose[:2]) > 440:
            raise PreparationError("outside_documented_reach")
        positions[name] = pose
    if positions["source"][:2] == positions["finished"][:2]:
        raise PreparationError("source_finished_overlap")
    for above, target in (("above_source", "source"), ("above_finished", "finished")):
        top, bottom = positions[above], positions[target]
        clearance = top[2] - bottom[2]
        if (top[:2] != bottom[:2] or top[3] != bottom[3]
                or not math.isfinite(clearance) or clearance < 20):
            raise PreparationError("invalid_approach_clearance")
    if positions["above_source"][2] != positions["above_finished"][2]:
        raise PreparationError("transfer_plane_unconfirmed")
    try:
        speed = float(speed_percent) if type(speed_percent) in (int, float) else math.nan
    except (ValueError, OverflowError):
        speed = math.nan
    if not math.isfinite(speed) or not 0 < speed <= 20:
        raise PreparationError("local_speed_missing_or_unsafe")
    return LocalPlan(
        tuple(positions.items()), speed,
        (
            PlanStep("move_to_taught", "above_source"),
            PlanStep("move_to_taught", "source"),
            PlanStep("acquire_part"),
            PlanStep("move_to_taught", "above_source"),
            PlanStep("move_to_taught", "above_finished"),
            PlanStep("move_to_taught", "finished"),
            PlanStep("release_part"),
            PlanStep("move_to_taught", "above_finished"),
        ),
    )


class Lab1PreflightClient(Protocol):
    """Existing public Lab 1 signatures only; no client is created here."""

    def get_status(self) -> dict: ...
    def require_safe_status(self, status: dict) -> None: ...
    def check_pose(self, x: float, y: float, z: float) -> bool | None: ...


@dataclass(frozen=True)
class PreflightReport:
    blockers: tuple[str, ...]
    reason: str = "execution_failed"
    plan: LocalPlan | None = None
    physical_execution_allowed: bool = field(default=False, init=False)


class PickPlacePreflightExecutor:
    """Status/reachability DI boundary; all outcomes are terminal refusals.

    No pump/ownership callbacks are accepted or executed. Both interfaces stay
    blocked even when all permitted client checks pass. There is no live switch.
    StationAdapter/StationJobStore retain stable-ID and restart handling.
    """

    def __init__(
        self,
        *,
        client: Lab1PreflightClient | None = None,
        positions_path: str | Path = DEFAULT_POSITIONS,
        speed_percent: float | None = None,
        calibration_confirmed: bool = False,
        preflight_enabled: bool = False,
    ) -> None:
        self.client = client
        self.positions_path = positions_path
        self.speed_percent = speed_percent
        self.calibration_confirmed = calibration_confirmed
        self.preflight_enabled = preflight_enabled
        self.last_report: PreflightReport | None = None

    @property
    def ready(self) -> bool:
        # Means "may run read-only preflight", NOT hardware readiness.
        return self.preflight_enabled is True

    def inspect(self, routine: str = "source_to_finished") -> PreflightReport:
        if routine != "source_to_finished":
            return PreflightReport(("invalid_routine",), "invalid_routine")
        if not self.ready:
            return PreflightReport(("local_preflight_disabled",), "robot_not_enabled")
        try:
            plan = build_local_plan(
                self.positions_path, routine=routine, speed_percent=self.speed_percent
            )
        except PreparationError as error:
            return PreflightReport((str(error),))
        if self.calibration_confirmed is not True:
            return PreflightReport(("calibration_unconfirmed",), plan=plan)
        if self.client is None:
            return PreflightReport(("mg400_client_missing",), plan=plan)
        try:
            status = self.client.get_status()
            if not isinstance(status, dict):
                return PreflightReport(("unknown_status_response",), plan=plan)
            if status.get("enabled") is not True:
                return PreflightReport(("robot_disabled_or_unknown",), "robot_not_enabled", plan)
            if self.client.require_safe_status(status) is not None:
                return PreflightReport(("unknown_safety_response",), plan=plan)
            for _, pose in plan.positions:
                # Upstream may return None for unsupported /api/check. Refuse it.
                if self.client.check_pose(*pose[:3]) is not True:
                    return PreflightReport(("reachability_unconfirmed",), plan=plan)
        except TimeoutError:
            return PreflightReport(("preflight_timeout",), plan=plan)
        except Exception:
            return PreflightReport(("mg400_preflight_failed",), plan=plan)
        # No callback can assert these unverified capabilities into existence.
        return PreflightReport(
            ("pump_interface_missing", "exclusive_owner_interface_missing",
             "live_pump_and_exclusive_control_binding_missing"),
            "executor_busy", plan,
        )

    def execute_pick_place(
        self, routine: str, job_id: str, *,
        session: str, seq: int, atom_sent_ms: int | None,
    ) -> ExecutionOutcome:
        self.last_report = self.inspect(routine)
        return ExecutionOutcome.refused(self.last_report.reason)
