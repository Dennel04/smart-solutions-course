from __future__ import annotations

import json
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
from test_robot_calibration import synthetic_document
from test_station_execute import FakeMG400Client, safe_status

PAPER = {
    "corner_x": 200.0,
    "corner_y": 105.0,
    "edge_x": 200.0,
    "edge_y": -105.0,
    "size": "A4",
    "orientation": "landscape",
    "margin_mm": 15.0,
}


class StationTextTests(unittest.TestCase):
    def configure(self, *, dry_run: bool, paper: bool = True, letter_font: str | None = None) -> None:
        root = Path(self.temporary_directory.name)
        document = synthetic_document()
        if paper:
            document["paper"] = PAPER
        calibration_path = root / "robot_calibration.json"
        calibration_path.write_text(json.dumps(document), encoding="utf-8")
        station.CONFIG = station.Config(
            log_path=root / "letter_events.csv",
            letters_path=DEFAULT_LETTERS_PATH,
            dry_run=dry_run,
            calibration_path=calibration_path,
            letter_font=letter_font,
        )

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        station.LETTER_PATHS = load_letter_paths(DEFAULT_LETTERS_PATH)
        station.LAST_SEQ.clear()
        station.EXECUTION_EVENTS.clear()
        FakeMG400Client.instances.clear()
        FakeMG400Client.next_status = safe_status()
        FakeMG400Client.trace.clear()
        FakeMG400Client.unreachable = set()
        station.MG400_CLIENT_FACTORY = FakeMG400Client
        self.addCleanup(setattr, station, "MG400_CLIENT_FACTORY", MG400Client)
        self.client = station.app.test_client()

    def wait_for_worker(self) -> None:
        self.assertTrue(station.EXECUTION_LOCK.acquire(timeout=5))
        station.EXECUTION_LOCK.release()

    def test_index_and_fonts(self) -> None:
        self.configure(dry_run=True)
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        page.close()
        fonts = self.client.get("/api/fonts").get_json()["fonts"]
        self.assertIn("futural", [f["name"] for f in fonts])

    def test_preview_returns_svg_and_never_calls_robot(self) -> None:
        self.configure(dry_run=False)
        response = self.client.post("/api/text/preview", json={"text": "TERE", "size_mm": 20})
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["reachable"])
        self.assertIn("<svg", body["svg"])
        self.assertEqual(FakeMG400Client.instances, [])

    def test_bad_request_is_422(self) -> None:
        self.configure(dry_run=True)
        response = self.client.post("/api/text/preview", json={"text": "TERE", "font": "nope"})
        self.assertEqual(response.status_code, 422)

    def test_dry_run_draw_sends_nothing(self) -> None:
        self.configure(dry_run=True)
        response = self.client.post("/api/text/draw", json={"text": "TERE", "size_mm": 20})
        body = response.get_json()
        self.assertEqual(response.status_code, 202)
        self.assertFalse(body["robot_started"])
        self.assertGreater(body["action_count"], 10)
        self.assertEqual(FakeMG400Client.instances, [])

    def test_execute_without_paper_calibration_is_refused(self) -> None:
        self.configure(dry_run=False, paper=False)
        response = self.client.post("/api/text/draw", json={"text": "TERE"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(FakeMG400Client.instances, [])

    def test_execute_draws_with_pen_heights_from_calibration(self) -> None:
        self.configure(dry_run=False)
        response = self.client.post("/api/text/draw", json={"text": "LT", "size_mm": 20})
        self.assertEqual(response.status_code, 202, response.get_json())
        job = response.get_json()["job"]
        self.wait_for_worker()
        status = self.client.get(f"/api/text/{job}").get_json()
        self.assertEqual(status["execution_status"], "completed", status)
        root = Path(self.temporary_directory.name)
        self.assertFalse((root / "letter_events.csv").exists())
        self.assertIn("executed", (root / "text_events.csv").read_text(encoding="utf-8"))
        moves = FakeMG400Client.instances[0].moves
        self.assertEqual({m[2] for m in moves}, {30.0, 25.0})  # pen_up_z, pen_down_z
        self.assertEqual(moves[0][2], 30.0)
        self.assertEqual(moves[-1][2], 30.0)
        self.assertTrue(all(m[3] == 0.0 for m in moves))

    def test_pen_moves_settle_tighter_than_xy_moves(self) -> None:
        self.configure(dry_run=False)
        tolerances: list[tuple[float, float]] = []
        original = FakeMG400Client.move_and_wait

        def recording(client, x, y, z, r, *, tolerance, timeout):
            tolerances.append((z, tolerance))
            return original(client, x, y, z, r, tolerance=tolerance, timeout=timeout)

        with mock.patch.object(FakeMG400Client, "move_and_wait", recording):
            self.client.post("/api/text/draw", json={"text": "L", "size_mm": 20})
            self.wait_for_worker()
        self.assertEqual(tolerances[0], (30.0, station.CONFIG.pen_tolerance))
        self.assertIn(station.CONFIG.move_tolerance, {t for _, t in tolerances})
        self.assertLess(station.CONFIG.pen_tolerance, station.CONFIG.move_tolerance)

    def test_execute_refuses_disabled_robot(self) -> None:
        self.configure(dry_run=False)
        FakeMG400Client.next_status = safe_status(enabled=False)
        response = self.client.post("/api/text/draw", json={"text": "LT", "size_mm": 20})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(FakeMG400Client.instances[0].moves, [])

    def test_server_joint_check_refuses_before_any_move(self) -> None:
        self.configure(dry_run=False)
        preview = self.client.post("/api/text/draw", json={"text": "L", "size_mm": 20})
        self.wait_for_worker()
        first_point = FakeMG400Client.instances[0].moves[1]
        FakeMG400Client.instances.clear()
        FakeMG400Client.unreachable = {(round(first_point[0], 2), round(first_point[1], 2), 25.0)}
        response = self.client.post("/api/text/draw", json={"text": "L", "size_mm": 20})
        self.assertEqual(preview.status_code, 202)
        self.assertEqual(response.status_code, 503)
        self.assertIn("joint limit", response.get_json()["error"])
        self.assertEqual(FakeMG400Client.instances[0].moves, [])

    def test_busy_station_rejects_second_job(self) -> None:
        self.configure(dry_run=False)
        self.assertTrue(station.EXECUTION_LOCK.acquire(blocking=False))
        try:
            response = self.client.post("/api/text/draw", json={"text": "LT"})
        finally:
            station.EXECUTION_LOCK.release()
        self.assertEqual(response.status_code, 409)

    def letter(self, letter: str, seq: int):
        return self.client.post(
            "/api/letter", json={"letter": letter, "session": "tw", "seq": seq}
        )

    def test_atom_letters_are_typed_left_to_right_on_the_sheet(self) -> None:
        self.configure(dry_run=True)
        station.LETTER_CURSOR = None
        self.assertEqual(self.letter("A", 1).status_code, 202)
        first = station.LETTER_CURSOR
        self.assertEqual(self.letter("L", 2).status_code, 202)
        second = station.LETTER_CURSOR
        assert first is not None and second is not None
        self.assertAlmostEqual(second[0] - first[0], station.CONFIG.letter_size_mm)
        self.assertEqual(second[1], first[1])
        self.client.post("/api/paper/cursor/reset")
        self.assertIsNone(station.LETTER_CURSOR)

    def test_atom_letter_on_paper_executes_in_robot_mm(self) -> None:
        self.configure(dry_run=False)
        station.LETTER_CURSOR = None
        self.assertEqual(self.letter("L", 1).status_code, 202)
        self.wait_for_worker()
        moves = FakeMG400Client.instances[0].moves
        self.assertEqual({m[2] for m in moves}, {30.0, 25.0})
        # Paper frame of this sheet: reading direction = robot -Y.
        xs = [m[0] for m in moves[1:-1]]
        self.assertTrue(all(200.0 <= x <= 430.0 for x in xs), xs)
        self.assertIn("check", FakeMG400Client.trace)

    def test_preflight_failure_does_not_move_the_cursor(self) -> None:
        self.configure(dry_run=False)
        station.LETTER_CURSOR = None
        FakeMG400Client.next_status = safe_status(enabled=False)
        self.assertEqual(self.letter("L", 1).status_code, 503)
        self.assertIsNone(station.LETTER_CURSOR)

    def test_atom_letter_falls_back_to_font(self) -> None:
        self.configure(dry_run=True, letter_font="futural")
        response = self.client.post(
            "/api/letter", json={"letter": "Z", "session": "s", "seq": 1}
        )
        self.assertEqual(response.status_code, 202)

    def test_atom_letter_without_font_fallback_is_still_422(self) -> None:
        self.configure(dry_run=True)
        response = self.client.post(
            "/api/letter", json={"letter": "Z", "session": "s", "seq": 1}
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
