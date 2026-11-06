from dataclasses import dataclass
import socket
from unittest import mock

import pytest
import requests

from src.executor import ExecutionOutcome, MockLetterExecutor, MockPickPlaceExecutor
from src.lab1_letter_executor import Lab1LetterExecutor
from src.models import lab1_letter_identity


SESSION, SEQ = lab1_letter_identity("job-1")


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.now += duration


@dataclass
class Response:
    status_code: int
    body: object
    elapsed: float = 0.0
    closed: bool = False

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body

    def close(self):
        self.closed = True


class FakeHTTP:
    def __init__(self, events, clock):
        self.events = list(events)
        self.clock = clock
        self.calls = []
        self.trust_env = True
        self.proxies = {"http": "http://synthetic.invalid:1234"}
        self.auth = ("synthetic-user", "synthetic-password")
        self.adapters = {}

    def mount(self, prefix, adapter):
        self.adapters[prefix] = adapter

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        assert self.events, "unexpected additional HTTP request"
        expected_method, response = self.events.pop(0)
        assert method == expected_method
        if isinstance(response, Exception):
            raise response
        self.clock.now += response.elapsed
        return response


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    deny = mock.Mock(side_effect=AssertionError("real network is forbidden"))
    monkeypatch.setattr(requests.sessions.Session, "request", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    yield
    deny.assert_not_called()


def accepted(**changes):
    return {"accepted": True, "duplicate": False, "dry_run": False,
            "robot_started": True, "letter": "A", "seq": SEQ, **changes}


def status(state="completed", **changes):
    return {"ok": True, "execution_mode": "execute", "dry_run": False,
            "session": SESSION, "seq": SEQ, "execution_status": state,
            "error": None, **changes}


def run(events, *, fields=None, **configuration):
    clock = Clock()
    http = FakeHTTP(events, clock)
    executor = Lab1LetterExecutor("http://127.0.0.1:5000", transport=http,
                                 monotonic=clock.monotonic, sleep=clock.sleep, **configuration)
    arguments = dict(letter="A", job_id="job-1", session=SESSION, seq=SEQ, atom_sent_ms=1234)
    arguments.update(fields or {})
    result = executor.execute_letter(**arguments)
    return result, http, clock


def assert_refused(result, http):
    assert result == ExecutionOutcome.refused("execution_failed")
    assert result.completion_confirmed is False
    assert sum(method == "POST" for method, _, _ in http.calls) <= 1


def test_accepted_preflight_started_completed_has_one_post_and_confirmed_result():
    responses = [Response(202, accepted()), Response(200, status("preflight")),
                 Response(200, status("started")), Response(200, status())]
    result, http, clock = run(list(zip(("POST", "GET", "GET", "GET"), responses)))
    assert result == ExecutionOutcome.done(completion_confirmed=True)
    assert [method for method, _, _ in http.calls] == ["POST", "GET", "GET", "GET"]
    assert clock.sleeps == [0.25, 0.25]
    assert http.calls[0][2]["json"] == {"letter": "A", "session": SESSION, "seq": 0, "atom_sent_ms": 1234}
    assert all(call[2]["params"] == {"session": SESSION, "seq": 0} for call in http.calls[1:])
    assert all(response.closed for response in responses)


def test_failed_is_refusal_not_success():
    result, http, _ = run([("POST", Response(202, accepted())),
                           ("GET", Response(200, status("failed", error="synthetic failure")))])
    assert_refused(result, http)
    assert len(http.calls) == 2


@pytest.mark.parametrize("change", [
    {"accepted": False}, {"accepted": 1}, {"duplicate": True}, {"duplicate": 0},
    {"dry_run": True}, {"dry_run": 0}, {"robot_started": False}, {"robot_started": 1},
    {"letter": "L"}, {"letter": None}, {"seq": False}, {"seq": "0"}, {"seq": 1},
])
def test_bad_post_ack_never_becomes_done(change):
    result, http, _ = run([("POST", Response(202, accepted(**change)))])
    assert_refused(result, http)
    assert len(http.calls) == 1


@pytest.mark.parametrize("change", [
    {"ok": False}, {"ok": 1}, {"execution_mode": "dry-run"},
    {"dry_run": True}, {"dry_run": 0}, {"session": "post-office"}, {"session": None},
    {"seq": False}, {"seq": "0"}, {"seq": 1}, {"error": "synthetic error"},
    {"execution_status": "done"}, {"execution_status": "unknown"},
    {"execution_status": None}, {"execution_status": 1},
])
def test_invalid_or_uncorrelated_status_never_becomes_done(change):
    result, http, _ = run([("POST", Response(202, accepted())),
                           ("GET", Response(200, status(**change)))])
    assert_refused(result, http)
    assert len(http.calls) == 2


@pytest.mark.parametrize("method", ["POST", "GET"])
@pytest.mark.parametrize("response", [
    Response(404, {}), Response(503, {}), Response(302, {}), Response(307, {}),
    Response(200, ValueError("malformed JSON")), Response(200, []),
    requests.Timeout("synthetic timeout"), requests.ConnectionError("synthetic disconnect"),
])
def test_http_and_transport_errors_never_retry_post(method, response):
    if method == "POST" and isinstance(response, Response) and response.status_code == 200:
        response = Response(202, response.body)
    events = [(method, response)]
    if method == "GET":
        events.insert(0, ("POST", Response(202, accepted())))
    result, http, _ = run(events)
    assert_refused(result, http)
    assert len(http.calls) == (1 if method == "POST" else 2)


def test_http_200_post_is_not_acceptance_or_completion():
    result, http, _ = run([("POST", Response(200, accepted()))])
    assert_refused(result, http)
    assert len(http.calls) == 1


def test_total_timeout_stops_status_queries_without_resubmission():
    events = [("POST", Response(202, accepted()))] + [("GET", Response(200, status("started"))) for _ in range(4)]
    result, http, clock = run(events, completion_timeout=1.0)
    assert_refused(result, http)
    assert len(http.calls) == 5 and clock.now == 1.0
    assert all(0 < call[2]["timeout"] <= 1.0 for call in http.calls)


@pytest.mark.parametrize("method", ["POST", "GET"])
def test_response_after_deadline_cannot_confirm_completion(method):
    events = [("POST", Response(202, accepted(), elapsed=2.0))] if method == "POST" else [
        ("POST", Response(202, accepted())), ("GET", Response(200, status(), elapsed=2.0))]
    result, http, _ = run(events, completion_timeout=1.0)
    assert_refused(result, http)


@pytest.mark.parametrize("url", [
    "http://localhost:5000", "https://127.0.0.1:5000", "http://127.0.0.2:5000",
    "http://192.0.2.1:5000", "http://127.0.0.1", "http://127.0.0.1:0",
    "http://127.0.0.1:65536", "http://user:pass@127.0.0.1:5000",
    "http://127.0.0.1:5000/path", "http://127.0.0.1:5000?x=1",
    "http://127.0.0.1:5000#fragment", "http://127.0.0.1:5000\n", "http://[::1]:5000",
])
def test_only_explicit_ipv4_loopback_endpoint_is_accepted(url):
    http = FakeHTTP([], Clock())
    with pytest.raises(ValueError):
        Lab1LetterExecutor(url, transport=http)
    assert http.calls == []


def test_proxy_retries_and_redirects_are_disabled():
    result, http, _ = run([("POST", Response(202, accepted())), ("GET", Response(200, status()))])
    assert result.completion_confirmed is True
    assert http.trust_env is False and http.proxies == {} and http.auth is None
    assert http.adapters["http://"].max_retries.total == 0
    for _, url, options in http.calls:
        assert url in ("http://127.0.0.1:5000/api/letter", "http://127.0.0.1:5000/api/letter/status")
        assert options["allow_redirects"] is False
        assert options["proxies"] == {"http": None, "https": None, "all": None}


@pytest.mark.parametrize("field", ["request_timeout", "completion_timeout", "poll_interval"])
@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_wait_configuration_is_bounded(field, value):
    with pytest.raises(ValueError):
        Lab1LetterExecutor("http://127.0.0.1:5000", transport=FakeHTTP([], Clock()), **{field: value})


@pytest.mark.parametrize("fields", [{"session": "post-office"}, {"seq": False}, {"job_id": "bad/id"},
                                    {"letter": "AB"}, {"atom_sent_ms": True}])
def test_unprepared_identity_or_bad_input_never_posts(fields):
    result, http, _ = run([], fields=fields)
    assert_refused(result, http)
    assert http.calls == []


def test_response_and_exception_text_are_not_printed(capsys):
    result, http, _ = run([("POST", requests.ConnectionError("synthetic private response marker"))])
    assert_refused(result, http)
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_mock_success_is_not_confirmed_physical_completion():
    arguments = dict(job_id="job-1", session=SESSION, seq=0, atom_sent_ms=1)
    assert MockLetterExecutor().execute_letter("A", **arguments) == ExecutionOutcome.done()
    assert MockPickPlaceExecutor().execute_pick_place("source_to_finished", **arguments) == ExecutionOutcome.done()
    assert ExecutionOutcome.done().completion_confirmed is False
    with pytest.raises(ValueError):
        ExecutionOutcome("refused", "execution_failed", completion_confirmed=True)
