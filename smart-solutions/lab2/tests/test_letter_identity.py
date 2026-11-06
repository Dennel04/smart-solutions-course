from dataclasses import replace
from hashlib import sha256
import json
import sqlite3
from types import SimpleNamespace

import pytest

from src import models
from src.executor import MockLetterExecutor
from src.models import (
    AtomLetterJob, LAB1_LETTER_IDENTITY, LEGACY_IDENTITY,
    MessageValidationError, StationResult, lab1_letter_identity, parse_atom_message,
)
from src.station_adapter import StationAdapter
from src.station_store import StationJobStore


def payload(job_id="job-1", letter="A", session="post-office", seq=1, uptime=1234):
    return {"job_id": job_id, "letter": letter, "session": session,
            "seq": seq, "atom_sent_ms": uptime}


def send(adapter, **fields):
    return json.loads(adapter.handle_line(json.dumps(payload(**fields))))["post_office_result"]


def adapter_for(database, *, stable=True, enabled=True, store=None):
    executor = MockLetterExecutor()
    adapter = StationAdapter(
        store or StationJobStore(database), executor=executor,
        local_execution_enabled=enabled, use_lab1_letter_identity=stable,
    )
    return adapter, executor


def test_exact_identity_is_stable_and_bounded():
    expected = sha256(b"lab2-letter:job-1").hexdigest()
    assert lab1_letter_identity("job-1") == (expected, 0)
    original = parse_atom_message(payload())
    canonical = original.for_lab1()
    assert canonical == canonical.for_lab1()
    assert (canonical.session, canonical.seq) == (expected, 0)
    assert len(canonical.session) == 64 and canonical.session != "text"
    assert canonical.identity_scheme == LAB1_LETTER_IDENTITY
    assert original.session == "post-office" and original.identity_scheme == LEGACY_IDENTITY


@pytest.mark.parametrize("job_id", ["", "not ascii ä", "x" * 81, "x/y", None])
def test_invalid_identity_input_is_rejected(job_id):
    with pytest.raises(ValueError):
        lab1_letter_identity(job_id)


def test_distinct_jobs_survive_identical_atom_session_and_sequence(tmp_path):
    database = tmp_path / "station.sqlite3"

    class RecordingStore(StationJobStore):
        def claim(self, job):
            assert job.identity_scheme == LAB1_LETTER_IDENTITY
            assert (job.session, job.seq) == lab1_letter_identity(job.job_id)
            return super().claim(job)

    adapter, executor = adapter_for(database, store=RecordingStore(database))
    assert send(adapter, job_id="job-1")["status"] == "done"
    assert send(adapter, job_id="job-2")["status"] == "done"
    assert len(executor.calls) == 2
    assert executor.calls[0].session != executor.calls[1].session
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT job_id, session, seq, identity_scheme FROM station_jobs ORDER BY job_id"
        ).fetchall()
    assert rows == [(job_id, *lab1_letter_identity(job_id), LAB1_LETTER_IDENTITY)
                    for job_id in ("job-1", "job-2")]


def test_atom_replacement_and_restart_return_cached_result(tmp_path):
    database = tmp_path / "station.sqlite3"
    adapter, executor = adapter_for(database)
    expected = send(adapter)
    assert send(adapter, session="replacement-atom", seq=0, uptime=1) == expected
    assert len(executor.calls) == 1
    restarted, new_executor = adapter_for(database)
    assert send(restarted, session="another-boot", seq=99, uptime=0) == expected
    assert new_executor.calls == []


def test_same_id_with_different_letter_is_conflict(tmp_path):
    adapter, executor = adapter_for(tmp_path / "station.sqlite3")
    assert send(adapter)["status"] == "done"
    assert send(adapter, letter="L", uptime=0)["reason"] == "duplicate_conflict"
    assert len(executor.calls) == 1


def test_same_id_with_different_job_type_is_conflict(tmp_path):
    adapter, executor = adapter_for(tmp_path / "station.sqlite3")
    assert send(adapter)["status"] == "done"
    result = json.loads(adapter.handle_line(json.dumps({
        "job": "pick_place", "routine": "source_to_finished", "job_id": "job-1",
        "session": "replacement", "seq": 0, "atom_sent_ms": 0,
    })))["post_office_result"]
    assert result["reason"] == "duplicate_conflict"
    assert len(executor.calls) == 1 and adapter.pick_place_executor.calls == []


