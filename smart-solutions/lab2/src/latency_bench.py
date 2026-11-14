"""Control and camera latency bench for docs/control_latency_cameras.csv and camera_metrics.csv.

One trial = the station sends one small linear move (Z +dz, next trial back to
the start) on the MG400 motion port. Timestamps on the station clock:

* command_timestamp: just before the MovL bytes are written to port 30003;
* robot_first_movement_timestamp: first feedback packet (port 30004, ~8 ms)
  whose joint angles left the resting value (src.motion_watch detector);
* camera_change_timestamp (optional, per --camera): first MJPEG frame from the
  local camera server that differs from the resting picture.

control latency = first movement - command; camera latency = camera change -
first movement (physical event -> frame received by a stream client, the page
adds only browser decode/paint).

Safety: run only with a person at the emergency stop, nothing else commanding
the robot (no hub, no station, no DobotStudio JOG), robot enabled and idle in
free air. The move is --dz-mm (default 3 mm) at --speed % (default 5 %).

Usage (from smart-solutions/lab2):
    python -m src.latency_bench --condition no_cameras --camera-count 0 --trials 10
    python -m src.latency_bench --condition both_cameras --camera-count 2 --camera table --camera tool
"""

from __future__ import annotations

import argparse
import csv
import re
import socket
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from src.motion_watch import FEEDBACK_PORT, MotionDetector, read_packets

DASHBOARD_PORT = 29999
MOTION_PORT = 30003
CONTROL_HEADER = ["condition", "camera_count", "trial", "command_timestamp",
                  "robot_first_movement_timestamp", "latency_ms", "method", "note"]


def iso(t: float) -> str:
    return datetime.fromtimestamp(t).isoformat(timespec="milliseconds")


class Port:
    """One request/reply MG400 TCP port."""

    def __init__(self, ip: str, port: int) -> None:
        self.sock = socket.create_connection((ip, port), timeout=5.0)

    def send(self, command: str) -> float:
        t = time.time()
        self.sock.sendall(command.encode())
        return t

    def reply(self) -> str:
        data = b""
        while not data.endswith(b";"):
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError("robot closed the port")
            data += chunk.strip()
        return data.decode()

    def call(self, command: str) -> str:
        self.send(command)
        answer = self.reply()
        if not answer.startswith("0,"):
            raise RuntimeError(f"{command} -> {answer}")
        return answer


class FeedbackWatch(threading.Thread):
    def __init__(self, ip: str) -> None:
        super().__init__(daemon=True)
        self.ip, self.detector = ip, MotionDetector()
        self.events: list[float] = []
        self.joints = None
        self.resting = threading.Event()

    def run(self) -> None:
        with socket.create_connection((self.ip, FEEDBACK_PORT), timeout=3.0) as sock:
            for t, joints in read_packets(sock):
                self.joints = joints
                if self.detector.update(t, joints):
                    self.events.append(t)
                    self.resting.clear()
                if not self.detector.moving:
                    self.resting.set()

    def first_after(self, t0: float, timeout: float) -> float | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            hits = [t for t in self.events if t >= t0]
            if hits:
                return hits[0]
            time.sleep(0.005)
        return None


