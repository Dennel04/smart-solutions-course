from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest import mock

import pytest

from src.executor import MockLetterExecutor
from src.station_process_lock import StationLockError, StationProcessLock


LAB2 = Path(__file__).resolve().parents[1]
PROBE = """
import sys
from src.station_process_lock import StationLockError, StationProcessLock
try:
    with StationProcessLock(sys.argv[1]):
        print('acquired')
except StationLockError:
    print('blocked')
    sys.exit(7)
"""
HOLDER = """
import sys
from pathlib import Path
from src.station_process_lock import StationProcessLock
with StationProcessLock(sys.argv[1]):
    Path(sys.argv[2]).write_text('ready', encoding='ascii')
    sys.stdin.read(1)
"""


def probe(database):
    result = subprocess.run([sys.executable, "-c", PROBE, str(database)], cwd=LAB2,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode in (0, 7), result.stderr
    return result.returncode


@contextmanager
def holder(database, ready_file):
    process = subprocess.Popen(
        [sys.executable, "-c", HOLDER, str(database), str(ready_file)], cwd=LAB2,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready_file.exists():
            assert process.poll() is None, process.communicate(timeout=5)
            assert time.monotonic() < deadline, "child did not acquire the process lock"
            time.sleep(0.01)
        yield process
    finally:
        try:
            process.communicate(input="x" if process.poll() is None else None, timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)


def test_second_process_is_blocked_and_normal_exit_releases_lock(tmp_path):
    database = tmp_path / "station.sqlite3"
    with holder(database, tmp_path / "ready") as process:
        assert probe(database) == 7
        assert not database.exists()  # Locking itself never opens SQLite.
    assert process.returncode == 0
    assert StationProcessLock(database).lock_path.exists()
    assert probe(database) == 0  # A remaining sidecar is not a stale ownership marker.


def test_different_databases_have_independent_os_locks(tmp_path):
    with holder(tmp_path / "one.sqlite3", tmp_path / "ready"):
        assert probe(tmp_path / "two.sqlite3") == 0
        assert probe(tmp_path / "one.sqlite3") == 7


def test_relative_and_absolute_database_paths_share_lock(tmp_path):
    database = tmp_path / "station.sqlite3"
    relative = os.path.relpath(database, LAB2)
    with holder(database, tmp_path / "ready"):
        assert probe(relative) == 7
        assert probe(database.parent / "unused" / ".." / database.name) == 7


def test_symlink_directory_alias_shares_canonical_lock(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable for this user")
    with holder(actual / "station.sqlite3", tmp_path / "ready"):
        assert probe(alias / "station.sqlite3") == 7


def test_killed_child_does_not_leave_permanent_os_lock(tmp_path):
    database = tmp_path / "station.sqlite3"
    with holder(database, tmp_path / "ready") as process:
        assert probe(database) == 7
        process.kill()  # No Python finally/__exit__ can run in the child.
        process.wait(timeout=5)
        assert process.returncode != 0
        assert probe(database) == 0


def test_exception_releases_lock_without_unlinking_sidecar(tmp_path):
    database = tmp_path / "station.sqlite3"
    with pytest.raises(RuntimeError, match="synthetic"):
        with StationProcessLock(database):
            assert probe(database) == 7
            raise RuntimeError("synthetic shutdown")
    assert StationProcessLock(database).lock_path.exists()
    assert probe(database) == 0


def test_reentry_cannot_replace_held_descriptor(tmp_path):
    database = tmp_path / "station.sqlite3"
    lock = StationProcessLock(database)
    with lock:
        with pytest.raises(StationLockError):
            lock.__enter__()
        assert probe(database) == 7
    assert probe(database) == 0


def cli_arguments(database, allow_mock=False):
    return SimpleNamespace(database=str(database), port="synthetic-not-a-device",
                           baud=115200, allow_mock_jobs=allow_mock, allow_live_letter=False,
                           confirm_local_safety=False, confirm_exclusive_control=False,
                           lab1_url="http://127.0.0.1:5000")


@pytest.mark.parametrize("allow_mock", [False, True])
def test_cli_locks_before_store_and_recovery_until_usb_loop_exits(tmp_path, monkeypatch, allow_mock):
    import src.station_adapter as module

    database = tmp_path / "station.sqlite3"
    original_store = module.StationJobStore
    initialize = original_store._initialize
    events = []

    def protected_store(path):
        assert Path(path) == database.resolve()
        assert not database.exists() and probe(path) == 7
        events.append("store")
        return original_store(path)

    def protected_recovery(store):
        assert probe(store.path) == 7
        events.append("recovery")
        initialize(store)

    def fake_usb(port, baud, adapter):
        assert port == "synthetic-not-a-device" and baud == 115200
        assert probe(database) == 7
        assert type(adapter.executor) is MockLetterExecutor
        assert adapter.live_letter_integration is False
        assert adapter.local_execution_enabled is allow_mock
        events.append("usb")

    monkeypatch.setattr(module, "parse_args", lambda: cli_arguments(database, allow_mock))
    monkeypatch.setattr(original_store, "_initialize", protected_recovery)
    monkeypatch.setattr(module, "StationJobStore", protected_store)
    monkeypatch.setattr(module, "run_serial_forever", fake_usb)
    assert module.main() == 0
    assert events == ["store", "recovery", "usb"]
    assert probe(database) == 0


@pytest.mark.parametrize("allow_mock", [False, True])
def test_cli_contention_exits_before_store_or_usb(tmp_path, monkeypatch, capsys, allow_mock):
    import src.station_adapter as module

    database = tmp_path / "station.sqlite3"
    store = mock.Mock(side_effect=AssertionError("Store must not open"))
    usb = mock.Mock(side_effect=AssertionError("USB must not open"))
    monkeypatch.setattr(module, "parse_args", lambda: cli_arguments(database, allow_mock))
    monkeypatch.setattr(module, "StationJobStore", store)
    monkeypatch.setattr(module, "run_serial_forever", usb)
    with holder(database, tmp_path / "ready"):
        assert module.main() == 1
    store.assert_not_called()
    usb.assert_not_called()
    assert not database.exists()
    assert "startup refused" in capsys.readouterr().err


def test_cli_os_lock_error_fails_closed(tmp_path, monkeypatch):
    import src.station_adapter as module
    import src.station_process_lock as locking

    store = mock.Mock()
    usb = mock.Mock()
    monkeypatch.setattr(module, "parse_args", lambda: cli_arguments(tmp_path / "station.sqlite3"))
    monkeypatch.setattr(module, "StationJobStore", store)
    monkeypatch.setattr(module, "run_serial_forever", usb)
    monkeypatch.setattr(locking.os, "open", mock.Mock(side_effect=PermissionError("synthetic denial")))
    assert module.main() == 1
    store.assert_not_called()
    usb.assert_not_called()


@pytest.mark.parametrize("phase", ["store", "usb"])
def test_cli_exception_releases_process_lock(tmp_path, monkeypatch, phase):
    import src.station_adapter as module

    database = tmp_path / "station.sqlite3"
    monkeypatch.setattr(module, "parse_args", lambda: cli_arguments(database))

    def fail(*args):
        assert probe(database) == 7
        raise RuntimeError("synthetic startup/shutdown failure")

    monkeypatch.setattr(module, "StationJobStore" if phase == "store" else "run_serial_forever", fail)
    with pytest.raises(RuntimeError, match="synthetic"):
        module.main()
    assert probe(database) == 0


@pytest.mark.parametrize("failure", [False, True])
def test_windows_backend_locks_byte_zero_nonblocking_and_closes_descriptor(tmp_path, monkeypatch, failure):
    """API fault injection only; real Windows OS locking needs a Windows run."""
    import src.station_process_lock as module

    calls = []

    def windows_lock(fd, mode, count):
        calls.append(fd)
        assert mode == 123 and count == 1 and os.lseek(fd, 0, os.SEEK_CUR) == 0
        assert not os.get_inheritable(fd)
        if failure:
            raise OSError("synthetic Windows lock contention")

    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(LK_NBLCK=123, locking=windows_lock))
    monkeypatch.setattr(module, "os", SimpleNamespace(
        name="nt", path=os.path, open=os.open, close=os.close, lseek=os.lseek,
        O_RDWR=os.O_RDWR, O_CREAT=os.O_CREAT, SEEK_SET=os.SEEK_SET,
    ))
    lock = StationProcessLock(tmp_path / "station.sqlite3")
    if failure:
        with pytest.raises(StationLockError):
            lock.__enter__()
    else:
        with lock:
            assert lock._fd == calls[0]
    assert len(calls) == 1 and lock._fd is None
    with pytest.raises(OSError):
        os.fstat(calls[0])
