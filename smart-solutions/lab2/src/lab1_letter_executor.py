"""One letter submission followed by read-only status queries to local Lab 1.

The caller owns SQLite idempotency, interlock and local execution permission.
This module does not enable a robot or release any interlock. The supplied
Session-compatible transport is owned/configured by this executor.
"""

from __future__ import annotations

import math
import time
from typing import Any, Callable, Protocol
from urllib.parse import urlsplit

from requests.adapters import HTTPAdapter

from .executor import ExecutionOutcome
from .models import lab1_letter_identity


class HTTPTransport(Protocol):
    trust_env: bool
    proxies: dict
    auth: Any

    def mount(self, prefix: str, adapter: HTTPAdapter) -> None: ...
    def request(self, method: str, url: str, **kwargs: Any) -> Any: ...


class Lab1LetterExecutor:
    def __init__(
        self, base_url: str, *, transport: HTTPTransport,
        request_timeout: float = 2.0, completion_timeout: float = 120.0,
        poll_interval: float = 0.25,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not isinstance(base_url, str):
            raise ValueError("Lab 1 endpoint must be a loopback URL with an explicit port")
        parsed = urlsplit(base_url)
        port = parsed.port
        if port is None or not 1 <= port <= 65535 or base_url not in (
            f"http://127.0.0.1:{port}", f"http://127.0.0.1:{port}/",
        ):
            raise ValueError("Lab 1 endpoint must be http://127.0.0.1:<port>")
        if any(not math.isfinite(value) or value <= 0
               for value in (request_timeout, completion_timeout, poll_interval)):
            raise ValueError("timeouts and polling interval must be finite and positive")
        self.base_url = f"http://127.0.0.1:{port}"
        self.transport = transport
        transport.trust_env = False
        transport.proxies.clear()
        transport.auth = None
        transport.mount("http://", HTTPAdapter(max_retries=0))
        self.request_timeout = request_timeout
        self.completion_timeout = completion_timeout
        self.poll_interval = poll_interval
        self.monotonic = monotonic
        self.sleep = sleep

    @property
    def ready(self) -> bool:
        # Configuration readiness only, never robot permission or safety proof.
        return True

    def _json(self, method: str, path: str, status: int, timeout: float, **kwargs: Any) -> dict:
        response = self.transport.request(
            method, self.base_url + path, timeout=timeout, allow_redirects=False,
            proxies={"http": None, "https": None, "all": None}, **kwargs,
        )
        try:
            if type(response.status_code) is not int or response.status_code != status:
                raise ValueError("unexpected Lab 1 HTTP status")
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("Lab 1 response must be a JSON object")
            return body
        finally:
            response.close()

    def execute_letter(
        self, letter: str, job_id: str, *, session: str, seq: int,
        atom_sent_ms: int | None,
    ) -> ExecutionOutcome:
        try:
            expected = lab1_letter_identity(job_id)
            if (type(session) is not str or type(seq) is not int or (session, seq) != expected
                    or not isinstance(letter, str) or len(letter) != 1 or not "A" <= letter <= "Z"):
                raise ValueError("letter identity was not prepared before execution")
            if atom_sent_ms is not None and (type(atom_sent_ms) is not int or atom_sent_ms < 0):
                raise ValueError("invalid Atom timestamp")
            start = self.monotonic()
            deadline = start + self.completion_timeout

            def remaining() -> float:
                now = self.monotonic()
                if not math.isfinite(now) or not math.isfinite(deadline) or now < start or now >= deadline:
                    raise TimeoutError("Lab 1 completion was not confirmed within the deadline")
                return deadline - now

            accepted = self._json(
                "POST", "/api/letter", 202, min(self.request_timeout, remaining()),
                json={"letter": letter, "session": session, "seq": seq, "atom_sent_ms": atom_sent_ms},
            )
            remaining()
            if not (accepted.get("accepted") is True and accepted.get("duplicate") is False
                    and accepted.get("dry_run") is False and accepted.get("robot_started") is True
                    and type(accepted.get("letter")) is str and accepted["letter"] == letter
                    and type(accepted.get("seq")) is int and accepted["seq"] == seq):
                raise ValueError("Lab 1 did not acknowledge the submitted letter")
            while True:
                status = self._json(
                    "GET", "/api/letter/status", 200, min(self.request_timeout, remaining()),
                    params={"session": session, "seq": seq},
                )
                remaining()
                if not (status.get("ok") is True and status.get("execution_mode") == "execute"
                        and status.get("dry_run") is False
                        and type(status.get("session")) is str and status["session"] == session
                        and type(status.get("seq")) is int and status["seq"] == seq):
                    raise ValueError("Lab 1 status does not match the submitted execution")
                state = status.get("execution_status")
                if state == "failed":
                    return ExecutionOutcome.refused("execution_failed")
                if status.get("error") is not None:
                    raise ValueError("Lab 1 status contains an error")
                if state == "completed":
                    return ExecutionOutcome.done(completion_confirmed=True)
                if state not in ("preflight", "started"):
                    raise ValueError("unknown Lab 1 execution status")
                self.sleep(min(self.poll_interval, remaining()))
        except Exception:
            # No exception text or response body crosses the Atom boundary.
            # The future adapter must retain its interlock for this outcome.
            return ExecutionOutcome.refused("execution_failed")
