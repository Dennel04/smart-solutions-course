from datetime import datetime, timedelta, timezone
import base64
from pathlib import Path
import sys

import pytest

LAB2_ROOT = Path(__file__).resolve().parents[1]
if str(LAB2_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB2_ROOT))

from server.app import create_app


class FakeClock:
    def __init__(self):
        self.value = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def app(tmp_path, clock):
    return create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "test.sqlite3"),
            "ATOM_API_KEY": "test-atom-key",
            "USER_USERNAME": "test-user",
            "USER_PASSWORD": "test-user-password",
            "DEFAULT_TTL_SECONDS": 60,
            "MAX_TTL_SECONDS": 3600,
            "ATOM_STALE_SECONDS": 10,
            "ATOM_OFFLINE_SECONDS": 30,
        },
        clock=clock,
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user_headers():
    value = base64.b64encode(b"test-user:test-user-password").decode("ascii")
    return {"Authorization": "Basic " + value}


@pytest.fixture
def atom_headers():
    return {"Authorization": "Bearer test-atom-key"}


@pytest.fixture
def valid_poll():
    return {
        "device_id": "test-atom",
        "poll_interval_ms": 1000,
        "atom_uptime_ms": 1234,
        "station": {"reachable": True, "robot_state": "mock_only"},
    }


@pytest.fixture
def create_letter(client, user_headers):
    def create(letter="A", ttl_seconds=60, extra=None):
        payload = {"job": "letter", "arg": {"letter": letter}, "ttl_seconds": ttl_seconds}
        if extra:
            payload.update(extra)
        return client.post("/api/jobs", headers=user_headers, json=payload)

    return create
