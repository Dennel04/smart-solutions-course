"""Explicit, local USB authorization only. Never upload/reset or contact a server."""
import argparse
import getpass
import json
import re
import time

MARKER = b"# HEALTH CHALLENGE "
SAFE_STATES = {
    "WAITING FOR USB", "WIFI CONNECTED", "TLS VERIFIED", "HEALTH OK",
    "INPUT ERROR", "INPUT ERROR; STOP", "CA ERROR", "WIFI ERROR", "TLS ERROR",
    "CERT OR UTC ERROR", "HEALTH ERROR", "NONCE ERROR; STOP",
    "RADIO STOP ERROR",
}


def valid_text(value, minimum, maximum):
    return minimum <= len(value) <= maximum and all(32 <= ord(c) <= 126 for c in value)


def make_frame(ssid, password, challenge, utc):
    if not valid_text(ssid, 1, 32) or not valid_text(password, 8, 63):
        raise ValueError("Invalid input: printable ASCII SSID 1–32, WPA2 password 8–63")
    if not re.fullmatch(r"[0-9a-f]{16}", challenge):
        raise ValueError("Invalid challenge")
    if type(utc) is not int or not 1704067200 <= utc < 2114380800:
        raise ValueError("Check the Mac UTC clock (2024–2036)")
    data = json.dumps(dict(action="health_once", challenge=challenge, ssid=ssid,
                           password=password, utc=utc, confirm=True),
                      ensure_ascii=True, separators=(",", ":")).encode("ascii") + b"\n"
    if len(data) > 511:
        raise ValueError("Input too long")
    return data


def session(port, ssid, password, *, clock=time.monotonic, utc=time.time, display=print):
    """No retries; receives a fresh challenge only AFTER explicit HELLO."""
    port.reset_input_buffer()
    port.write(b"HELLO\n")
    end = clock() + 8
    challenge = None
    while clock() < end:
        line = port.readline(128).strip()
        if line.startswith(MARKER):
            value = line[len(MARKER):]
            if not re.fullmatch(b"[0-9a-f]{16}", value):
                raise RuntimeError("Invalid device challenge; no authorization sent")
            challenge = value.decode("ascii")
            break
    if challenge is None:
        raise RuntimeError("No health-only challenge; STOP, no automatic reconnect")
    frame = make_frame(ssid, password, challenge, int(utc()))
    if port.write(frame) != len(frame):
        raise RuntimeError("Incomplete USB write; STOP")
    del frame
    end = clock() + 90
    while clock() < end:
        # Never echo arbitrary device output, payloads, or exceptions.
        line = port.readline(128).strip()
        state = line.removeprefix(b"# HEALTH ").decode("ascii", errors="replace")
        if state in SAFE_STATES:
            display(state)
            if state == "HEALTH OK":
                return True
            if "ERROR" in state:
                return False
    raise RuntimeError("USB result timeout; STOP, no automatic retry")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    # getpass refuses an echoing/non-interactive fallback rather than logging secrets.
    import warnings
    warnings.simplefilter("error", getpass.GetPassWarning)
    try:
        ssid = getpass.getpass("Wi-Fi SSID (hidden): ")
        password = getpass.getpass("Wi-Fi password (hidden): ")
        if not valid_text(ssid, 1, 32) or not valid_text(password, 8, 63):
            raise ValueError("input")
        print("Check the Mac UTC clock. This sends ONE production GET /health after USB authorization.")
        if input("Type HEALTH ONCE to authorize: ") != "HEALTH ONCE":
            return 1
        import serial
        # Do not pulse DTR/RTS, reset the device, or retry a failed connection.
        port = serial.Serial(port=None, baudrate=115200, timeout=0.5, write_timeout=2)
        port.dtr = False
        port.rts = False
        port.port = args.port
        try:
            port.open()
            return 0 if session(port, ssid, password) else 1
        finally:
            port.close()
    except (Exception, KeyboardInterrupt):
        print("STOP: local session failed/cancelled; no automatic retry. Details suppressed to protect credentials.")
        return 1
    finally:
        # Python/driver allocations cannot promise cryptographic memory erasure.
        ssid = password = None


if __name__ == "__main__":
    raise SystemExit(main())
