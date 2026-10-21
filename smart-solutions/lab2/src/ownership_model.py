"""Isolated ownership simulation, NOT a robot lock or a command gateway.

Only SQLite is accessed. Evidence and identities are synthetic assertions, not
authenticated hardware facts. No instance or grant permits physical execution.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass, field, fields
from enum import Enum
import math
from pathlib import Path
import re
import sqlite3
import time
from typing import Callable


class State(str, Enum):
    FREE = "FREE"
    RESERVED = "RESERVED"
    ACTIVE = "ACTIVE"
    UNCERTAIN = "UNCERTAIN"
    BLOCKED = "BLOCKED"


class Incident(str, Enum):
    OWNER_CRASH = "owner_crash"
    CONNECTION_LOST = "connection_lost"
    UNKNOWN_RESULT = "unknown_result"
    COMMAND_FAILED = "command_failed"


class OwnershipDenied(RuntimeError):
    """Fixed model diagnostic; never a robot command."""


@dataclass(frozen=True)
class Owner:
    client_id: str
    session_id: str
    job_id: str


@dataclass(frozen=True)
class Grant:
    owner: Owner
    token: int
    epoch: int
    physical_execution_allowed: bool = field(default=False, init=False)


@dataclass(frozen=True)
class Snapshot:
    state: State
    token: int
    owner: Owner | None
    pending_step: str | None
    reason: str
    physical_execution_allowed: bool = field(default=False, init=False)


@dataclass(frozen=True)
class StepAdmission:
    grant: Grant
    step_id: str
    physical_execution_allowed: bool = field(default=False, init=False)


@dataclass(frozen=True)
class StepEvidence:
    acknowledged: bool = False
    feedback_fresh: bool = False
    effect_confirmed: bool = False
    no_fault: bool = False
    robot_stopped: bool = False


@dataclass(frozen=True)
class CompletionEvidence:
    sequence_complete: bool = False
    feedback_fresh: bool = False
    robot_stopped: bool = False
    outputs_safe: bool = False
    no_fault: bool = False


def _identifier(value):
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is None:
        raise OwnershipDenied("invalid_identifier")


def _duration(value):
    if type(value) not in (int, float) or not 0 < value <= 3600:
        raise OwnershipDenied("invalid_duration")
    return float(value)


def _confirmed(value, expected_type):
    return type(value) is expected_type and all(
        getattr(value, item.name) is True for item in fields(expected_type)
    )


class OwnershipModel:
    """One simulated coordinator; construction starts a new durable epoch.

    Clients share this object. Reopening the same database models coordinator
    restart, invalidates old instances and never resumes an existing grant.
    This deliberate inhibition is NOT a cross-process gateway lifecycle lock.
    """

    def __init__(self, path: str | Path, *, clock: Callable[[], float] = time.monotonic):
        if str(path) in ("", ":memory:"):
            raise ValueError("an explicit file-backed simulation database is required")
        self.path = str(path)
        self.clock = clock
        now = self._now()
        with closing(self._connect()) as connection, connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS ownership_state (
                    id INTEGER PRIMARY KEY CHECK(id = 1), state TEXT NOT NULL,
                    token INTEGER NOT NULL, epoch INTEGER NOT NULL,
                    client_id TEXT, session_id TEXT, job_id TEXT,
                    lease_deadline REAL, sequence_deadline REAL, last_now REAL NOT NULL,
                    pending_step TEXT, reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ownership_jobs (
                    job_id TEXT PRIMARY KEY, client_id TEXT NOT NULL,
                    session_id TEXT NOT NULL, token INTEGER NOT NULL, state TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ownership_steps (
                    job_id TEXT NOT NULL, step_id TEXT NOT NULL, state TEXT NOT NULL,
                    PRIMARY KEY(job_id, step_id)
                );
            """)
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection)
            if row is None:
                connection.execute("""INSERT INTO ownership_state
                    (id, state, token, epoch, last_now, reason)
                    VALUES (1, 'BLOCKED', 1, 1, ?, 'startup_requires_operator')""", (now,))
            else:
                state = "UNCERTAIN" if row["job_id"] is not None else "BLOCKED"
                self._invalidate(connection, row, state, "coordinator_restart")
                connection.execute("""UPDATE ownership_state SET epoch=epoch+1,
                    last_now=?, lease_deadline=NULL, sequence_deadline=NULL WHERE id=1""", (now,))
            self.epoch = self._row(connection)["epoch"]

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _row(connection):
        return connection.execute("SELECT * FROM ownership_state WHERE id=1").fetchone()

    def _now(self):
        try:
            value = self.clock()
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError
            return float(value)
        except Exception as error:
            raise OwnershipDenied("invalid_clock") from error

    @staticmethod
    def _invalidate(connection, row, state, reason):
        connection.execute("""UPDATE ownership_state
            SET state=?, token=token+1, reason=? WHERE id=1""", (state, reason))
        if row["job_id"] is not None:
            connection.execute("UPDATE ownership_jobs SET state='UNCERTAIN' WHERE job_id=?",
                               (row["job_id"],))
            connection.execute("""UPDATE ownership_steps SET state='UNCERTAIN'
                WHERE job_id=? AND state='PENDING'""", (row["job_id"],))

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection)
            if row["epoch"] != self.epoch:
                raise OwnershipDenied("coordinator_restarted")
            try:
                now = self._now()
            except OwnershipDenied:
                state = "UNCERTAIN" if row["job_id"] is not None else "BLOCKED"
                self._invalidate(connection, row, state, "invalid_clock")
                raise
            reason = None
            if now < row["last_now"]:
                reason = "clock_regressed"
            elif row["state"] in ("RESERVED", "ACTIVE"):
                if now >= row["sequence_deadline"]:
                    reason = "sequence_timeout"
                elif now >= row["lease_deadline"]:
                    reason = "heartbeat_lost"
            if reason:
                state = "UNCERTAIN" if row["job_id"] is not None else "BLOCKED"
                self._invalidate(connection, row, state, reason)
            connection.execute("UPDATE ownership_state SET last_now=? WHERE id=1", (now,))
            yield connection, self._row(connection), now
            connection.commit()
        except OwnershipDenied:
            # A denial must not roll back a timeout/revocation detected above.
            connection.commit()
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _snapshot(row):
        owner = (None if row["job_id"] is None else
                 Owner(row["client_id"], row["session_id"], row["job_id"]))
        return Snapshot(State(row["state"]), row["token"], owner,
                        row["pending_step"], row["reason"])

    def snapshot(self) -> Snapshot:
        with self._transaction() as (_, row, _):
            return self._snapshot(row)

    @staticmethod
    def _require_grant(row, grant, states):
        if type(grant) is not Grant or type(grant.owner) is not Owner:
            raise OwnershipDenied("invalid_grant")
        if (type(grant.token) is not int or type(grant.epoch) is not int
                or grant.token != row["token"] or grant.epoch != row["epoch"]):
            raise OwnershipDenied("stale_fence")
        expected = Owner(row["client_id"], row["session_id"], row["job_id"])
        if grant.owner != expected:
            raise OwnershipDenied("wrong_owner_or_job")
        if row["state"] not in states:
            raise OwnershipDenied("state_forbids_operation")

    def reserve(self, owner: Owner, *, lease_seconds: float, sequence_seconds: float) -> Grant:
        if type(owner) is not Owner:
            raise OwnershipDenied("invalid_owner")
        for value in (owner.client_id, owner.session_id, owner.job_id):
            _identifier(value)
        lease, sequence = _duration(lease_seconds), _duration(sequence_seconds)
        with self._transaction() as (connection, row, now):
            if connection.execute("SELECT 1 FROM ownership_jobs WHERE job_id=?",
                                  (owner.job_id,)).fetchone():
                raise OwnershipDenied("duplicate_job_id")
            if row["state"] != "FREE":
                raise OwnershipDenied("not_free")
            token = row["token"] + 1
            connection.execute("""UPDATE ownership_state SET state='RESERVED', token=?,
                client_id=?, session_id=?, job_id=?, lease_deadline=?, sequence_deadline=?,
                pending_step=NULL, reason='reserved' WHERE id=1""",
                (token, owner.client_id, owner.session_id, owner.job_id,
                 now + min(lease, sequence), now + sequence))
            connection.execute("INSERT INTO ownership_jobs VALUES (?, ?, ?, ?, 'RESERVED')",
                               (owner.job_id, owner.client_id, owner.session_id, token))
            return Grant(owner, token, self.epoch)

    def activate(self, grant: Grant) -> None:
        with self._transaction() as (connection, row, _):
            self._require_grant(row, grant, ("RESERVED",))
            connection.execute("UPDATE ownership_state SET state='ACTIVE', reason='active' WHERE id=1")
            connection.execute("UPDATE ownership_jobs SET state='ACTIVE' WHERE job_id=?",
                               (grant.owner.job_id,))

    def heartbeat(self, grant: Grant, *, lease_seconds: float) -> None:
        lease = _duration(lease_seconds)
        with self._transaction() as (connection, row, now):
            self._require_grant(row, grant, ("RESERVED", "ACTIVE"))
            connection.execute("UPDATE ownership_state SET lease_deadline=? WHERE id=1",
                               (min(now + lease, row["sequence_deadline"]),))

    def admit_step(self, grant: Grant, step_id: str) -> StepAdmission:
        """Record a MODEL step before its hypothetical dispatch; no callback/I/O."""
        _identifier(step_id)
        with self._transaction() as (connection, row, _):
            self._require_grant(row, grant, ("ACTIVE",))
            if row["pending_step"] is not None:
                raise OwnershipDenied("step_pending")
            if connection.execute("SELECT 1 FROM ownership_steps WHERE job_id=? AND step_id=?",
                                  (grant.owner.job_id, step_id)).fetchone():
                raise OwnershipDenied("duplicate_step_id")
            connection.execute("INSERT INTO ownership_steps VALUES (?, ?, 'PENDING')",
                               (grant.owner.job_id, step_id))
            connection.execute("UPDATE ownership_state SET pending_step=? WHERE id=1", (step_id,))
            return StepAdmission(grant, step_id)

    def confirm_step(self, grant: Grant, step_id: str, evidence: StepEvidence) -> None:
        with self._transaction() as (connection, row, _):
            self._require_grant(row, grant, ("ACTIVE",))
            if row["pending_step"] != step_id or step_id is None:
                raise OwnershipDenied("wrong_pending_step")
            if not _confirmed(evidence, StepEvidence):
                self._invalidate(connection, row, "UNCERTAIN", "step_result_unconfirmed")
                raise OwnershipDenied("step_result_unconfirmed")
            connection.execute("UPDATE ownership_steps SET state='CONFIRMED' WHERE job_id=? AND step_id=?",
                               (grant.owner.job_id, step_id))
            connection.execute("UPDATE ownership_state SET pending_step=NULL WHERE id=1")

    def complete(self, grant: Grant, evidence: CompletionEvidence) -> None:
        with self._transaction() as (connection, row, _):
            self._require_grant(row, grant, ("ACTIVE",))
            confirmed = connection.execute("""SELECT COUNT(*) FROM ownership_steps
                WHERE job_id=? AND state='CONFIRMED'""", (grant.owner.job_id,)).fetchone()[0]
            if row["pending_step"] is not None or not confirmed or not _confirmed(evidence, CompletionEvidence):
                self._invalidate(connection, row, "UNCERTAIN", "completion_unconfirmed")
                raise OwnershipDenied("completion_unconfirmed")
            connection.execute("UPDATE ownership_jobs SET state='COMPLETED' WHERE job_id=?",
                               (grant.owner.job_id,))
            self._free(connection, "sequence_confirmed")

    @staticmethod
    def _free(connection, reason):
        connection.execute("""UPDATE ownership_state SET state='FREE', token=token+1,
            client_id=NULL, session_id=NULL, job_id=NULL, lease_deadline=NULL,
            sequence_deadline=NULL, pending_step=NULL, reason=? WHERE id=1""", (reason,))

    def report_incident(self, grant: Grant, incident: Incident) -> None:
        if type(incident) is not Incident:
            raise OwnershipDenied("invalid_incident")
        with self._transaction() as (connection, row, _):
            self._require_grant(row, grant, ("RESERVED", "ACTIVE"))
            self._invalidate(connection, row, "UNCERTAIN", incident.value)

    def block(self, *, expected_token: int) -> None:
        with self._transaction() as (connection, row, _):
            self._require_token(row, expected_token)
            self._invalidate(connection, row, "UNCERTAIN" if row["job_id"] else "BLOCKED", "local_block")

    @staticmethod
    def _require_token(row, token):
        if type(token) is not int or token != row["token"]:
            raise OwnershipDenied("stale_fence")

    def operator_clear(
        self, *, expected_token: int, operator_id: str, local_confirmation: bool,
        stopped_confirmed: bool, no_pending_commands: bool, outputs_safe: bool,
    ) -> None:
        """Synthetic operator assertions only; not an authentication mechanism."""
        _identifier(operator_id)
        with self._transaction() as (connection, row, _):
            self._require_token(row, expected_token)
            if row["state"] not in ("UNCERTAIN", "BLOCKED"):
                raise OwnershipDenied("operator_clear_not_applicable")
            if not all(value is True for value in (
                local_confirmation, stopped_confirmed, no_pending_commands, outputs_safe,
            )):
                raise OwnershipDenied("operator_confirmation_required")
            self._free(connection, "operator_confirmed")
