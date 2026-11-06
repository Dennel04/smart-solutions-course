import json
import socket
import sqlite3
import sys
from types import SimpleNamespace
from unittest import mock

import pytest
import requests

from src.lab1_letter_executor import Lab1LetterExecutor
from src.models import AtomLetterJob, lab1_letter_identity
from src.station_process_lock import StationLockError, StationProcessLock
from src.station_store import StationJobStore
import src.station_adapter as module
import src.serial_transport as serial_transport


def arguments(tmp_path, **changes):
    values = dict(database=str(tmp_path / "station.sqlite3"), port="synthetic-not-a-device",
                  baud=115200, allow_mock_jobs=False, allow_live_letter=True,
                  confirm_local_safety=True, confirm_exclusive_control=True,
                  lab1_url="http://127.0.0.1:5000")
    values.update(changes)
    return SimpleNamespace(**values)


def message(job_id="synthetic-letter-1"):
    return json.dumps(dict(letter="A", session="post-office", seq=1,
                           atom_sent_ms=1234, job_id=job_id))


@pytest.fixture(autouse=True)
def forbid_hardware_and_network(monkeypatch):
    network = mock.Mock(side_effect=AssertionError("real network is forbidden"))
    usb = mock.Mock(side_effect=AssertionError("real USB is forbidden"))
    monkeypatch.setattr(requests.sessions.Session, "request", network)
    monkeypatch.setattr(socket, "create_connection", network)
    monkeypatch.setattr(serial_transport, "_open_serial", usb)
    monkeypatch.setattr(module, "run_serial_forever", usb)
    yield
    network.assert_not_called()
    usb.assert_not_called()


@pytest.mark.parametrize("local,exclusive", [(False, False), (False, True), (True, False), (1, True)])
def test_missing_local_permission_refuses_before_lock_store_session_or_usb(tmp_path, monkeypatch, local, exclusive):
    args = arguments(tmp_path, confirm_local_safety=local, confirm_exclusive_control=exclusive)
    monkeypatch.setattr(module, "parse_args", lambda: args)
    denied = mock.Mock(side_effect=AssertionError("startup must not advance"))
    monkeypatch.setattr(module, "StationProcessLock", denied)
    monkeypatch.setattr(module, "StationJobStore", denied)
    monkeypatch.setattr(module.requests, "Session", denied)
    assert module.main() == 2
    denied.assert_not_called()


def test_live_cli_uses_real_configured_session_and_preserves_claim_before_post(tmp_path, monkeypatch):
    args = arguments(tmp_path)
    calls, closed = [], []
    close = requests.Session.close

    def fake_request(session, method, url, **kwargs):
        assert type(session) is requests.Session
        assert session.trust_env is False and session.proxies == {} and session.auth is None
        assert session.adapters["http://"].max_retries.total == 0
        assert kwargs["allow_redirects"] is False
        assert kwargs["proxies"] == dict(http=None, https=None, all=None)
        assert 0 < kwargs["timeout"] <= 2.0
        with pytest.raises(StationLockError):
            with StationProcessLock(args.database):
                pass
        with sqlite3.connect(args.database) as connection:
            saved = connection.execute("SELECT state,may_move,interlock_held FROM station_jobs").fetchone()
        assert saved == ("in_progress", 1, 1)
        session_id, seq = lab1_letter_identity("synthetic-letter-1")
        calls.append(method)
        if method == "POST":
            assert url == "http://127.0.0.1:5000/api/letter"
            assert kwargs["json"]["session"] == session_id and kwargs["json"]["seq"] == seq
            code, body = 202, dict(accepted=True, duplicate=False, dry_run=False,
                                   robot_started=True, letter="A", seq=seq)
        else:
            assert method == "GET" and url == "http://127.0.0.1:5000/api/letter/status"
            code, body = 200, dict(ok=True, execution_mode="execute", dry_run=False,
                                   session=session_id, seq=seq, execution_status="completed", error=None)
        response = requests.Response()
        response.status_code = code
        response._content = json.dumps(body).encode()
        response._content_consumed = True
        return response

    def record_close(session):
        # Session shutdown is still inside the database process lock.
        with pytest.raises(StationLockError):
            with StationProcessLock(args.database):
                pass
        closed.append(session)
        close(session)

    def fake_usb(port, baud, adapter):
        assert type(adapter.executor) is Lab1LetterExecutor and adapter.live_letter_integration is True
        line = message()
        assert json.loads(adapter.handle_line(line))["post_office_result"]["status"] == "done"
        assert adapter.store.interlock_job_id() is None
        assert adapter.handle_line(line) == adapter.store.get("synthetic-letter-1").to_json_line()
        assert calls == ["POST", "GET"]
        pick = json.loads(line)
        pick.pop("letter")
        pick.update(job="pick_place", routine="source_to_finished", job_id="synthetic-pick-1", seq=2)
        result = json.loads(adapter.handle_line(json.dumps(pick)))["post_office_result"]
        assert result["status"] == "refused" and result["reason"] == "robot_not_enabled"
        assert adapter.pick_place_executor.calls == []
        assert calls == ["POST", "GET"]

    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(requests.Session, "request", fake_request)
    monkeypatch.setattr(requests.Session, "close", record_close)
    monkeypatch.setattr(module, "run_serial_forever", fake_usb)
    assert module.main() == 0
    assert len(closed) == 1 and calls == ["POST", "GET"]
    with StationProcessLock(args.database):
        pass


