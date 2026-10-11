"""Durable station-side idempotency and restart state in SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from pathlib import Path

from .models import AtomLetterJob, StationResult


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
                    letter TEXT NOT NULL,
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
    def _same_payload(row: sqlite3.Row, job: AtomLetterJob) -> bool:
        return (
            row["letter"] == job.letter
            and row["session"] == job.session
            and row["seq"] == job.seq
            and row["atom_sent_ms"] == job.atom_sent_ms
        )

    def claim(self, job: AtomLetterJob) -> ClaimDecision:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM station_jobs WHERE job_id = ?", (job.job_id,)
            ).fetchone()
            if existing is not None:
                if not self._same_payload(existing, job):
                    connection.commit()
                    return ClaimDecision(
                        "conflict",
                        StationResult(job.job_id, "refused", "duplicate_conflict"),
                    )
                if existing["state"] == "in_progress":
                    connection.commit()
                    return ClaimDecision(
                        "busy", StationResult(job.job_id, "refused", "executor_busy")
                    )
                connection.commit()
                return ClaimDecision("cached", self._result(existing))

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

            connection.execute(
                """
                INSERT INTO station_jobs
                    (job_id, letter, session, seq, atom_sent_ms, state, reason, updated_at)
                VALUES (?, ?, ?, ?, ?, 'in_progress', NULL, ?)
                """,
                (
                    job.job_id,
                    job.letter,
                    job.session,
                    job.seq,
                    job.atom_sent_ms,
                    self._now(),
                ),
            )
            connection.commit()
            return ClaimDecision("execute")
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def finish(self, result: StationResult) -> None:
        with self._connect() as connection:
            changed = connection.execute(
                """
                UPDATE station_jobs
                   SET state = ?, reason = ?, updated_at = ?
                 WHERE job_id = ? AND state = 'in_progress'
                """,
                (result.status, result.reason, self._now(), result.job_id),
            ).rowcount
            if changed != 1:
                raise RuntimeError("station job was not in progress")

    def get(self, job_id: str) -> StationResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM station_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None or row["state"] == "in_progress":
            return None
        return self._result(row)
