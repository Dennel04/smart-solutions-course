"""Passive MG400 first-movement detector for the Lab 2 latency CSVs.

Reads only the MG400 real-time feedback port (30004, one 1440-byte packet about
every 8 ms) and never sends a command, so it can run next to the station that
drives the robot. When the arm has been still and then any actual joint angle
moves more than --threshold-deg from the resting value, it prints and appends
one event with the wall-clock time of that packet:

    first_movement_iso,first_movement_epoch_ms,joint,delta_deg,rest_ms

That time is the `robot_first_movement_timestamp` of
docs/latency_poll_*.csv and docs/control_latency_cameras.csv; the start
timestamp comes from the post-office job / user click. Resolution is one
feedback period (~8 ms) plus the time the arm needs to cover the threshold.

Usage (from smart-solutions/lab2):
    python -m src.motion_watch --out data/motion_events.csv
"""

from __future__ import annotations

import argparse
import csv
import socket
import struct
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

FEEDBACK_PORT = 30004
PACKET_SIZE = 1440
MAGIC = 0x0123456789ABCDEF
OFF_TEST_VALUE = 48
OFF_ROBOT_MODE = 24
OFF_Q_ACTUAL = 432  # 6 x double, degrees (Dobot MyType)


def parse_joints(packet: bytes) -> tuple[float, float, float, float] | None:
    """Actual J1..J4 in degrees, or None when the packet is misaligned."""
    if len(packet) < PACKET_SIZE:
        return None
    if struct.unpack_from("<Q", packet, OFF_TEST_VALUE)[0] != MAGIC:
        return None
    return struct.unpack_from("<4d", packet, OFF_Q_ACTUAL)


@dataclass
class MotionDetector:
    """Rest → first-movement edge detector on actual joint angles."""

    threshold_deg: float = 0.05
    rest_s: float = 0.3

    def __post_init__(self) -> None:
        self.rest_joints: tuple[float, ...] | None = None
        self.last_joints: tuple[float, ...] | None = None
        self.still_since: float | None = None
        self.moving = True  # wait for a rest period before the first event

    def update(self, t: float, joints: tuple[float, ...]):
        """Feed one sample; return (joint_index, delta_deg, rest_ms) on a movement edge."""
        event = None
        if self.last_joints is None:
            self.last_joints, self.still_since = joints, t
            return None
        step = max(abs(a - b) for a, b in zip(joints, self.last_joints))
        self.last_joints = joints
        if self.moving:
            if step < self.threshold_deg / 10:
                if self.still_since is None:
                    self.still_since = t
                if t - self.still_since >= self.rest_s:
                    self.moving, self.rest_joints = False, joints
            else:
                self.still_since = None
            return None
        deltas = [abs(a - b) for a, b in zip(joints, self.rest_joints)]
        index = max(range(len(deltas)), key=deltas.__getitem__)
        if deltas[index] > self.threshold_deg:
            event = (index + 1, deltas[index], (t - self.still_since) * 1000.0)
            self.moving, self.still_since = True, None
        return event


def read_packets(sock: socket.socket):
    buffer = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("feedback port closed")
        t = time.time()
        buffer += chunk
        while len(buffer) >= PACKET_SIZE:
            joints = parse_joints(buffer[:PACKET_SIZE])
            if joints is None:  # resynchronise on the magic value
                at = buffer.find(struct.pack("<Q", MAGIC), 1)
                buffer = buffer[at - OFF_TEST_VALUE:] if at >= OFF_TEST_VALUE else b""
                continue
            buffer = buffer[PACKET_SIZE:]
            yield t, joints


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--robot-ip", default="192.168.1.6")
    parser.add_argument("--threshold-deg", type=float, default=0.05)
    parser.add_argument("--rest-s", type=float, default=0.3)
    parser.add_argument("--out", type=Path, help="append events to this CSV")
    parser.add_argument("--duration-s", type=float, default=0.0, help="0 = until Ctrl+C")
    args = parser.parse_args(argv)

    detector = MotionDetector(args.threshold_deg, args.rest_s)
    writer = None
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        new = not args.out.exists()
        handle = args.out.open("a", newline="", encoding="utf-8")
        writer = csv.writer(handle)
        if new:
            writer.writerow(["first_movement_iso", "first_movement_epoch_ms", "joint",
                             "delta_deg", "rest_ms"])
    started, packets = time.time(), 0
    with socket.create_connection((args.robot_ip, FEEDBACK_PORT), timeout=3.0) as sock:
        print(f"listening to {args.robot_ip}:{FEEDBACK_PORT}", flush=True)
        try:
            for t, joints in read_packets(sock):
                packets += 1
                event = detector.update(t, joints)
                if event:
                    joint, delta, rest_ms = event
                    iso = datetime.fromtimestamp(t).isoformat(timespec="milliseconds")
                    row = [iso, f"{t * 1000:.0f}", f"J{joint}", f"{delta:.3f}", f"{rest_ms:.0f}"]
                    print(",".join(row), flush=True)
                    if writer:
                        writer.writerow(row)
                        handle.flush()
                if args.duration_s and t - started >= args.duration_s:
                    break
        except KeyboardInterrupt:
            pass
    elapsed = time.time() - started
    print(f"# {packets} packets in {elapsed:.1f} s ({packets / max(elapsed, 1e-9):.0f} Hz)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
