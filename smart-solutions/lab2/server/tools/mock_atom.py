"""Mock the future Atom -> local station -> post-office result chain."""

import argparse
import os
import sys
import time

import requests


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:5001")
    parser.add_argument("--poll-delay", type=float, default=0.0)
    parser.add_argument("--result-delay", type=float, default=0.0)
    parser.add_argument("--outcome", choices=("done", "refused"), default="done")
    parser.add_argument("--once", action="store_true", help="poll once and exit")
    return parser.parse_args()


def main():
    args = parse_args()
    key = os.environ.get("ATOM_API_KEY")
    if not key:
        raise SystemExit("ATOM_API_KEY is required; use the same local/dev value as the server.")
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    poll_interval = max(1, int(max(args.poll_delay, 0.001) * 1000))

    while True:
        if args.poll_delay:
            time.sleep(args.poll_delay)
        response = requests.post(
            args.server.rstrip("/") + "/api/atom/poll",
            headers=headers,
            json={
                "device_id": "local-mock-atom",
                "poll_interval_ms": poll_interval,
                "atom_uptime_ms": int(time.monotonic() * 1000),
                "station": {"reachable": True, "robot_state": "mock_only"},
            },
            timeout=5,
        )
        response.raise_for_status()
        job = response.json()["job"]
        print("poll job:", job)
        if job is not None:
            letter = job["arg"]["letter"]
            print(
                "mock local boundary: station received letter %s; no Atom or MG400 was used"
                % letter
            )
            if args.result_delay:
                time.sleep(args.result_delay)
            if args.outcome == "done":
                result_payload = {
                    "id": job["id"],
                    "status": "done",
                    "result": {"simulated": True, "letter": letter},
                }
            else:
                result_payload = {
                    "id": job["id"],
                    "status": "refused",
                    "reason": "mock_station_refused",
                }
            result = requests.post(
                args.server.rstrip("/") + "/api/atom/result",
                headers=headers,
                json=result_payload,
                timeout=5,
            )
            result.raise_for_status()
            print("result:", result.json())
        if args.once:
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.RequestException as error:
        raise SystemExit("mock Atom request failed: %s" % error)