@pytest.mark.parametrize("status,reason", [("done", None), ("refused", "execution_failed")])
def test_legacy_terminal_history_is_preserved_without_reexecution(tmp_path, status, reason):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("""CREATE TABLE station_jobs (
            job_id TEXT PRIMARY KEY, letter TEXT NOT NULL, session TEXT NOT NULL,
            seq INTEGER NOT NULL, atom_sent_ms INTEGER, state TEXT NOT NULL,
            reason TEXT, updated_at TEXT NOT NULL, UNIQUE(session, seq))""")
        connection.execute("INSERT INTO station_jobs VALUES (?,?,?,?,?,?,?,?)",
                           ("job-1", "A", "post-office", 1, 1234, status, reason, "original"))
        before = connection.execute("SELECT * FROM station_jobs").fetchall()
    adapter, executor = adapter_for(database)
    result = send(adapter, session="replacement", seq=0, uptime=5)
    assert result == StationResult("job-1", status, reason).as_envelope()["post_office_result"]
    assert executor.calls == []
    with sqlite3.connect(database) as connection:
        after = connection.execute("""SELECT job_id, letter, session, seq, atom_sent_ms,
            state, reason, updated_at FROM station_jobs""").fetchall()
        assert connection.execute("SELECT identity_scheme FROM station_jobs").fetchone() == (LEGACY_IDENTITY,)
    assert after == before


def test_legacy_duplicate_rules_and_mock_call_fields_are_unchanged(tmp_path):
    adapter, executor = adapter_for(tmp_path / "station.sqlite3", stable=False)
    assert send(adapter)["status"] == "done"
    assert send(adapter, job_id="job-2")["reason"] == "duplicate_conflict"
    assert executor.calls == [AtomLetterJob("A", "post-office", 1, "job-1", 1234)]


def test_stable_rows_are_not_executed_again_by_a_legacy_caller(tmp_path):
    database = tmp_path / "station.sqlite3"
    stable, first_executor = adapter_for(database)
    expected = send(stable)
    legacy, executor = adapter_for(database, stable=False)
    assert send(legacy, session="different", seq=5, uptime=9) == expected
    assert len(first_executor.calls) == 1 and executor.calls == []


def test_derived_pair_collision_is_refused_before_executor(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "sha256", lambda _: SimpleNamespace(hexdigest=lambda: "0" * 64))
    adapter, executor = adapter_for(tmp_path / "station.sqlite3")
    assert send(adapter)["status"] == "done"
    assert send(adapter, job_id="job-2")["reason"] == "duplicate_conflict"
    assert len(executor.calls) == 1


def test_sqlite_unique_pair_constraint_is_retained(tmp_path):
    database = tmp_path / "station.sqlite3"
    adapter, _ = adapter_for(database)
    send(adapter, job_id="job-1")
    send(adapter, job_id="job-2")
    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE station_jobs SET session=?, seq=0 WHERE job_id='job-2'",
                               (lab1_letter_identity("job-1")[0],))


def test_incomplete_canonical_claim_is_not_restarted(tmp_path):
    database = tmp_path / "station.sqlite3"
    job = parse_atom_message(payload()).for_lab1()
    store = StationJobStore(database)
    assert store.claim(job).action == "execute"
    restarted, executor = adapter_for(database)
    assert send(restarted, session="replacement", seq=0, uptime=0)["reason"] == "ambiguous_after_restart"
    assert executor.calls == []


def test_incomplete_legacy_claim_is_not_restarted_by_stable_caller(tmp_path):
    database = tmp_path / "station.sqlite3"
    store = StationJobStore(database)
    assert store.claim(parse_atom_message(payload())).action == "execute"
    restarted, executor = adapter_for(database)
    assert send(restarted, session="replacement", seq=0, uptime=0)["reason"] == "ambiguous_after_restart"
    assert executor.calls == []


def test_identity_option_does_not_enable_execution(tmp_path):
    adapter, executor = adapter_for(tmp_path / "station.sqlite3", enabled=False)
    assert send(adapter)["reason"] == "robot_not_enabled"
    assert executor.calls == []


def test_unprepared_stable_identity_cannot_be_claimed(tmp_path):
    store = StationJobStore(tmp_path / "station.sqlite3")
    job = replace(parse_atom_message(payload()), identity_scheme=LAB1_LETTER_IDENTITY)
    with pytest.raises(ValueError):
        store.claim(job)
    assert store.get(job.job_id) is None


def test_identity_marker_is_not_accepted_from_atom():
    message = payload()
    message["identity_scheme"] = LAB1_LETTER_IDENTITY
    with pytest.raises(MessageValidationError):
        parse_atom_message(message)
