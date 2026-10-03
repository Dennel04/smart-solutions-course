"""USB channel for Atom letters: AtomS3 serial line -> station POST /api/letter.

The merged Atom firmware writes every sent letter as one JSON line on its USB
serial port, next to the 10 ms pump telemetry:

    {"letter":"K","session":"1a2b...","seq":3,"atom_sent_ms":81234}

This bridge is for a station PC without WiFi (the lab desktop): it forwards
those lines to the station and ignores everything else. When the pump logger
(data-acquisition-course logger.py) already owns the port, use its --station
option instead -- only one program can open a COM port.

Run:
    python src/atom_bridge.py --port COM4 --station http://127.0.0.1:5000
"""

from __future__ import annotations

import argparse
import json
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

import requests

RETRIES = 3
RETRY_DELAY_S = 0.25


def letter_event(message: object) -> dict[str, Any] | None:
    """The station payload if ``message`` is a letter event, else None."""
    if not isinstance(message, dict) or "letter" not in message:
        return None
    letter = message.get("letter")
    session = message.get("session")
    seq = message.get("seq")
    sent = message.get("atom_sent_ms")
    if not (isinstance(letter, str) and len(letter) == 1 and "A" <= letter <= "Z"):
        return None
    if not isinstance(session, str) or not session:
        return None
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        return None
    payload: dict[str, Any] = {"letter": letter, "session": session, "seq": seq}
    if isinstance(sent, int) and not isinstance(sent, bool) and sent >= 0:
        payload["atom_sent_ms"] = sent
    return payload


class LetterForwarder:
    """POSTs letters on its own thread, so a slow station never stalls the
    serial reader (the pump logger's 500 ms watchdog lives on that reader)."""

    def __init__(
        self,
        station_url: str,
        *,
        session: requests.Session | None = None,
        log: Callable[[str], None] = print,
        timeout: float = 2.0,
    ) -> None:
        self.url = station_url.rstrip("/") + "/api/letter"
        self.session = session or requests.Session()
        self.log = log
        self.timeout = timeout
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="letter-forwarder", daemon=True)
        self._thread.start()

    def submit(self, payload: dict[str, Any]) -> None:
        self._queue.put(payload)

    def close(self, wait: float = 3.0) -> None:
        self._queue.put(None)
        self._thread.join(wait)

    def _run(self) -> None:
        while True:
            payload = self._queue.get()
            if payload is None:
                return
            self._forward(payload)

    def _forward(self, payload: dict[str, Any]) -> None:
        for attempt in range(1, RETRIES + 1):
            try:
                response = self.session.post(self.url, json=payload, timeout=self.timeout)
            except requests.RequestException as exc:
                self.log(f"[letter] {payload['letter']} seq={payload['seq']} attempt {attempt}: {exc}")
                time.sleep(RETRY_DELAY_S)
                continue
            # 2xx = accepted, 409/422/503 = the station answered and decided;
            # a retry would not change that answer.
            self.log(
                f"[letter] {payload['letter']} seq={payload['seq']} -> HTTP {response.status_code} "
                f"{response.text.strip()[:160]}"
            )
            return
        self.log(f"[letter] {payload['letter']} seq={payload['seq']} not delivered")


def run_bridge(lines, forwarder: LetterForwarder, log: Callable[[str], None] = print) -> None:
    """Forward letter events from an iterable of raw serial lines."""
    for raw in lines:
        if not raw:
            continue
        text = raw.decode("utf-8", errors="replace").strip() if isinstance(raw, bytes) else raw.strip()
        if not text.startswith("{"):
            continue
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            continue
        payload = letter_event(message)
        if payload is not None:
            log(f"[atom] letter {payload['letter']} seq={payload['seq']}")
            forwarder.submit(payload)


def open_atom(port: str, baud: int):
    """Open the Atom's USB serial without resetting it (DTR/RTS low first)."""
    import serial

    ser = serial.serial_for_url(port, baud, timeout=0.2, do_not_open=True)
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", required=True, help="Atom USB serial port, e.g. COM4")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--station", default="http://127.0.0.1:5000")
    args = p.parse_args()

    import serial

    forwarder = LetterForwarder(args.station)
    print(f"bridge {args.port} -> {forwarder.url} (Ctrl+C to stop)")
    try:
        # The port vanishes when the Atom resets (side RESET button, re-flash,
        # loose cable): wait and reopen instead of dying.
        while True:
            try:
                ser = open_atom(args.port, args.baud)
            except serial.SerialException as exc:
                print(f"[usb] {args.port} not available ({exc}); retrying")
                time.sleep(1.0)
                continue
            print(f"[usb] {args.port} open")

            def lines():
                while True:
                    yield ser.readline()

            try:
                run_bridge(lines(), forwarder)
            except serial.SerialException as exc:
                print(f"[usb] port lost ({exc}); reconnecting")
            finally:
                ser.close()
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        forwarder.close()


if __name__ == "__main__":
    main()
