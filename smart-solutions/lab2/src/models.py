"""Validated Atom/station protocol models with no hardware dependencies."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


ALLOWED_FIELDS = {"letter", "session", "seq", "atom_sent_ms", "job_id"}
JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
STABLE_REASONS = {
    "invalid_message",
    "invalid_letter",
    "duplicate_conflict",
    "robot_not_enabled",
    "executor_busy",
    "ambiguous_after_restart",
    "execution_failed",
}


class MessageValidationError(ValueError):
    def __init__(self, reason: str, job_id: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.job_id = job_id


@dataclass(frozen=True)
class AtomLetterJob:
    letter: str
    session: str
    seq: int
    job_id: str
    atom_sent_ms: int | None = None


@dataclass(frozen=True)
class StationResult:
    job_id: str
    status: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"done", "refused"}:
            raise ValueError("station result status must be done or refused")
        if self.status == "refused" and self.reason not in STABLE_REASONS:
            raise ValueError("station refusal reason is not stable")
        if self.status == "done" and self.reason is not None:
            raise ValueError("done result must not contain a reason")

    def as_envelope(self) -> dict[str, dict[str, str]]:
        payload = {"id": self.job_id, "status": self.status}
        if self.reason is not None:
            payload["reason"] = self.reason
        return {"post_office_result": payload}

    def to_json_line(self) -> str:
        return json.dumps(self.as_envelope(), separators=(",", ":"), sort_keys=True)


def _best_effort_job_id(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    value = payload.get("job_id")
    return value if isinstance(value, str) and JOB_ID_PATTERN.fullmatch(value) else ""


def parse_atom_message(payload: object) -> AtomLetterJob:
    """Validate the exact JSON object emitted by Lab 2 Atom firmware."""
    job_id = _best_effort_job_id(payload)
    if not isinstance(payload, dict):
        raise MessageValidationError("invalid_message")
    if set(payload) - ALLOWED_FIELDS:
        raise MessageValidationError("invalid_message", job_id)
    if not job_id:
        raise MessageValidationError("invalid_message")

    letter = payload.get("letter")
    if not isinstance(letter, str) or len(letter) != 1 or not ("A" <= letter <= "Z"):
        raise MessageValidationError("invalid_letter", job_id)

    session = payload.get("session")
    if not isinstance(session, str) or not session.strip() or len(session) > 64:
        raise MessageValidationError("invalid_message", job_id)

    seq = payload.get("seq")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise MessageValidationError("invalid_message", job_id)

    atom_sent_ms = payload.get("atom_sent_ms")
    if atom_sent_ms is not None and (
        isinstance(atom_sent_ms, bool) or not isinstance(atom_sent_ms, int) or atom_sent_ms < 0
    ):
        raise MessageValidationError("invalid_message", job_id)

    return AtomLetterJob(
        letter=letter,
        session=session.strip(),
        seq=seq,
        job_id=job_id,
        atom_sent_ms=atom_sent_ms,
    )


def parse_json_line(line: str | bytes) -> tuple[object, str]:
    text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
    try:
        return json.loads(text), text
    except (json.JSONDecodeError, TypeError):
        raise MessageValidationError("invalid_message") from None
