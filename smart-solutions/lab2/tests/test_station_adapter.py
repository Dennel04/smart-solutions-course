import json

from src.e2e_demo import run_demo
from src.executor import MockLetterExecutor
from src.models import AtomLetterJob, StationResult, parse_atom_message
from src.serial_transport import process_lines
from src.station_adapter import StationAdapter
from src.station_store import StationJobStore


def atom_payload(job_id="job-1", letter="A", session="post-office", seq=1, **extra):
    payload = {
        "letter": letter,
        "session": session,
        "seq": seq,
        "atom_sent_ms": 1234,
        "job_id": job_id,
    }
    payload.update(extra)
    return payload


def decode(line):
    return json.loads(line)["post_office_result"]


def make_adapter(tmp_path, *, executor=None, enabled=True):
    selected = executor or MockLetterExecutor()
    return (
        StationAdapter(
            StationJobStore(tmp_path / "station.sqlite3"),
            executor=selected,
            local_execution_enabled=enabled,
        ),
        selected,
    )


def test_valid_letter_message_is_accepted(tmp_path):
    adapter, executor = make_adapter(tmp_path)
    result = decode(adapter.handle_line(json.dumps(atom_payload())))
    assert result == {"id": "job-1", "status": "done"}
    assert [job.letter for job in executor.calls] == ["A"]


def test_invalid_json_is_refused(tmp_path):
    adapter, _ = make_adapter(tmp_path)
    result = decode(adapter.handle_line("{not-json"))
    assert result == {"id": "", "status": "refused", "reason": "invalid_message"}


def test_missing_job_id_is_refused(tmp_path):
    adapter, _ = make_adapter(tmp_path)
    payload = atom_payload()
    payload.pop("job_id")
    result = decode(adapter.handle_line(json.dumps(payload)))
    assert result["status"] == "refused"
    assert result["reason"] == "invalid_message"


def test_invalid_letter_is_refused(tmp_path):
    adapter, executor = make_adapter(tmp_path)
    result = decode(adapter.handle_line(json.dumps(atom_payload(letter="AB"))))
    assert result == {"id": "job-1", "status": "refused", "reason": "invalid_letter"}
    assert executor.calls == []


def test_direct_motion_fields_are_refused(tmp_path):
    adapter, executor = make_adapter(tmp_path)
    result = decode(adapter.handle_line(json.dumps(atom_payload(x=10, speed=20))))
    assert result == {"id": "job-1", "status": "refused", "reason": "invalid_message"}
    assert executor.calls == []


def test_duplicate_job_id_returns_same_terminal_result(tmp_path):
    adapter, executor = make_adapter(tmp_path)
    line = json.dumps(atom_payload())
    first = adapter.handle_line(line)
    second = adapter.handle_line(line)
    assert second == first
    assert len(executor.calls) == 1


def test_conflicting_reuse_of_job_id_is_refused(tmp_path):
    adapter, executor = make_adapter(tmp_path)
    assert decode(adapter.handle_line(json.dumps(atom_payload(letter="A"))))["status"] == "done"
    conflict = decode(adapter.handle_line(json.dumps(atom_payload(letter="L"))))
    assert conflict["reason"] == "duplicate_conflict"
    assert len(executor.calls) == 1


def test_session_seq_duplicate_does_not_reexecute(tmp_path):
    adapter, executor = make_adapter(tmp_path)
    adapter.handle_line(json.dumps(atom_payload(job_id="job-1")))
    duplicate = decode(adapter.handle_line(json.dumps(atom_payload(job_id="job-2"))))
    assert duplicate == {
        "id": "job-2",
        "status": "refused",
        "reason": "duplicate_conflict",
    }
    assert len(executor.calls) == 1


def test_mock_executor_success_becomes_done(tmp_path):
    adapter, _ = make_adapter(tmp_path, executor=MockLetterExecutor())
    assert decode(adapter.handle_line(json.dumps(atom_payload())))["status"] == "done"


