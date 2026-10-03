"""Build docs/latency.csv from data/letter_events.csv (Lab 1, part 3).

Three timestamps per press:
  atom_sent_ms                     Atom millis() when the long press sent the letter
  station_received_monotonic_ns    station clock when the letter arrived
  robot_command_monotonic_ns       station clock when the first move went to the robot

The Atom and the PC have separate clocks, so the Atom -> station hop is measured
relative to the fastest press of the session: offset = min(station - atom) is
taken as "0 ms", every other press shows how much slower it was. The
station -> robot hop is on one clock and is absolute.

    python tools/latency_report.py [--session <id>] [--after-seq N] [--last 30]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--events", type=Path, default=LAB / "data" / "letter_events.csv")
    p.add_argument("--out", type=Path, default=LAB / "docs" / "latency.csv")
    p.add_argument("--session", help="Atom session id (default: the last one in the file)")
    p.add_argument("--last", type=int, default=30, help="use the last N presses of the session")
    p.add_argument("--after-seq", type=int, default=None,
                   help="only presses with a larger Atom seq (start of the measured run)")
    a = p.parse_args()

    with a.events.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["atom_sent_ms"] and r["station_received_monotonic_ns"]]
    session = a.session or rows[-1]["session"]
    rows = [r for r in rows if r["session"] == session
            and (a.after_seq is None or int(r["seq"]) > a.after_seq)][-a.last:]
    if not rows:
        raise SystemExit(f"no presses for session {session}")

    raw = [int(r["station_received_monotonic_ns"]) / 1e6 - int(r["atom_sent_ms"]) for r in rows]
    offset = min(raw)
    out = []
    for n, (r, d) in enumerate(zip(rows, raw), 1):
        cmd = r["robot_command_monotonic_ns"]
        to_robot = (int(cmd) - int(r["station_received_monotonic_ns"])) / 1e6 if cmd else None
        out.append({
            "katse_nr": n,
            "letter": r["letter"],
            "atom_sent_ts": r["atom_sent_ms"],
            "station_received_ts": r["station_received_iso"],
            "station_robot_command_ts": cmd,
            "atom_to_station_ms": f"{d - offset:.1f}",
            "station_to_robot_ms": f"{to_robot:.1f}" if to_robot is not None else "",
            "note": f"session {session}, seq {r['seq']}, {r['status']}" + (f"; {r['note']}" if r["note"] else ""),
        })

    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    def stats(key: str) -> str:
        v = [float(o[key]) for o in out if o[key]]
        return f"n={len(v)} keskmine {sum(v) / len(v):.1f} ms, max {max(v):.1f} ms" if v else "n=0"

    print(f"{len(out)} presses -> {a.out}")
    print(f"Atom -> jaam  (suhteline, kiireim = 0): {stats('atom_to_station_ms')}")
    print(f"jaam -> robot (absoluutne):            {stats('station_to_robot_ms')}")


if __name__ == "__main__":
    main()
