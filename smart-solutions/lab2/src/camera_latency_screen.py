"""Camera event-to-frame latency, FPS and bandwidth with the station monitor as the event.

The station monitor must be inside the camera picture. A full-screen window
flips black/white every --period-s; each flip time is the physical event
(plus the monitor's own display lag, ~1 refresh). One MJPEG client reads the
local camera server; a frame "shows" a flip when the mean brightness of the
screen region crosses half-way between its black and white levels. The
screen region is found automatically as the pixels that change most between
the black and white phases.

latency = frame received by the stream client - flip time (station clock);
FPS and Mbit/s come from the camera server counters over the same window.

Usage (from smart-solutions/lab2, camera server already running):
    python -m src.camera_latency_screen --camera table --flips 12
"""

from __future__ import annotations

import argparse
import csv
import json
import threading
import time
import tkinter as tk
import urllib.request
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


def iso(t: float) -> str:
    return datetime.fromtimestamp(t).isoformat(timespec="milliseconds")


class Stream(threading.Thread):
    def __init__(self, url: str) -> None:
        super().__init__(daemon=True)
        self.url, self.frames = url, []

    def run(self) -> None:
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
                    self.frames.append((t, cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)
                                        .astype(np.float32)))


def metrics(server: str, name: str) -> dict:
    data = json.load(urllib.request.urlopen(f"{server}/api/cameras", timeout=5))
    return data["cameras"][name]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--camera", default="table")
    p.add_argument("--server", default="http://127.0.0.1:5002")
    p.add_argument("--flips", type=int, default=12)
    p.add_argument("--period-s", type=float, default=1.5)
    p.add_argument("--out", type=Path, default=Path("docs/camera_metrics.csv"))
    p.add_argument("--note", default="")
    a = p.parse_args(argv)

    stream = Stream(f"{a.server}/stream/{a.camera}.mjpg")
    stream.start()
    time.sleep(3.0)
    before, t_before = metrics(a.server, a.camera), time.time()

    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.configure(background="black", cursor="none")
    flips: list[tuple[float, str]] = []
    state = {"i": 0}

    def flip() -> None:
        if state["i"] >= a.flips + 2:
            root.destroy()
            return
        colour = "white" if state["i"] % 2 == 0 else "black"
        root.configure(background=colour)
        root.update_idletasks()
        root.update()
        flips.append((time.time(), colour))
        state["i"] += 1
        root.after(int(a.period_s * 1000), flip)

    root.after(1500, flip)
    root.mainloop()
    time.sleep(1.0)
    after, t_after = metrics(a.server, a.camera), time.time()

    frames = list(stream.frames)
    # screen region: pixels with the largest difference between the phases
    def phase_mean(colour: str) -> np.ndarray:
        picks = []
        for (t0, c), (t1, _) in zip(flips, flips[1:]):
            if c == colour:
                picks += [f for t, f in frames if t0 + 0.6 * (t1 - t0) <= t < t1]
        return np.mean(picks, axis=0)

    white, black = phase_mean("white"), phase_mean("black")
    diff = white - black
    mask = diff > max(40.0, np.percentile(diff, 99) * 0.5)
    if mask.sum() < 20:
        raise SystemExit(f"screen not found in the {a.camera} picture (max diff {diff.max():.0f})")
    level_w, level_b = white[mask].mean(), black[mask].mean()
    half = (level_w + level_b) / 2

    latencies = []
    for (t0, colour), (t1, _) in zip(flips[1:], flips[2:]):  # first flip only primes the phases
        for t, f in frames:
            if t < t0:
                continue
            v = f[mask].mean()
            if (colour == "white" and v > half) or (colour == "black" and v < half):
                latencies.append((t0, t, (t - t0) * 1000))
                break
    window = t_after - t_before
    m0, m1 = before["metrics"], after["metrics"]
    fps = (m1["frames_served"] - m0["frames_served"]) / window
    mbit = (m1["bytes_served"] - m0["bytes_served"]) * 8 / window / 1e6
    cfg = after["configuration"]
    capture = f'{cfg.get("capture_width", "")}x{cfg.get("capture_height", "")}'
    display = f'{after["resolution"]["width"]}x{after["resolution"]["height"]}'

    new = not a.out.exists() or a.out.stat().st_size == 0
    with a.out.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new:
            writer.writerow(["measured_at", "camera", "source", "trial", "capture_resolution",
                             "display_resolution", "client_count", "target_fps", "measured_latency_ms",
                             "measured_fps", "bandwidth_mbps", "method", "note"])
        for trial, (t0, _t, ms) in enumerate(latencies, 1):
            writer.writerow([iso(t0), a.camera, cfg.get("backend", ""), trial, capture, display, 1,
                             after["target_fps"], f"{ms:.0f}", f"{fps:.2f}", f"{mbit:.2f}",
                             "monitor_flip_to_stream_client", a.note])
    values = [ms for *_, ms in latencies]
    print(f"{a.camera}: {len(values)} flips, latency mean {np.mean(values):.0f} ms, "
          f"min {min(values):.0f}, max {max(values):.0f}; served {fps:.2f} fps, {mbit:.2f} Mbit/s; "
          f"screen pixels {int(mask.sum())}, levels {level_b:.0f}->{level_w:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
