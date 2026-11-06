"""Durable station-side idempotency and restart state in SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from .models import (
    AtomJob, AtomLetterJob, StationResult,
    LAB1_LETTER_IDENTITY, LEGACY_IDENTITY, lab1_letter_identity,
)


@dataclass(frozen=True)
class ClaimDecision:
    action: str
    result: StationResult | None = None


class StationJobStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS station_jobs (
                    job_id TEXT PRIMARY KEY,
                    letter TEXT NOT NULL DEFAULT '',
                    job_type TEXT NOT NULL DEFAULT 'letter',
                    arg_json TEXT NOT NULL DEFAULT '{}',
                    identity_scheme TEXT NOT NULL DEFAULT 'legacy',
                    may_move INTEGER NOT NULL DEFAULT 0 CHECK(may_move IN (0, 1)),
                    interlock_held INTEGER NOT NULL DEFAULT 0
                        CHECK(interlock_held IN (0, 1) AND interlock_held <= may_move),
                    session TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    atom_sent_ms INTEGER,
                    state TEXT NOT NULL,
                    reason TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE(session, seq)
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(station_jobs)").fetchall()
            }
            if "job_type" not in columns:
                connection.execute(
                    "ALTER TABLE station_jobs ADD COLUMN job_type TEXT NOT NULL DEFAULT 'letter'"
                )
            if "arg_json" not in columns:
                connection.execute(
                    "ALTER TABLE station_jobs ADD COLUMN arg_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "identity_scheme" not in columns:
                connection.execute(
                    "ALTER TABLE station_jobs ADD COLUMN identity_scheme TEXT NOT NULL DEFAULT 'legacy'"
                )
            if "may_move" not in columns:
                connection.execute(
                    "ALTER TABLE station_jobs ADD COLUMN may_move INTEGER NOT NULL DEFAULT 0 CHECK(may_move IN (0, 1))"
                )
            if "interlock_held" not in columns:
                connection.execute(
                    "ALTER TABLE station_jobs ADD COLUMN interlock_held INTEGER NOT NULL DEFAULT 0 "
                    "CHECK(interlock_held IN (0, 1) AND interlock_held <= may_move)"
                )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS one_live_interlock "
                "ON station_jobs(interlock_held) WHERE interlock_held = 1"
            )
            for row in connection.execute(
                "SELECT job_id, letter, arg_json FROM station_jobs"
            ).fetchall():
                if row["arg_json"] == "{}":
                    connection.execute(
                        "UPDATE station_jobs SET arg_json = ? WHERE job_id = ?",
                        (self._argument_json({"letter": row["letter"]}), row["job_id"]),
                    )
            # Recovery must not free a possibly moving robot's interlock.
            connection.execute(
                "UPDATE station_jobs SET interlock_held = 1 "
                "WHERE may_move = 1 AND state = 'in_progress'"
            )
            connection.execute(
                """
                UPDATE station_jobs
                   SET state = 'refused', reason = 'ambiguous_after_restart', updated_at = ?
                 WHERE state = 'in_progress'
                """,
                (self._now(),),
            )

    @staticmethod
    def _result(row: sqlite3.Row, job_id: str | None = None) -> StationResult:
        return StationResult(job_id or row["job_id"], row["state"], row["reason"])

    @staticmethod
    def _argument_json(argument: dict[str, str]) -> str:
        return json.dumps(argument, separators=(",", ":"), sort_keys=True)

    @classmethod
    def _same_payload(cls, row: sqlite3.Row, job: AtomJob) -> bool:
        logical_match = (
            row["job_type"] == job.job_type
            and row["arg_json"] == cls._argument_json(job.argument)
        )
        if not logical_match:
            return False
        # New callers can retrieve legacy results without rewriting their keys.
        if isinstance(job, AtomLetterJob) and (
            row["identity_scheme"] == LAB1_LETTER_IDENTITY
            or job.identity_scheme == LAB1_LETTER_IDENTITY
        ):
            return True
        return (
            row["session"] == job.session
            and row["seq"] == job.seq
            and row["atom_sent_ms"] == job.atom_sent_ms
        )

    def claim(self, job: AtomJob) -> ClaimDecision:
        return self._claim(job, may_move=False)

    @classmethod
    def _existing_decision(cls, row: sqlite3.Row, job: AtomJob, *, may_move: bool) -> ClaimDecision:
        if not cls._same_payload(row, job) or bool(row["may_move"]) != may_move:
            return ClaimDecision("conflict", StationResult(job.job_id, "refused", "duplicate_conflict"))
        if row["state"] == "in_progress":
            return ClaimDecision("busy", StationResult(job.job_id, "refused", "executor_busy"))
        return ClaimDecision("cached", cls._result(row))

    def lookup_live(self, job: AtomLetterJob) -> ClaimDecision | None:
        """Read existing decisions without granting permission or changing history."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM station_jobs WHERE job_id = ?", (job.job_id,)
            ).fetchone()
        return None if row is None else self._existing_decision(row, job, may_move=True)

    def claim_live(self, job: AtomJob, *, local_execution_enabled: bool = False) -> ClaimDecision:
        """Reserve SQLite permission only; this does not execute robot commands."""
        if local_execution_enabled is not True:
            return ClaimDecision("blocked", StationResult(job.job_id, "refused", "robot_not_enabled"))
        return self._claim(job, may_move=True)

    def _claim(self, job: AtomJob, *, may_move: bool) -> ClaimDecision:
        identity_scheme = job.identity_scheme if isinstance(job, AtomLetterJob) else LEGACY_IDENTITY
        if identity_scheme not in (LEGACY_IDENTITY, LAB1_LETTER_IDENTITY):
            raise ValueError("unsupported station identity scheme")
        if identity_scheme == LAB1_LETTER_IDENTITY and (
            job.session, job.seq
        ) != lab1_letter_identity(job.job_id):
            raise ValueError("Lab 1 identity was not derived before claim")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM station_jobs WHERE job_id = ?", (job.job_id,)
            ).fetchone()
            if existing is not None:
                decision = self._existing_decision(existing, job, may_move=may_move)
                connection.commit()
                return decision

            if may_move and connection.execute(
                "SELECT job_id FROM station_jobs WHERE interlock_held = 1 LIMIT 1"
            ).fetchone() is not None:
                connection.commit()
                return ClaimDecision("blocked", StationResult(job.job_id, "refused", "executor_busy"))

            legacy_duplicate = connection.execute(
                "SELECT * FROM station_jobs WHERE session = ? AND seq = ?",
                (job.session, job.seq),
            ).fetchone()
            if legacy_duplicate is not None:
                connection.commit()
                return ClaimDecision(
                    "conflict",
                    StationResult(job.job_id, "refused", "duplicate_conflict"),
                )

            active = connection.execute(
                "SELECT job_id FROM station_jobs WHERE state = 'in_progress' LIMIT 1"
            ).fetchone()
            if active is not None:
                connection.commit()
                return ClaimDecision(
                    "busy", StationResult(job.job_id, "refused", "executor_busy")
                )

            inserted = connection.execute(
                """
                INSERT INTO station_jobs
                    (job_id, letter, job_type, arg_json, identity_scheme, may_move, interlock_held,
                     session, seq, atom_sent_ms,
                     state, reason, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_progress', NULL, ?)
                """,
                (
                    job.job_id,
                    job.argument.get("letter", ""),
                    job.job_type,
                    self._argument_json(job.argument),
                    identity_scheme,
                    int(may_move),
                    int(may_move),
                    job.session,
                    job.seq,
                    job.atom_sent_ms,
                    self._now(),
                ),
            ).rowcount
            if inserted != 1:
                raise RuntimeError("station claim was not persisted")
            if may_move:
                stored = connection.execute(
                    "SELECT may_move, interlock_held, state FROM station_jobs WHERE job_id = ?",
                    (job.job_id,),
                ).fetchone()
                if stored is None or tuple(stored) != (1, 1, "in_progress"):
                    raise RuntimeError("live interlock was not persisted")
            connection.commit()
            return ClaimDecision("execute")
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def finish(self, result: StationResult, *, completion_confirmed: bool = False) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state, may_move, interlock_held FROM station_jobs WHERE job_id = ?",
                (result.job_id,),
            ).fetchone()
            if row is None or row["state"] != "in_progress":
                raise RuntimeError("station job was not in progress")
            release = bool(row["may_move"]) and result.status == "done"
            if row["may_move"] and (
                not row["interlock_held"] or (release and completion_confirmed is not True)
            ):
                raise RuntimeError("live completion requires held interlock and confirmed success")
            changed = connection.execute(
                """
                UPDATE station_jobs
                   SET state = ?, reason = ?, updated_at = ?,
                       interlock_held = CASE WHEN ? THEN 0 ELSE interlock_held END
                 WHERE job_id = ? AND state = 'in_progress'
                """,
                (result.status, result.reason, self._now(), release, result.job_id),
            ).rowcount
            if changed != 1:
                raise RuntimeError("station job was not in progress")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def interlock_job_id(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT job_id FROM station_jobs WHERE interlock_held = 1"
            ).fetchone()
        return None if row is None else row["job_id"]

    def confirm_safe(
        self, job_id: str, *, local_confirmation: bool = False,
        robot_stopped: bool = False, no_pending_motion: bool = False,
    ) -> None:
        """Local operator assertions only; never proof obtained from the robot."""
        if any(value is not True for value in (local_confirmation, robot_stopped, no_pending_motion)):
            raise ValueError("local confirmation, stopped robot and no pending motion are required")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """UPDATE station_jobs
                      SET interlock_held = 0,
                          reason = CASE WHEN state = 'in_progress' THEN 'execution_failed' ELSE reason END,
                          updated_at = CASE WHEN state = 'in_progress' THEN ? ELSE updated_at END,
                          state = CASE WHEN state = 'in_progress' THEN 'refused' ELSE state END
                    WHERE job_id = ? AND may_move = 1 AND interlock_held = 1""",
                (self._now(), job_id),
            ).rowcount
            if changed != 1:
                raise RuntimeError("no held live interlock for this job")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(self, job_id: str) -> StationResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM station_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None or row["state"] == "in_progress":
            return None
        return self._result(row)
