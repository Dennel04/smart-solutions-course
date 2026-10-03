from __future__ import annotations

import sys
import unittest
from pathlib import Path

LAB1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB1_ROOT / "src"))

from mg400_client import MG400Client, MG400Error


class FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.body


class FakeSession:
    def __init__(self, bodies: list[dict[str, object]]) -> None:
        self.bodies = list(bodies)
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        return FakeResponse(self.bodies.pop(0))


MOVE_OK = {"ok": True, "clamped": {"x": 10.0, "y": 20.0, "z": 30.0, "r": 40.0}}


def status(pose: list[float], **overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "connected": True,
        "enabled": True,
        "error": False,
        "fault_kind": None,
        "fault_label": None,
        "pose": pose,
        "feedback_ok": True,
        "servo_active": True,
        "link_error": None,
        "servo_error": None,
        "stalled": False,
    }
    result.update(overrides)
    return result


class MG400ClientTests(unittest.TestCase):
    def test_realistic_status_without_ok_passes_contract_and_safety_gate(self) -> None:
        realistic = status([250.0, 0.0, 50.0, 0.0])
        realistic.update(robot_mode=5, mode_name="ENABLED (idle)")
        session = FakeSession([realistic])
        client = MG400Client(session=session)

        received = client.get_status()
        client.require_safe_status(received)

        self.assertNotIn("ok", received)
        self.assertEqual(client.pose_from_status(received), (250.0, 0.0, 50.0, 0.0))

    def test_explicit_false_status_ok_is_rejected(self) -> None:
        session = FakeSession([status([250.0, 0.0, 50.0, 0.0], ok=False)])
        client = MG400Client(session=session)
        with self.assertRaisesRegex(MG400Error, "ok was not true"):
            client.get_status()

    def test_move_and_wait_polls_until_target_pose(self) -> None:
        session = FakeSession(
            [
                MOVE_OK,
                status([0.0, 0.0, 0.0, 0.0]),
                status([10.0, 20.0, 30.0, 40.0]),
            ]
        )
        clock = iter([0.0, 0.1]).__next__
        client = MG400Client(
            session=session, monotonic=clock, sleep=lambda _: None
        )

        result = client.move_and_wait(10, 20, 30, 40, timeout=1)

        self.assertEqual(result["pose"], [10.0, 20.0, 30.0, 40.0])
        self.assertEqual(
            [call[1].rsplit("/api", 1)[-1] for call in session.calls],
            ["/move", "/status", "/status"],
        )
        self.assertTrue(all(call[2]["timeout"] == 2.0 for call in session.calls))

    def test_move_timeout_stops_and_raises(self) -> None:
        session = FakeSession(
            [
                MOVE_OK,
                status([0.0, 0.0, 0.0, 0.0]),
                {"ok": True},
            ]
        )
        clock = iter([0.0, 2.0]).__next__
        client = MG400Client(
            session=session, monotonic=clock, sleep=lambda _: None
        )

        with self.assertRaisesRegex(MG400Error, "timed out"):
            client.move_and_wait(10, 20, 30, 40, timeout=1)

        self.assertEqual(session.calls[-1][1], "http://127.0.0.1:8000/api/stop")

    def test_unsafe_status_interrupts_wait(self) -> None:
        session = FakeSession(
            [MOVE_OK, status([0.0, 0.0, 0.0, 0.0], stalled=True)]
        )
        client = MG400Client(session=session, sleep=lambda _: None)
        with self.assertRaisesRegex(MG400Error, "stalled"):
            client.move_and_wait(10, 20, 30, 40)

    def test_post_still_requires_true_ok(self) -> None:
        session = FakeSession([{}])
        client = MG400Client(session=session)
        with self.assertRaisesRegex(MG400Error, "ok was not true"):
            client.set_speed(20)

    def test_servo_inactive_blocks_motion(self) -> None:
        with self.assertRaisesRegex(MG400Error, "servo follower"):
            MG400Client.require_safe_status(
                status([250.0, 0.0, 50.0, 0.0], servo_active=False)
            )

    def test_clamped_move_aborts_before_status_poll(self) -> None:
        session = FakeSession(
            [{"ok": True, "clamped": {"x": 9.0, "y": 20.0, "z": 30.0, "r": 40.0}}]
        )
        client = MG400Client(session=session)
        with self.assertRaisesRegex(MG400Error, "target was clamped"):
            client.move_and_wait(10.0, 20.0, 30.0, 40.0)
        self.assertEqual(len(session.calls), 1)


class MissingRouteResponse(FakeResponse):
    status_code = 404


class CheckPoseTests(unittest.TestCase):
    def test_reachable_flag_is_returned(self) -> None:
        session = FakeSession([{"ok": True, "reachable": False, "reason": "J3"}])
        client = MG400Client(session=session)  # type: ignore[arg-type]
        self.assertFalse(client.check_pose(300, 0, -100))
        method, url, kwargs = session.calls[0]
        self.assertEqual((method, url), ("POST", "http://127.0.0.1:8000/api/check"))
        self.assertEqual(kwargs["json"], {"x": 300, "y": 0, "z": -100})

    def test_upstream_server_without_check_returns_none(self) -> None:
        session = FakeSession([])
        session.request = lambda *a, **k: MissingRouteResponse({})  # type: ignore[method-assign]
        self.assertIsNone(MG400Client(session=session).check_pose(300, 0, -100))  # type: ignore[arg-type]

    def test_malformed_check_reply_is_an_error(self) -> None:
        client = MG400Client(session=FakeSession([{"ok": True}]))  # type: ignore[arg-type]
        with self.assertRaises(MG400Error):
            client.check_pose(300, 0, -100)


if __name__ == "__main__":
    unittest.main()
