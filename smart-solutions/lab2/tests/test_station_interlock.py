from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from threading import Barrier

import pytest

from src.executor import MockLetterExecutor
from src.models import AtomLetterJob, StationResult
from src.station_adapter import StationAdapter
from src.station_store import StationJobStore


def job(job_id="job-1"):
    return AtomLetterJob("A", "post-office", 1, job_id, 1234).for_lab1()


def live(store, job_id="job-1"):
    return store.claim_live(job(job_id), local_execution_enabled=True)


def row(database, job_id="job-1"):
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        found = connection.execute("SELECT * FROM station_jobs WHERE job_id=?", (job_id,)).fetchone()
    return None if found is None else dict(found)


def confirm(store, job_id="job-1", **overrides):
    flags = dict(local_confirmation=True, robot_stopped=True, no_pending_motion=True)
    flags.update(overrides)
    store.confirm_safe(job_id, **flags)


@pytest.fixture
def store(tmp_path):
    return StationJobStore(tmp_path / "station.sqlite3")


def test_live_is_disabled_by_default(store):
    decision = store.claim_live(job())
    assert decision.action == "blocked"
    assert decision.result.reason == "robot_not_enabled"
    assert row(store.path) is None and store.interlock_job_id() is None


def test_permission_is_returned_only_after_committed_live_interlock(store):
    decision = live(store)
    assert decision.action == "execute"
    # A separate connection sees the committed guard before any possible caller action.
    recorded = row(store.path)
    assert (recorded["job_id"], recorded["may_move"], recorded["interlock_held"], recorded["state"]) == (
        "job-1", 1, 1, "in_progress")
    assert store.interlock_job_id() == "job-1"


def test_concurrent_live_claims_only_grant_one_permission(store):
    start = Barrier(2)

    def claim(job_id):
        start.wait(timeout=5)
        return job_id, live(store, job_id).action

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("job-1", "job-2")))
    assert sorted(action for _, action in results) == ["blocked", "execute"]
    winner = next(job_id for job_id, action in results if action == "execute")
    loser = next(job_id for job_id, action in results if action == "blocked")
    assert store.interlock_job_id() == winner and row(store.path, loser) is None


def test_done_requires_confirmation_and_releases_atomically(store):
    live(store)
    with pytest.raises(RuntimeError):
        store.finish(StationResult("job-1", "done"))
    assert row(store.path)["state"] == "in_progress" and store.interlock_job_id() == "job-1"
    store.finish(StationResult("job-1", "done"), completion_confirmed=True)
    recorded = row(store.path)
    assert (recorded["state"], recorded["may_move"], recorded["interlock_held"]) == ("done", 1, 0)
    assert store.interlock_job_id() is None
    assert live(store).action == "cached"
    assert live(store, "job-2").action == "execute"


@pytest.mark.parametrize("incident", ["failed", "timeout", "connection_lost", "unknown_state"])
def test_unsuccessful_completion_keeps_interlock_after_repeated_restart(store, incident):
    # All these future executor incidents map to refusal; no HTTP is simulated here.
    live(store)
    store.finish(StationResult("job-1", "refused", "execution_failed"))
    before = row(store.path)
    for _ in range(2):
        store = StationJobStore(store.path)
        assert store.interlock_job_id() == "job-1"
        assert live(store, "job-2").action == "blocked"
        assert live(store).action == "cached"
        assert row(store.path) == before


def test_crash_recovery_refuses_job_but_keeps_guard(store):
    live(store)
    for _ in range(2):
        store = StationJobStore(store.path)
        assert store.get("job-1") == StationResult("job-1", "refused", "ambiguous_after_restart")
        assert store.interlock_job_id() == "job-1"
        assert live(store, "job-2").action == "blocked"


@pytest.mark.parametrize("missing", ["local_confirmation", "robot_stopped", "no_pending_motion"])
def test_operator_release_requires_all_confirmations(store, missing):
    live(store)
    with pytest.raises(ValueError):
        confirm(store, **{missing: False})
    assert store.interlock_job_id() == "job-1"


def test_operator_release_preserves_terminal_history_and_never_reclaims_old_job(store):
    live(store)
    store.finish(StationResult("job-1", "refused", "execution_failed"))
    before = row(store.path)
    confirm(store)
    after = row(store.path)
    assert after == {**before, "interlock_held": 0}
    assert live(store).action == "cached"
    assert store.get("job-1") == StationResult("job-1", "refused", "execution_failed")
    assert live(store, "job-2").action == "execute"


def test_operator_release_of_unfinished_job_refuses_it_without_replay(store):
    live(store)
    confirm(store)
    assert store.get("job-1") == StationResult("job-1", "refused", "execution_failed")
    assert live(store).action == "cached" and store.interlock_job_id() is None


def test_wrong_job_cannot_release_interlock(store):
    live(store)
    with pytest.raises(RuntimeError):
        confirm(store, "other-job")
    assert store.interlock_job_id() == "job-1"


