from __future__ import annotations

import sys
import unittest
from pathlib import Path

LAB1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB1_ROOT / "src"))

import requests

from atom_bridge import LetterForwarder, letter_event, run_bridge


class FakeResponse:
    status_code = 202
    text = '{"ok":true}'


class FakeSession:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.posts: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict, timeout: float) -> FakeResponse:
        self.posts.append((url, json))
        if self.failures:
            self.failures -= 1
            raise requests.ConnectionError("station down")
        return FakeResponse()


class AtomBridgeTests(unittest.TestCase):
    def test_letter_event_validation(self) -> None:
        good = {"letter": "K", "session": "ab12", "seq": 3, "atom_sent_ms": 99}
        self.assertEqual(letter_event(good), good)
        for bad in (
            {"t": 1, "adc": 2, "p": -1.0, "mode": "off", "pump": 0},  # telemetry
            {"letter": "k", "session": "s", "seq": 1},
            {"letter": "AB", "session": "s", "seq": 1},
            {"letter": "A", "session": "", "seq": 1},
            {"letter": "A", "session": "s", "seq": True},
            {"letter": "A", "session": "s", "seq": -1},
            ["letter"],
        ):
            self.assertIsNone(letter_event(bad), bad)

    def test_bad_timestamp_is_dropped_not_the_letter(self) -> None:
        payload = letter_event({"letter": "A", "session": "s", "seq": 1, "atom_sent_ms": -5})
        self.assertEqual(payload, {"letter": "A", "session": "s", "seq": 1})

    def test_only_letter_lines_are_forwarded(self) -> None:
        session = FakeSession()
        forwarder = LetterForwarder("http://station:5000/", session=session, log=lambda _: None)
        lines = [
            b'{"t":10,"adc":2011,"p":-0.1,"mode":"off","pump":0}\n',
            b"# LETTER queue K session=ab seq=1\n",
            b'{"letter":"K","session":"ab","seq":1,"atom_sent_ms":5}\n',
            b"garbage{\n",
            b"",
        ]
        run_bridge(lines, forwarder, log=lambda _: None)
        forwarder.close()
        self.assertEqual(
            session.posts,
            [("http://station:5000/api/letter", {"letter": "K", "session": "ab", "seq": 1, "atom_sent_ms": 5})],
        )

    def test_atom_log_lines_are_printed_not_forwarded(self) -> None:
        session = FakeSession()
        forwarder = LetterForwarder("http://station:5000/", session=session, log=lambda _: None)
        printed: list[str] = []
        run_bridge([b"# portal GET http://connectivitycheck.gstatic.com/generate_204\n"], forwarder, log=printed.append)
        forwarder.close()
        self.assertEqual(session.posts, [])
        self.assertEqual(printed, ["[atom-log] portal GET http://connectivitycheck.gstatic.com/generate_204"])

    def test_network_errors_are_retried(self) -> None:
        session = FakeSession(failures=2)
        forwarder = LetterForwarder("http://s:5000", session=session, log=lambda _: None)
        forwarder.submit({"letter": "A", "session": "s", "seq": 1})
        forwarder.close()
        self.assertEqual(len(session.posts), 3)


if __name__ == "__main__":
    unittest.main()
