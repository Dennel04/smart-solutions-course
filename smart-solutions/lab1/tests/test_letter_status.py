from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest import mock

LAB1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB1_ROOT / "src"))

import station


class LetterStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        for patch in (
            mock.patch.object(station, "CONFIG", replace(station.CONFIG, dry_run=False)),
            mock.patch.dict(station.EXECUTION_EVENTS, {}, clear=True),
            mock.patch.dict(station.LAST_SEQ, {}, clear=True),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.guards = []
        for name in ("MG400_CLIENT_FACTORY", "_execute_plan", "_run_execution", "append_log"):
            patch = mock.patch.object(station, name, side_effect=AssertionError(name + " called"))
            self.guards.append(patch.start())
            self.addCleanup(patch.stop)
        for target in ("station.threading.Thread", "requests.sessions.Session.request", "socket.create_connection"):
            patch = mock.patch(target, side_effect=AssertionError(target + " called"))
            self.guards.append(patch.start())
            self.addCleanup(patch.stop)
        self.client = station.app.test_client()

    def tearDown(self) -> None:
        for guard in self.guards:
            guard.assert_not_called()

    def get_status(self, query=None):
        if query is None:
            query = {"session": "post-office", "seq": "1"}
        before = {key: (value.state, value.error) for key, value in station.EXECUTION_EVENTS.items()}
        sequences = dict(station.LAST_SEQ)
        response = self.client.get("/api/letter/status", query_string=query)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(before, {key: (value.state, value.error) for key, value in station.EXECUTION_EVENTS.items()})
        self.assertEqual(sequences, station.LAST_SEQ)
        return response

    def test_started_then_completed_reads_worker_state(self) -> None:
        record = station.ExecutionRecord("started")
        with station.SEQ_LOCK:
            station.EXECUTION_EVENTS[("post-office", 1)] = record
        started = self.get_status()
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.get_json(), {
            "ok": True, "session": "post-office", "seq": 1,
            "execution_status": "started", "error": None,
            "execution_mode": "execute", "dry_run": False,
        })
        with station.SEQ_LOCK:
            record.state = "completed"
        completed = self.get_status()
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.get_json()["execution_status"], "completed")

    def test_failed_preserves_error(self) -> None:
        station.EXECUTION_EVENTS[("post-office", 1)] = station.ExecutionRecord("failed", "synthetic failure")
        response = self.get_status()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["execution_status"], "failed")
        self.assertEqual(response.get_json()["error"], "synthetic failure")

    def test_preflight_is_not_completed(self) -> None:
        station.EXECUTION_EVENTS[("post-office", 1)] = station.ExecutionRecord("preflight")
        response = self.get_status()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["execution_status"], "preflight")

    def test_unknown_and_restart_do_not_reconstruct_execution(self) -> None:
        station.LAST_SEQ["post-office"] = 1
        for existed in (False, True):
            with self.subTest(previous_record=existed):
                if existed:
                    station.EXECUTION_EVENTS[("post-office", 1)] = station.ExecutionRecord("completed")
                    station.EXECUTION_EVENTS.clear()  # Simulate process restart.
                response = self.get_status()
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.get_json()["error"], "unknown letter execution")
                self.assertNotIn("execution_status", response.get_json())

    def test_dry_run_never_exposes_physical_success(self) -> None:
        station.CONFIG = replace(station.CONFIG, dry_run=True)
        station.EXECUTION_EVENTS[("post-office", 1)] = station.ExecutionRecord("completed")
        response = self.get_status()
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.get_json()["ok"])
        self.assertTrue(response.get_json()["dry_run"])
        self.assertEqual(response.get_json()["execution_mode"], "dry-run")
        self.assertNotIn("execution_status", response.get_json())

    def test_internal_text_record_is_not_a_letter_result(self) -> None:
        station.EXECUTION_EVENTS[("text", 1)] = station.ExecutionRecord("completed")
        for session in ("text", " text "):
            with self.subTest(session=session):
                response = self.get_status({"session": session, "seq": "1"})
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("execution_status", response.get_json())
        self.assertEqual(self.client.get("/api/text/1").get_json()["execution_status"], "completed")

    def test_letter_post_rejects_reserved_text_session_before_execution(self) -> None:
        station.EXECUTION_EVENTS[("text", 1)] = station.ExecutionRecord("completed")
        before = dict(station.EXECUTION_EVENTS)
        for session in ("text", " text "):
            response = self.client.post("/api/letter", json={"letter": "A", "session": session, "seq": 1})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json()["error"], "session 'text' is reserved for internal text jobs")
        self.assertEqual(station.EXECUTION_EVENTS, before)
        self.assertEqual(station.LAST_SEQ, {})

    def test_invalid_session_is_rejected(self) -> None:
        for query in ({"seq": "1"}, {"session": "", "seq": "1"},
                      {"session": "  ", "seq": "1"}, {"session": "a" * 65, "seq": "1"},
                      [("session", "a"), ("session", "b"), ("seq", "1")]):
            with self.subTest(query=query):
                self.assertEqual(self.get_status(query).status_code, 400)

    def test_invalid_seq_is_rejected(self) -> None:
        for seq in (None, "", "-1", "1.0", "true", "+1", " 1", "١"):
            query = {"session": "post-office"}
            if seq is not None:
                query["seq"] = seq
            with self.subTest(seq=seq):
                self.assertEqual(self.get_status(query).status_code, 400)
        self.assertEqual(self.get_status([("session", "a"), ("seq", "1"), ("seq", "2")]).status_code, 400)

    def test_zero_and_trimmed_session_match_canonical_key(self) -> None:
        station.EXECUTION_EVENTS[("post-office", 0)] = station.ExecutionRecord("started")
        response = self.get_status({"session": " post-office ", "seq": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["session"], "post-office")
        self.assertEqual(response.get_json()["seq"], 0)


if __name__ == "__main__":
    unittest.main()