def test_mock_completion_cannot_clear_live_guard_or_become_live_success(store):
    live(store)
    store.finish(StationResult("job-1", "refused", "execution_failed"))
    assert store.claim(job("mock-job")).action == "execute"
    store.finish(StationResult("mock-job", "done"))
    assert store.interlock_job_id() == "job-1"
    assert live(store, "mock-job").action == "conflict"
    assert store.get("mock-job") == StationResult("mock-job", "done")


@pytest.mark.parametrize("timing,trigger", [
    ("AFTER", "SELECT RAISE(ABORT, 'injected write failure');"),
    ("BEFORE", "SELECT RAISE(IGNORE);"),
    ("AFTER", "UPDATE station_jobs SET interlock_held=0 WHERE job_id=NEW.job_id;"),
])
def test_failed_or_missing_interlock_write_never_grants_permission(store, timing, trigger):
    with sqlite3.connect(store.path) as connection:
        connection.executescript("CREATE TRIGGER fail_live " + timing + " INSERT ON station_jobs "
                                "WHEN NEW.may_move=1 BEGIN " + trigger + " END;")
    with pytest.raises((sqlite3.Error, RuntimeError)):
        live(store)
    assert row(store.path) is None


def test_unique_index_rejects_a_second_held_interlock(store):
    live(store)
    store.finish(StationResult("job-1", "refused", "execution_failed"))
    assert store.claim(job("mock-job")).action == "execute"
    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE station_jobs SET may_move=1, interlock_held=1 WHERE job_id='mock-job'")


def test_recovery_write_error_does_not_free_interlock(store):
    live(store)
    with sqlite3.connect(store.path) as connection:
        connection.executescript("""CREATE TRIGGER fail_recovery BEFORE UPDATE ON station_jobs
            WHEN OLD.may_move=1 BEGIN SELECT RAISE(ABORT, 'injected recovery failure'); END;""")
    with pytest.raises(sqlite3.Error):
        StationJobStore(store.path)
    assert store.interlock_job_id() == "job-1"
    assert live(store, "job-2").action == "blocked"


@pytest.mark.parametrize("after_commit", [False, True])
def test_commit_error_never_returns_live_permission(store, monkeypatch, after_commit):
    class BrokenCommit(sqlite3.Connection):
        def commit(self):
            if after_commit:
                super().commit()
            raise sqlite3.OperationalError("injected commit failure")

    def broken_connect():
        connection = sqlite3.connect(store.path, factory=BrokenCommit)
        connection.row_factory = sqlite3.Row
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(store, "_connect", broken_connect)
        with pytest.raises(sqlite3.Error):
            live(store)
    if after_commit:
        assert store.interlock_job_id() == "job-1"
        assert live(store, "job-2").action == "blocked"
    else:
        assert row(store.path) is None


@pytest.mark.parametrize("operation", ["finish", "confirm"])
def test_release_write_failure_preserves_state_and_guard(store, operation):
    live(store)
    before = row(store.path)
    with sqlite3.connect(store.path) as connection:
        connection.executescript("""CREATE TRIGGER fail_release BEFORE UPDATE ON station_jobs
            WHEN OLD.interlock_held=1 AND NEW.interlock_held=0
            BEGIN SELECT RAISE(ABORT, 'injected release failure'); END;""")
    with pytest.raises(sqlite3.Error):
        if operation == "finish":
            store.finish(StationResult("job-1", "done"), completion_confirmed=True)
        else:
            confirm(store)
    assert row(store.path) == before
    assert live(store, "job-2").action == "blocked"


def test_adapter_store_error_prevents_mock_call(store, monkeypatch):
    executor = MockLetterExecutor()
    adapter = StationAdapter(store, executor=executor, local_execution_enabled=True)

    def unavailable():
        raise sqlite3.OperationalError("injected database unavailable")

    monkeypatch.setattr(store, "_connect", unavailable)
    with pytest.raises(sqlite3.Error):
        adapter.handle_line(json.dumps({"job_id": "job-1", "letter": "A", "session": "post-office", "seq": 1}))
    assert executor.calls == []


def test_old_terminal_rows_migrate_without_changes_or_interlock(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript("""CREATE TABLE station_jobs (
            job_id TEXT PRIMARY KEY, letter TEXT NOT NULL, session TEXT NOT NULL,
            seq INTEGER NOT NULL, atom_sent_ms INTEGER, state TEXT NOT NULL,
            reason TEXT, updated_at TEXT NOT NULL, UNIQUE(session,seq));
            INSERT INTO station_jobs VALUES ('old','A','post-office',1,10,'done',NULL,'original');""")
        before = connection.execute("SELECT * FROM station_jobs").fetchall()
    migrated = StationJobStore(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("""SELECT job_id,letter,session,seq,atom_sent_ms,state,reason,updated_at
            FROM station_jobs""").fetchall() == before
    assert migrated.interlock_job_id() is None
    assert migrated.get("old") == StationResult("old", "done")
    assert live(migrated, "old").action == "conflict"
