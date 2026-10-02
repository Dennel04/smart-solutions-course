from __future__ import annotations

import csv
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

LAB1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB1_ROOT / "src"))

import station
from letter_paths import DEFAULT_LETTERS_PATH, load_letter_paths
from mg400_client import MG400Client


class StationDryRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        log_path = Path(self.temporary_directory.name) / "letter_events.csv"
        station.CONFIG = station.Config(
            log_path=log_path,
            letters_path=DEFAULT_LETTERS_PATH,
            dry_run=True,
        )
        station.LETTER_PATHS = load_letter_paths(DEFAULT_LETTERS_PATH)
        station.LAST_SEQ.clear()
        station.EXECUTION_EVENTS.clear()
        station.MG400_CLIENT_FACTORY = mock.Mock(side_effect=AssertionError("MG400 called"))
        self.addCleanup(setattr, station, "MG400_CLIENT_FACTORY", MG400Client)
        self.client = station.app.test_client()
        self.log_path = log_path

    @staticmethod
    def payload(letter: str, session: str, seq: int) -> dict[str, object]:
        return {
            "letter": letter,
            "session": session,
            "seq": seq,
            "atom_sent_ms": 100,
        }

    def test_a_l_n_are_accepted_in_dry_run(self) -> None:
        with mock.patch.object(socket, "create_connection") as network_call:
            with mock.patch.object(station.threading, "Thread") as worker:
                for seq, letter in enumerate(("A", "L", "N"), start=1):
                    response = self.client.post(
                        "/api/letter",
                        json=self.payload(letter, "configured", seq),
                    )
                    self.assertEqual(response.status_code, 202)
                    self.assertFalse(response.get_json()["robot_started"])
                    self.assertTrue(response.get_json()["dry_run"])
                network_call.assert_not_called()
                worker.assert_not_called()
        station.MG400_CLIENT_FACTORY.assert_not_called()

        with self.log_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row["status"] for row in rows], ["accepted_dry_run"] * 3)
        self.assertTrue(all(row["robot_command_monotonic_ns"] == "" for row in rows))

    def test_unconfigured_letter_returns_422_without_consuming_sequence(self) -> None:
        missing = self.client.post(
            "/api/letter",
            json=self.payload("Z", "unsupported", 1),
        )
        self.assertEqual(missing.status_code, 422)
        self.assertFalse(missing.get_json()["ok"])
        self.assertFalse(missing.get_json()["robot_started"])

        accepted = self.client.post(
            "/api/letter",
            json=self.payload("A", "unsupported", 1),
        )
        self.assertEqual(accepted.status_code, 202)

    def test_duplicate_keeps_existing_ack_semantics(self) -> None:
        payload = self.payload("A", "duplicate", 7)
        first = self.client.post("/api/letter", json=payload)
        duplicate = self.client.post("/api/letter", json=payload)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.get_json()["duplicate"])

    def test_default_cli_mode_is_dry_run(self) -> None:
        with mock.patch.object(sys, "argv", ["station.py"]):
            args = station.parse_args()
        self.assertFalse(args.execute)

    def test_health_reports_mode_and_incomplete_calibration_without_network(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["execution_mode"], "dry-run")
        self.assertFalse(body["calibration_complete"])
        station.MG400_CLIENT_FACTORY.assert_not_called()


if __name__ == "__main__":
    unittest.main()
