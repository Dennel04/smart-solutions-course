"""Smart Solutions Lab 1 station-side letter receiver.

Dry-run is the default. Real motion requires the explicit ``--execute`` flag,
a complete calibration and a safe status from the official mg400-base server.

Run:
    python -m pip install -r requirements.txt
    python station.py --host 0.0.0.0 --port 5000

Test without Atom:
    python mock_atom.py --url http://127.0.0.1:5000 --letter A
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from letter_paths import (
    DEFAULT_LETTERS_PATH,
    LetterPaths,
    get_letter_path,
    load_letter_paths,
)
from mg400_client import MG400Client, MG400Error
from motion_plan import MotionAction, build_motion_plan, format_motion_plan
from robot_calibration import (
    DEFAULT_CALIBRATION_PATH,
    CalibrationError,
    RobotCalibration,
    load_robot_calibration,
)
from robot_mapping import map_normalized_point


app = Flask(__name__)
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    log_path: Path
    letters_path: Path
    dry_run: bool
    calibration_path: Path = DEFAULT_CALIBRATION_PATH
    mg400_url: str = "http://127.0.0.1:8000"
    network_timeout: float = 1.0
    move_timeout: float = 15.0
    move_tolerance: float = 0.5


@dataclass
class ExecutionRecord:
    state: str
    error: str | None = None


CONFIG = Config(
    log_path=Path("data/letter_events.csv"),
    letters_path=DEFAULT_LETTERS_PATH,
    dry_run=True,
)
LOG_LOCK = threading.Lock()
# Flask serves requests on threads: the duplicate check and the update must be atomic.
SEQ_LOCK = threading.Lock()
EXECUTION_LOCK = threading.Lock()

# The latest accepted sequence number per Atom boot/session id.
# It prevents a retry from accidentally starting the same robot drawing twice.
LAST_SEQ: dict[str, int] = {}
# Execute-mode lifecycle per Atom event. Preflight failures are removed so the
# same event can be retried; once the first move is attempted the record stays.
EXECUTION_EVENTS: dict[tuple[str, int], ExecutionRecord] = {}
LETTER_PATHS: LetterPaths = load_letter_paths(CONFIG.letters_path)
MG400_CLIENT_FACTORY = MG400Client


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def monotonic_ns() -> int:
    return time.monotonic_ns()


def ensure_log() -> None:
    CONFIG.log_path.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG.log_path.exists():
        return
    with CONFIG.log_path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                "letter",
                "session",
                "seq",
                "atom_sent_ms",
                "station_received_iso",
                "station_received_monotonic_ns",
                "robot_command_monotonic_ns",
                "status",
                "note",
            ]
        )


def append_log(
    *,
    letter: str,
    session: str,
    seq: int,
    atom_sent_ms: int | None,
    station_received_iso: str,
    station_received_monotonic_ns: int,
    robot_command_monotonic_ns: int | None,
    status: str,
    note: str = "",
) -> None:
    ensure_log()
    with LOG_LOCK, CONFIG.log_path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                letter,
                session,
                seq,
                "" if atom_sent_ms is None else atom_sent_ms,
                station_received_iso,
                station_received_monotonic_ns,
                "" if robot_command_monotonic_ns is None else robot_command_monotonic_ns,
                status,
                note,
            ]
        )


def validate_message(payload: object) -> tuple[str, str, int, int | None]:
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")

    letter = payload.get("letter")
    if not isinstance(letter, str):
        raise ValueError("letter must be a string")

    letter = letter.strip().upper()
    if len(letter) != 1 or not ("A" <= letter <= "Z"):
        raise ValueError("letter must be one character A-Z")

    # Session + sequence make retries idempotent.
    session = payload.get("session", "default")
    if not isinstance(session, str) or not session.strip():
        raise ValueError("session must be a non-empty string")
    session = session.strip()[:64]

    seq = payload.get("seq", 0)
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise ValueError("seq must be a non-negative integer")

    atom_sent_ms = payload.get("atom_sent_ms")
    if atom_sent_ms is not None:
        if isinstance(atom_sent_ms, bool) or not isinstance(atom_sent_ms, int) or atom_sent_ms < 0:
            raise ValueError("atom_sent_ms must be a non-negative integer")

    return letter, session, seq, atom_sent_ms


@app.get("/health")
def health():
    try:
        calibration_complete = load_robot_calibration(CONFIG.calibration_path).is_complete
    except CalibrationError:
        calibration_complete = False
    return jsonify(
        ok=True,
        service="smart-solutions-station",
        execution_mode="dry-run" if CONFIG.dry_run else "execute",
        calibration_complete=calibration_complete,
    )


def _execute_plan(
    plan: list[MotionAction],
    calibration: RobotCalibration,
    client: MG400Client,
    on_first_move: Callable[[int], None],
) -> None:
    """Execute one complete normalized plan after a fresh safety check."""
    calibration.require_complete()
    status = client.get_status()
    client.require_safe_status(status)
    current_x, current_y, current_z, _ = client.pose_from_status(status)

    speed = calibration.motion.speed_percent
    r = calibration.pose.r
    pen_up_z = calibration.pose.pen_up_z
    pen_down_z = calibration.pose.pen_down_z
    if None in (speed, r, pen_up_z, pen_down_z):
        raise CalibrationError("roboti kalibratsioon on puudulik")

    client.set_speed(speed)
    first_move_recorded = False
    for item in plan:
        action = item["action"]
        if action == "PEN_UP":
            current_z = pen_up_z
        elif action == "PEN_DOWN":
            current_z = pen_down_z
        elif action == "MOVE_NORMALIZED":
            point = map_normalized_point(calibration, item["x"], item["y"])
            current_x, current_y = point.x, point.y
        else:
            raise ValueError(f"unknown motion action: {action}")
        if not first_move_recorded:
            on_first_move(monotonic_ns())
            first_move_recorded = True
        client.move_and_wait(
            current_x,
            current_y,
            current_z,
            r,
            tolerance=CONFIG.move_tolerance,
            timeout=CONFIG.move_timeout,
        )


def _run_execution(
    *,
    key: tuple[str, int],
    letter: str,
    atom_sent_ms: int | None,
    received_iso: str,
    received_mono: int,
    plan: list[MotionAction],
    calibration: RobotCalibration,
    client: MG400Client,
) -> None:
    command_ns: int | None = None
    final_state = "completed"
    error: str | None = None

    def record_first_move(value: int) -> None:
        nonlocal command_ns
        command_ns = value

    try:
        _execute_plan(plan, calibration, client, record_first_move)
    except Exception as exc:
        final_state = "failed"
        error = str(exc)
        LOGGER.exception("MG400 letter execution failed for %s seq=%s", *key)
        try:
            client.stop()
        except MG400Error as stop_exc:
            LOGGER.warning("best-effort MG400 stop failed: %s", stop_exc)
    finally:
        with SEQ_LOCK:
            record = EXECUTION_EVENTS[key]
            record.state = final_state
            record.error = error
        try:
            append_log(
                letter=letter,
                session=key[0],
                seq=key[1],
                atom_sent_ms=atom_sent_ms,
                station_received_iso=received_iso,
                station_received_monotonic_ns=received_mono,
                robot_command_monotonic_ns=command_ns,
                status="executed" if final_state == "completed" else "execution_error",
                note="MG400 motion plan completed" if error is None else error,
            )
        except Exception:
            LOGGER.exception("could not write MG400 execution log")
        finally:
            EXECUTION_LOCK.release()


@app.post("/api/letter")
def receive_letter():
    # Timestamp as early as possible after Flask has accepted the request.
    received_mono = monotonic_ns()
    received_iso = utc_iso()

    try:
        payload = request.get_json(force=False, silent=False)
        letter, session, seq, atom_sent_ms = validate_message(payload)
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 400

    try:
        strokes = get_letter_path(letter, LETTER_PATHS)
    except ValueError as exc:
        append_log(
            letter=letter,
            session=session,
            seq=seq,
            atom_sent_ms=atom_sent_ms,
            station_received_iso=received_iso,
            station_received_monotonic_ns=received_mono,
            robot_command_monotonic_ns=None,
            status="path_not_configured",
            note=str(exc),
        )
        return (
            jsonify(
                ok=False,
                error="letter path not configured",
                letter=letter,
                robot_started=False,
            ),
            422,
        )

    plan = build_motion_plan(strokes)
    execution_lock_acquired = False
    execution_key = (session, seq)
    execution_record: ExecutionRecord | None = None
    with SEQ_LOCK:
        previous = LAST_SEQ.get(session)
        execution_record = EXECUTION_EVENTS.get(execution_key)
        duplicate = execution_record is not None or (
            previous is not None and seq <= previous
        )
        if not duplicate:
            if not CONFIG.dry_run:
                execution_lock_acquired = EXECUTION_LOCK.acquire(blocking=False)
                if execution_lock_acquired:
                    execution_record = ExecutionRecord("preflight")
                    EXECUTION_EVENTS[execution_key] = execution_record
            else:
                LAST_SEQ[session] = seq

    if duplicate:
        state = execution_record.state if execution_record else "superseded"
        failed = state in ("failed", "preflight")
        error = (
            execution_record.error
            if state == "failed" and execution_record is not None
            else "preflight is still in progress" if state == "preflight" else None
        )
        append_log(
            letter=letter,
            session=session,
            seq=seq,
            atom_sent_ms=atom_sent_ms,
            station_received_iso=received_iso,
            station_received_monotonic_ns=received_mono,
            robot_command_monotonic_ns=None,
            status=f"duplicate_{state}",
            note=error or "acknowledged; robot command suppressed",
        )
        return (
            jsonify(
                ok=not failed,
                duplicate=True,
                letter=letter,
                seq=seq,
                station_received_iso=received_iso,
                robot_started=state in ("started", "failed", "completed"),
                dry_run=CONFIG.dry_run,
                execution_status=state,
                **({"error": error} if error else {}),
            ),
            409 if failed else (202 if state == "started" else 200),
        )

    if not CONFIG.dry_run and not execution_lock_acquired:
        append_log(
            letter=letter,
            session=session,
            seq=seq,
            atom_sent_ms=atom_sent_ms,
            station_received_iso=received_iso,
            station_received_monotonic_ns=received_mono,
            robot_command_monotonic_ns=None,
            status="busy",
            note="another letter execution is already running",
        )
        return (
            jsonify(
                ok=False,
                error="station is already drawing another letter",
                letter=letter,
                robot_started=False,
                dry_run=False,
            ),
            409,
        )

    if not CONFIG.dry_run:
        try:
            calibration = load_robot_calibration(CONFIG.calibration_path)
            calibration.require_complete()
            client = MG400_CLIENT_FACTORY(
                CONFIG.mg400_url, network_timeout=CONFIG.network_timeout
            )
            # Complete the safety gate while this request owns the busy lock.
            # No MG400 POST is made during preflight.
            status = client.get_status()
            client.require_safe_status(status)
            client.pose_from_status(status)
        except (CalibrationError, MG400Error, ValueError) as exc:
            with SEQ_LOCK:
                # The event was not accepted; the same Atom seq may retry.
                EXECUTION_EVENTS.pop(execution_key, None)
            EXECUTION_LOCK.release()
            append_log(
                letter=letter,
                session=session,
                seq=seq,
                atom_sent_ms=atom_sent_ms,
                station_received_iso=received_iso,
                station_received_monotonic_ns=received_mono,
                robot_command_monotonic_ns=None,
                status="preflight_error",
                note=str(exc),
            )
            return (
                jsonify(
                    ok=False,
                    error=str(exc),
                    letter=letter,
                    robot_started=False,
                    dry_run=False,
                ),
                503,
            )

        worker = threading.Thread(
            target=_run_execution,
            kwargs={
                "key": execution_key,
                "letter": letter,
                "atom_sent_ms": atom_sent_ms,
                "received_iso": received_iso,
                "received_mono": received_mono,
                "plan": plan,
                "calibration": calibration,
                "client": client,
            },
            name=f"mg400-letter-{session[:12]}-{seq}",
            daemon=False,
        )
        with SEQ_LOCK:
            try:
                worker.start()
            except RuntimeError as exc:
                EXECUTION_EVENTS.pop(execution_key, None)
                EXECUTION_LOCK.release()
                return jsonify(ok=False, error=str(exc), robot_started=False), 503
            EXECUTION_EVENTS[execution_key].state = "started"
            LAST_SEQ[session] = max(seq, LAST_SEQ.get(session, seq))
        return (
            jsonify(
                ok=True,
                accepted=True,
                duplicate=False,
                letter=letter,
                seq=seq,
                station_received_iso=received_iso,
                robot_started=True,
                execution_status="started",
                dry_run=False,
                action_count=len(plan),
            ),
            202,
        )

    append_log(
        letter=letter,
        session=session,
        seq=seq,
        atom_sent_ms=atom_sent_ms,
        station_received_iso=received_iso,
        station_received_monotonic_ns=received_mono,
        robot_command_monotonic_ns=None,
        status="accepted_dry_run",
        note="normalized motion plan only; no robot command sent",
    )

    print(
        json.dumps(
            {
                "event": "letter",
                "letter": letter,
                "session": session,
                "seq": seq,
                "station_received_iso": received_iso,
                "status": "accepted_dry_run",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print(format_motion_plan(plan), flush=True)

    return (
        jsonify(
            ok=True,
            duplicate=False,
            letter=letter,
            seq=seq,
            station_received_iso=received_iso,
            robot_started=False,
            dry_run=True,
            action_count=len(plan),
        ),
        202,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--log", type=Path, default=Path("data/letter_events.csv"))
    p.add_argument("--letters", type=Path, default=DEFAULT_LETTERS_PATH)
    p.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION_PATH)
    p.add_argument("--mg400-url", default="http://127.0.0.1:8000")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--execute",
        action="store_true",
        help="allow MG400 commands after calibration and safety checks",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="build and print normalized plans without sending robot commands (default)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    CONFIG = Config(
        log_path=args.log,
        letters_path=args.letters,
        dry_run=not args.execute,
        calibration_path=args.calibration,
        mg400_url=args.mg400_url,
    )
    LETTER_PATHS = load_letter_paths(CONFIG.letters_path)
    ensure_log()
    # Debug/reloader off: the station must have one process and one event queue.
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
