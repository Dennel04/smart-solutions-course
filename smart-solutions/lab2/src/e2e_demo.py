"""In-process post-office -> mock Atom -> station -> result software demo."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import tempfile

from server.app import create_app

from .executor import MockLetterExecutor
from .station_adapter import StationAdapter
from .station_store import StationJobStore


def _basic(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": "Basic " + token}


def run_demo(directory: str | Path) -> dict[str, object]:
    root = Path(directory)
    atom_key = "local-demo-placeholder-key"
    username = "demo-user"
    password = "local-demo-placeholder-password"
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(root / "post_office.sqlite3"),
            "ATOM_API_KEY": atom_key,
            "USER_USERNAME": username,
            "USER_PASSWORD": password,
        }
    )
    client = app.test_client()
    user_headers = _basic(username, password)
    atom_headers = {"Authorization": "Bearer " + atom_key}

    created_response = client.post(
        "/api/jobs",
        headers=user_headers,
        json={"job": "letter", "arg": {"letter": "A"}, "ttl_seconds": 60},
    )
    if created_response.status_code != 201:
        raise RuntimeError("demo could not create a post-office job")
    created = created_response.get_json()

    polled = client.post(
        "/api/atom/poll",
        headers=atom_headers,
        json={
            "device_id": "local-demo-atom",
            "poll_interval_ms": 1000,
            "atom_uptime_ms": 1234,
            "station": {"reachable": True, "robot_state": "mock_only"},
        },
    ).get_json()["job"]
    atom_line = json.dumps(
        {
            "letter": polled["arg"]["letter"],
            "session": "post-office",
            "seq": 1,
            "atom_sent_ms": 1234,
            "job_id": polled["id"],
        }
    )

    adapter = StationAdapter(
        StationJobStore(root / "station.sqlite3"),
        executor=MockLetterExecutor(),
        local_execution_enabled=True,
    )
    station_line = adapter.handle_line(atom_line)
    terminal = json.loads(station_line)["post_office_result"]
    result_response = client.post(
        "/api/atom/result",
        headers=atom_headers,
        json={
            "id": terminal["id"],
            "status": terminal["status"],
            **(
                {"result": {"source": "local_station_demo", "letter": polled["arg"]["letter"]}}
                if terminal["status"] == "done"
                else {"reason": terminal["reason"]}
            ),
        },
    )
    if result_response.status_code != 200:
        raise RuntimeError("demo could not return the station result")
    stored = client.get("/api/jobs/" + created["id"], headers=user_headers).get_json()
    return {
        "job_id": created["id"],
        "station_result": terminal,
        "server_status": stored["status"],
        "hardware_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", help="keep demo SQLite files in this directory")
    args = parser.parse_args()
    if args.workdir:
        result = run_demo(args.workdir)
    else:
        with tempfile.TemporaryDirectory(prefix="lab2-station-demo-") as directory:
            result = run_demo(directory)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
