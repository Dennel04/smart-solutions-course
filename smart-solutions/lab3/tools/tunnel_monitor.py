"""48-hour WireGuard reachability journal and offline report (Python 3.9+).

Use "analyze --log PATH --start UTC" offline. On an authorised Linux host,
use "monitor --allow-live --log PATH --start UTC --interface NAME
--target IP --timeout SECONDS" with a verified WireGuard interface and route.
Use the same arguments to resume. Keep the journal and its .state.json
sidecar together at the original path; never remove either during a run.
Use a fresh output path rather than resuming a legacy journal without state.
Do not use the repository CSV template for output.
"""

import argparse
import csv
import fcntl
import io
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import NamedTuple


FIELDS = ("timestamp", "reachable", "rtt_ms", "notes")
HEADER = (",".join(FIELDS) + "\n").encode("ascii")
TEMPLATE = Path(__file__).resolve().parents[1] / "data" / "tunnel_48h.csv"
STEP = timedelta(seconds=10)
WINDOW = timedelta(hours=48)
EXPECTED = WINDOW // STEP
UTC = timezone.utc
# Require iputils' complete one-packet summary, without ICMP errors.
SUMMARY = re.compile(
    r"^1 packets? transmitted, ([01]) received, (?:0|100)% packet loss, time \d+ms$",
    re.MULTILINE,
)
RTT = re.compile(r"^rtt min/avg/max/mdev = (\d+(?:\.\d+)?)/", re.MULTILINE)


class Sample(NamedTuple):
    reachable: str
    rtt_ms: str
    notes: str


def utc_now():
    return datetime.now(UTC)


def utc_timestamp(value):
    try:
        stamp = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        raise ValueError("expected an ISO 8601 UTC timestamp") from None
    if stamp.utcoffset() != timedelta(0):
        raise ValueError("timestamp must explicitly use UTC")
    return stamp.astimezone(UTC)


def iso(stamp):
    return stamp.isoformat().replace("+00:00", "Z")


def window_end(start):
    try:
        return start + WINDOW
    except OverflowError:
        raise ValueError("start leaves no room for the complete 48-hour UTC window") from None


def validate_row(row, start, rows, line):
    if len(row) != len(FIELDS):
        raise ValueError(f"line {line}: expected four columns")
    timestamp, reachable, rtt, notes = row
    stamp = utc_timestamp(timestamp)
    offset = stamp - start
    if not timedelta(0) <= offset < WINDOW or offset % STEP:
        raise ValueError(f"line {line}: timestamp outside the scheduled grid")
    if stamp in rows:
        raise ValueError(f"line {line}: duplicate timestamp")
    if reachable not in ("", "0", "1"):
        raise ValueError(f"line {line}: invalid reachable value")
    if rtt:
        try:
            valid_rtt = reachable == "1" and math.isfinite(float(rtt)) and float(rtt) >= 0
        except ValueError:
            valid_rtt = False
        if not valid_rtt:
            raise ValueError(f"line {line}: invalid RTT")
    rows[stamp] = Sample(reachable, rtt, notes)


def read_journal(raw, start):
    """Read complete records only; return rows and the end of the valid prefix."""
    boundary = raw.rfind(b"\n") + 1
    if not boundary:
        if not HEADER.startswith(raw):
            raise ValueError("invalid journal header")
        return {}, 0
    reader = csv.reader(io.StringIO(raw[:boundary].decode("utf-8"), newline=""), strict=True)
    if tuple(next(reader, ())) != FIELDS:
        raise ValueError("invalid journal header")
    rows = {}
    for row in reader:
        validate_row(row, start, rows, reader.line_num)
    return rows, boundary


def analyze(raw, start):
    end = window_end(start)
    rows, boundary = read_journal(raw, start)
    up = down = outages = longest = streak = 0
    for index in range(EXPECTED):
        sample = rows.get(start + index * STEP)
        status = sample.reachable if sample else ""
        if status == "0":
            outages += streak == 0
            down += 1
            streak += 1
            longest = max(longest, streak)
        else:
            up += status == "1"
            streak = 0  # Missing and unknown break a run of observed failures.
    known = up + down
    unknown = EXPECTED - known
    seconds = int(STEP.total_seconds())
    return {
        "expected_checks": EXPECTED,
        "recorded_checks": len(rows),
        "missing_intervals": EXPECTED - len(rows),
        "recorded_unknown_checks": len(rows) - known,
        "observed_outages": outages,
        "observed_downtime_seconds": down * seconds,
        "longest_observed_outage_seconds": longest * seconds,
        "unknown_seconds": unknown * seconds,
        "known_availability_percent": 100 * up / known if known else None,
        "window_availability_bounds_percent": [100 * up / EXPECTED, 100 * (up + unknown) / EXPECTED],
        "first_interval_down": rows.get(start, Sample("", "", "")).reachable == "0",
        "last_interval_down": rows.get(end - STEP, Sample("", "", "")).reachable == "0",
        "ignored_incomplete_tail": boundary < len(raw),
    }