class StreamWatch(threading.Thread):
    """Receives one MJPEG stream; records arrival time and a tiny grey thumbnail per frame."""

    def __init__(self, url: str) -> None:
        super().__init__(daemon=True)
        self.url, self.frames = url, []  # (t, thumbnail ndarray)
        self.error = None

    def run(self) -> None:
        import cv2
        import numpy as np

        try:
            stream = urllib.request.urlopen(self.url, timeout=5)
            buffer = b""
            while True:
                chunk = stream.read(16384)
                if not chunk:
                    return
                buffer += chunk
                while True:
                    start = buffer.find(b"\xff\xd8")
                    end = buffer.find(b"\xff\xd9", start + 2)
                    if start < 0 or end < 0:
                        break
                    jpeg, buffer = buffer[start:end + 2], buffer[end + 2:]
                    t = time.time()
                    image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_GRAYSCALE)
                    if image is not None:
                        thumb = cv2.resize(image, (160, 90), interpolation=cv2.INTER_AREA)
                        self.frames.append((t, thumb.astype("float32")))
                        del self.frames[:-400]
        except Exception as exc:  # reported in the CSV note
            self.error = repr(exc)

    def change_after(self, t_rest: float, t_move: float, timeout: float, k: float = 4.0):
        """First frame after t_move differing from the frames before t_move by k x noise."""
        import numpy as np

        deadline = time.time() + timeout
        while time.time() < deadline:
            frames = list(self.frames)
            rest = [f for t, f in frames if t_rest <= t < t_move]
            if len(rest) >= 2:
                base = rest[-1]
                noise = max(np.mean(np.abs(rest[-1] - rest[-2])), 0.3)
                for t, f in frames:
                    if t >= t_move and np.mean(np.abs(f - base)) > k * noise:
                        return t, float(np.mean(np.abs(f - base)) / noise)
            time.sleep(0.01)
        return None, None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--robot-ip", default="192.168.1.6")
    p.add_argument("--condition", required=True, help="no_cameras / usb_only / both_cameras")
    p.add_argument("--camera-count", type=int, required=True)
    p.add_argument("--camera", action="append", default=[], help="camera server name to time (table, tool)")
    p.add_argument("--camera-server", default="http://127.0.0.1:5002")
    p.add_argument("--trials", type=int, default=10)
    p.add_argument("--dz-mm", type=float, default=3.0)
    p.add_argument("--speed", type=int, default=5)
    p.add_argument("--out", type=Path, default=Path("docs/control_latency_cameras.csv"))
    p.add_argument("--camera-out", type=Path, default=Path("data/camera_latency_trials.csv"))
    p.add_argument("--note", default="")
    a = p.parse_args(argv)

    watch = FeedbackWatch(a.robot_ip)
    watch.start()
    streams = {name: StreamWatch(f"{a.camera_server}/stream/{name}.mjpg") for name in a.camera}
    for s in streams.values():
        s.start()
    dash, motion = Port(a.robot_ip, DASHBOARD_PORT), Port(a.robot_ip, MOTION_PORT)
    mode = dash.call("RobotMode()")
    if "{5}" not in mode:
        raise SystemExit(f"robot must be enabled and idle (mode 5): {mode}")
    pose = [float(v) for v in re.search(r"\{([^}]*)\}", dash.call("GetPose()")).group(1).split(",")[:4]]
    dash.call(f"SpeedFactor({a.speed})")
    print(f"start pose {pose}, {a.trials} trials of Z±{a.dz_mm} mm at {a.speed} %", flush=True)

    rows, cam_rows = [], []
    if not watch.resting.wait(5):
        raise SystemExit("robot is not at rest")
    time.sleep(1.0)
    for trial in range(1, a.trials + 1):
        z = pose[2] + (a.dz_mm if trial % 2 else 0.0)
        t_rest = time.time() - 0.8
        t_cmd = motion.send(f"MovL({pose[0]:.3f},{pose[1]:.3f},{z:.3f},{pose[3]:.3f})")
        answer = motion.reply()
        if not answer.startswith("0,"):
            raise SystemExit(f"MovL refused: {answer}")
        t_move = watch.first_after(t_cmd, 5.0)
        if t_move is None:
            raise SystemExit("no movement detected within 5 s; stopping")
        latency = (t_move - t_cmd) * 1000
        rows.append([a.condition, a.camera_count, trial, iso(t_cmd), iso(t_move), f"{latency:.0f}",
                     "feedback_30004", f"MovL Z{'+' if trial % 2 else '-'}{a.dz_mm}mm {a.speed}% {a.note}".strip()])
        line = f"trial {trial}: command->movement {latency:.0f} ms"
        for name, stream in streams.items():
            t_cam, ratio = stream.change_after(t_rest, t_move, 3.0)
            cam_ms = None if t_cam is None else (t_cam - t_move) * 1000
            cam_rows.append([iso(t_move), name, a.condition, trial,
                             "" if cam_ms is None else f"{cam_ms:.0f}",
                             "" if ratio is None else f"{ratio:.1f}", stream.error or ""])
            line += f", {name} frame +{cam_ms:.0f} ms" if cam_ms is not None else f", {name} no change"
        print(line, flush=True)
        time.sleep(0.2)
        while not watch.resting.wait(0.1):
            pass
        time.sleep(1.0)

    for path, header, data in ((a.out, CONTROL_HEADER, rows),
                               (a.camera_out, ["movement_timestamp", "camera", "condition", "trial",
                                               "movement_to_frame_ms", "diff_over_noise", "error"], cam_rows)):
        if not data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if new:
                writer.writerow(header)
            writer.writerows(data)
    values = [float(r[5]) for r in rows]
    print(f"{a.condition}: mean {sum(values) / len(values):.0f} ms, max {max(values):.0f} ms, n={len(values)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