def test_mock_executor_refusal_is_stable(tmp_path):
    executor = MockLetterExecutor(refusals={"A": "robot_not_enabled"})
    adapter, _ = make_adapter(tmp_path, executor=executor)
    result = decode(adapter.handle_line(json.dumps(atom_payload())))
    assert result["status"] == "refused"
    assert result["reason"] == "robot_not_enabled"


def test_executor_failure_becomes_stable_refusal(tmp_path):
    adapter, _ = make_adapter(tmp_path, executor=MockLetterExecutor(failures={"A"}))
    result = decode(adapter.handle_line(json.dumps(atom_payload())))
    assert result["reason"] == "execution_failed"
    assert decode(adapter.handle_line(json.dumps(atom_payload()))) == result


def test_restart_persistence_prevents_terminal_replay(tmp_path):
    database = tmp_path / "station.sqlite3"
    first_executor = MockLetterExecutor()
    first = StationAdapter(
        StationJobStore(database), executor=first_executor, local_execution_enabled=True
    )
    line = json.dumps(atom_payload())
    expected = first.handle_line(line)

    second_executor = MockLetterExecutor()
    restarted = StationAdapter(
        StationJobStore(database), executor=second_executor, local_execution_enabled=True
    )
    assert restarted.handle_line(line) == expected
    assert len(first_executor.calls) == 1
    assert second_executor.calls == []


def test_ambiguous_in_progress_job_is_refused_after_restart(tmp_path):
    database = tmp_path / "station.sqlite3"
    job = parse_atom_message(atom_payload())
    assert StationJobStore(database).claim(job).action == "execute"

    executor = MockLetterExecutor()
    restarted = StationAdapter(
        StationJobStore(database), executor=executor, local_execution_enabled=True
    )
    result = decode(restarted.handle_line(json.dumps(atom_payload())))
    assert result["reason"] == "ambiguous_after_restart"
    assert executor.calls == []


def test_malformed_serial_line_does_not_stop_processing(tmp_path):
    adapter, executor = make_adapter(tmp_path)
    emitted = []
    process_lines(
        [b"{broken\n", (json.dumps(atom_payload()) + "\n").encode()],
        adapter,
        emit=emitted.append,
        log=lambda _: None,
    )
    assert decode(emitted[0])["reason"] == "invalid_message"
    assert decode(emitted[1])["status"] == "done"
    assert len(executor.calls) == 1


def test_default_mode_does_not_call_executor_or_mg400(tmp_path):
    executor = MockLetterExecutor()
    adapter, _ = make_adapter(tmp_path, executor=executor, enabled=False)
    result = decode(adapter.handle_line(json.dumps(atom_payload())))
    assert result["reason"] == "robot_not_enabled"
    assert executor.calls == []


def test_result_json_contains_stable_job_id(tmp_path):
    adapter, _ = make_adapter(tmp_path)
    result = decode(adapter.handle_line(json.dumps(atom_payload(job_id="stable-123"))))
    assert result["id"] == "stable-123"


def test_second_job_is_refused_while_first_is_in_progress(tmp_path):
    store = StationJobStore(tmp_path / "station.sqlite3")
    assert store.claim(parse_atom_message(atom_payload(job_id="job-1"))).action == "execute"
    adapter = StationAdapter(store, executor=MockLetterExecutor(), local_execution_enabled=True)
    result = decode(
        adapter.handle_line(json.dumps(atom_payload(job_id="job-2", session="other", seq=2)))
    )
    assert result["reason"] == "executor_busy"


def test_result_model_matches_firmware_envelope():
    line = StationResult("stable-id", "refused", "execution_failed").to_json_line()
    assert decode(line) == {
        "id": "stable-id",
        "status": "refused",
        "reason": "execution_failed",
    }


def test_end_to_end_post_office_station_demo(tmp_path):
    result = run_demo(tmp_path)
    assert result["station_result"]["id"] == result["job_id"]
    assert result["station_result"]["status"] == "done"
    assert result["server_status"] == "done"
    assert result["hardware_used"] is False