def ping_once(target, interface, timeout, run=subprocess.run):
    """Linux iputils only; never emit process output, exception text or commands."""
    command = ["ping", f"-{target.version}", "-n", "-I", interface, "-c", "1",
               "-W", str(timeout), str(target)]
    try:
        result = run(command, capture_output=True, text=True, encoding="ascii", errors="replace",
                     env={**os.environ, "LC_ALL": "C"}, timeout=timeout + 1, check=False)
    except subprocess.TimeoutExpired:
        return Sample("", "", "process_timeout")
    except OSError:
        return Sample("", "", "probe_launch_error")
    summary = SUMMARY.search(result.stdout)
    if result.stderr or not summary:
        return Sample("", "", "probe_error_or_unrecognized_output")
    received = summary[1]
    if result.returncode == 0 and received == "1":
        rtt = RTT.search(result.stdout)
        return Sample("1", rtt[1] if rtt else "", "reply" if rtt else "reply_without_rtt")
    if result.returncode == 1 and received == "0":
        return Sample("0", "", "no_reply")
    return Sample("", "", "probe_error_or_unrecognized_output")


def ip_record(arguments, run):
    """A single iproute2 JSON record, or unknown; never log command output."""
    try:
        result = run(["ip", "-j", *arguments], capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=1, check=False)
        records = json.loads(result.stdout) if result.returncode == 0 and not result.stderr else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if isinstance(records, list) and len(records) == 1 and isinstance(records[0], dict):
        return records[0]
    return None


def path_error(target, interface, run):
    link = ip_record(["-d", "link", "show", "dev", interface], run)
    info = link.get("linkinfo") if link else None
    if (not isinstance(info, dict) or info.get("info_kind") != "wireguard"
            or link.get("ifname") != interface):
        return "wireguard_interface_unverified"
    flags = link.get("flags")
    if not isinstance(flags, list) or "UP" not in flags:
        return "wireguard_interface_down"
    # Do not force oif here: check the kernel's actual route selection.
    route = ip_record([f"-{target.version}", "route", "get", str(target)], run)
    if not route or route.get("dev") != interface or route.get("type", "unicast") != "unicast":
        return "wireguard_route_unverified"
    return None


def verified_probe(target, interface, timeout, run):
    error = path_error(target, interface, run)
    if error:
        return Sample("", "", error)
    result = ping_once(target, interface, timeout, run=run)
    # Do not trust either outcome if the path is no longer confirmed.
    error = path_error(target, interface, run)
    return Sample("", "", error) if error else result


def write_durable(file, content):
    file.write(content)
    file.flush()
    os.fsync(file.fileno())


def save_attempt(path, run_notes, last_attempt):
    """Replace state durably before dispatch; caller holds the journal lock."""
    data = json.dumps({"run": run_notes, "last_attempt": last_attempt}).encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as file:
        temporary = Path(file.name)
        try:
            write_durable(file, data)
            file.close()
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


def load_attempt(path, run_notes, raw):
    try:
        state = json.loads(path.read_bytes())
    except FileNotFoundError:
        # Existing CSV bytes could belong to a probe that ran without durable
        # state. Do not guess a watermark or silently reuse a legacy journal.
        if raw:
            raise ValueError("existing journal has no attempt state; use a fresh output path")
        save_attempt(path, run_notes, -1)
        return -1
    except ValueError:
        raise ValueError("invalid journal attempt state") from None
    if not isinstance(state, dict) or state.get("run") != run_notes:
        raise ValueError("journal parameters do not match this run")
    last_attempt = state.get("last_attempt")
    if type(last_attempt) is not int or not -1 <= last_attempt < EXPECTED:
        raise ValueError("invalid journal attempt index")
    return last_attempt