def test_live_startup_refuses_existing_interlock_before_session_or_usb(tmp_path, monkeypatch):
    args = arguments(tmp_path)
    store = StationJobStore(args.database)
    job = AtomLetterJob("A", "post-office", 1, "old-job").for_lab1()
    assert store.claim_live(job, local_execution_enabled=True).action == "execute"
    session = mock.Mock(side_effect=AssertionError("HTTP session must not start"))
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(module.requests, "Session", session)
    assert module.main() == 1
    session.assert_not_called()
    assert store.interlock_job_id() == "old-job"
    assert store.get("old-job").reason == "ambiguous_after_restart"


@pytest.mark.parametrize("url", ["http://localhost:5000", "https://127.0.0.1:5000",
                                  "http://192.0.2.1:5000", "http://127.0.0.1:5000/path"])
def test_bad_endpoint_never_opens_usb_or_requests(tmp_path, monkeypatch, url):
    monkeypatch.setattr(module, "parse_args", lambda: arguments(tmp_path, lab1_url=url))
    assert module.main() == 2


def test_session_and_process_lock_close_when_usb_loop_raises(tmp_path, monkeypatch):
    args = arguments(tmp_path)
    sessions = []
    close = requests.Session.close

    def record_close(session):
        sessions.append(session)
        close(session)

    def fail_usb(*args):
        raise RuntimeError("synthetic USB failure")

    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(module, "run_serial_forever", fail_usb)
    monkeypatch.setattr(requests.Session, "close", record_close)
    with pytest.raises(RuntimeError, match="synthetic"):
        module.main()
    assert len(sessions) == 1
    with StationProcessLock(args.database):
        pass


def test_live_transport_error_persists_refusal_and_blocks_next_job(tmp_path, monkeypatch):
    args = arguments(tmp_path)
    calls = []

    def fake_request(session, method, url, **kwargs):
        calls.append(method)
        raise requests.Timeout("synthetic timeout")

    def fake_usb(port, baud, adapter):
        result = json.loads(adapter.handle_line(message()))["post_office_result"]
        assert result["status"] == "refused" and result["reason"] == "execution_failed"
        assert adapter.store.interlock_job_id() == "synthetic-letter-1"
        blocked = json.loads(adapter.handle_line(message("synthetic-letter-2")))["post_office_result"]
        assert blocked["reason"] == "executor_busy" and calls == ["POST"]

    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(requests.Session, "request", fake_request)
    monkeypatch.setattr(module, "run_serial_forever", fake_usb)
    assert module.main() == 0


def test_cli_defaults_and_mutually_exclusive_modes(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["station_adapter", "--port", "synthetic-not-a-device"])
    args = module.parse_args()
    assert not args.allow_live_letter and not args.allow_mock_jobs
    assert not args.confirm_local_safety and not args.confirm_exclusive_control
    monkeypatch.setattr(sys, "argv", ["station_adapter", "--port", "synthetic-not-a-device",
                                     "--allow-mock-jobs", "--allow-live-letter"])
    with pytest.raises(SystemExit) as error:
        module.parse_args()
    assert error.value.code == 2