def collect(file, start, run_notes, probe, *, state_path, now=utc_now, sleep=time.sleep):
    """Resume with the file already exclusively locked; use injectable offline I/O."""
    end = window_end(start)
    file.seek(0)
    raw = file.read()
    rows, boundary = read_journal(raw, start)
    if any(not sample.notes.startswith(run_notes + ";") for sample in rows.values()):
        raise ValueError("journal parameters do not match this run")
    last_attempt = load_attempt(state_path, run_notes, raw)
    if any((stamp - start) // STEP > last_attempt for stamp in rows):
        raise ValueError("journal contains records ahead of its attempt state")
    if boundary < len(raw):
        # Only a non-terminated fragment is rolled back. Never drop complete rows.
        file.truncate(boundary)
        file.flush()
        os.fsync(file.fileno())
    file.seek(0, os.SEEK_END)
    if not boundary:
        write_durable(file, HEADER)

    # Never replay an attempted slot, even if it has no CSV row or UTC rolled back.
    resumed_at = now()
    for index in range(last_attempt + 1, EXPECTED):
        planned = start + index * STEP
        if planned < resumed_at or planned in rows:
            continue
        actual = now()
        while actual < planned:
            sleep((planned - actual).total_seconds())
            actual = now()
        if actual >= end:
            break
        if actual >= planned + STEP:
            continue
        save_attempt(state_path, run_notes, index)
        actual = now()
        if not planned <= actual < planned + STEP:
            continue  # The durable write crossed a slot boundary or a clock jump.
        result = probe()
        notes = f"{run_notes};actual={iso(actual)};status={result.notes}"
        line = io.StringIO(newline="")
        csv.writer(line, lineterminator="\n").writerow(
            (iso(planned), result.reachable, result.rtt_ms, notes)
        )
        write_durable(file, line.getvalue().encode("utf-8"))


def live_parameters(interface, address, timeout):
    # A name (not a source IP or arbitrary ping option) and a numeric target.
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,14}", interface):
        raise ValueError("invalid interface name")
    try:
        target = ipaddress.ip_address(address)
    except ValueError:
        raise ValueError("target must be a numeric IP address") from None
    if "%" in address or target.is_unspecified or target.is_loopback or target.is_multicast:
        raise ValueError("target must be a non-local unicast peer address without a scope suffix")
    if not 1 <= timeout <= 8:
        raise ValueError("timeout must be 1–8 seconds (shorter than the slot)")
    return target


def monitor(path, start, interface, target, timeout, *, run=subprocess.run):
    end = window_end(start)
    if path.resolve() == TEMPLATE.resolve():
        raise ValueError("use a separate output journal, not the repository template")
    # Check aliases before preflight too, so a template alias cannot run commands.
    if path.exists() and TEMPLATE.exists() and path.samefile(TEMPLATE):
        raise ValueError("output journal refers to the repository template")
    error = path_error(target, interface, run)
    if error:
        raise ValueError(f"WireGuard path preflight failed: {error}")
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o600), "r+b") as file:
        journal_stat = os.fstat(file.fileno())
        if TEMPLATE.exists() and os.path.samestat(journal_stat, TEMPLATE.stat()):
            raise ValueError("output journal refers to the repository template")
        if journal_stat.st_nlink != 1:
            raise ValueError("journal must not have hard-link aliases")
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        notes = (f"start={iso(start)};end={iso(end)};method=icmp;"
                 f"interface={interface};target={target};timeout_s={timeout}")
        state_path = path.with_name(path.name + ".state.json")
        collect(file, start, notes, lambda: verified_probe(target, interface, timeout, run),
                state_path=state_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    offline = modes.add_parser("analyze", help="offline JSON report")
    live = modes.add_parser("monitor", help="authorised Linux iputils collection only")
    for mode in (offline, live):
        mode.add_argument("--log", type=Path, required=True)
        mode.add_argument("--start", required=True, help="planned start in ISO 8601 UTC")
    live.add_argument("--allow-live", action="store_true")
    live.add_argument("--interface", required=True, help="verified WireGuard interface")
    live.add_argument("--target", required=True, help="approved numeric peer IP")
    live.add_argument("--timeout", type=int, required=True, help="seconds, 1–8")
    args = parser.parse_args(argv)
    try:
        start = utc_timestamp(args.start)
        window_end(start)
        if args.mode == "analyze":
            print(json.dumps(analyze(args.log.read_bytes(), start), indent=2))
        else:
            if not args.allow_live or sys.platform != "linux":
                parser.error("live mode requires Linux and explicit --allow-live")
            target = live_parameters(args.interface, args.target, args.timeout)
            monitor(args.log, start, args.interface, target, args.timeout)
    except BlockingIOError:
        parser.error("journal is locked by another process")
    except OSError as error:
        parser.error(f"journal I/O failed (errno {error.errno})")
    except (ValueError, csv.Error) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
