import io
import fcntl
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from tools import tunnel_monitor as monitor


START = monitor.utc_timestamp("2026-01-01T00:00:00Z")
META = "synthetic-run"


def row(slot, reachable, rtt="", notes=META + ";status=synthetic"):
    return f"{monitor.iso(START + slot * monitor.STEP)},{reachable},{rtt},{notes}\n".encode()


class AnalysisTests(unittest.TestCase):
    def test_empty_window_is_all_unknown_not_down(self):
        report = monitor.analyze(monitor.HEADER, START)
        self.assertEqual(report["expected_checks"], 17280)
        self.assertEqual(report["missing_intervals"], 17280)
        self.assertEqual(report["observed_outages"], 0)
        self.assertIsNone(report["known_availability_percent"])
        self.assertEqual(report["window_availability_bounds_percent"], [0, 100])

    def test_unknown_and_missing_break_outages(self):
        data = monitor.HEADER + b"".join([
            row(6, "0"), row(1, "0"), row(0, "0"), row(3, "0"),
            row(4, ""), row(5, "0"), row(7, "1", "0.42"),
        ])
        report = monitor.analyze(data, START)
        self.assertEqual(report["recorded_checks"], 7)
        self.assertEqual(report["recorded_unknown_checks"], 1)
        self.assertEqual(report["missing_intervals"], 17273)
        self.assertEqual(report["observed_outages"], 3)
        self.assertEqual(report["observed_downtime_seconds"], 50)
        self.assertEqual(report["longest_observed_outage_seconds"], 20)
        self.assertEqual(report["unknown_seconds"], 172740)
        self.assertAlmostEqual(report["known_availability_percent"], 100 / 6)
        self.assertTrue(report["first_interval_down"])
        self.assertFalse(report["last_interval_down"])

    def test_half_open_window_includes_final_slot_but_not_end(self):
        report = monitor.analyze(monitor.HEADER + row(17279, "0"), START)
        self.assertTrue(report["last_interval_down"])
        self.assertEqual(report["observed_downtime_seconds"], 10)
        with self.assertRaisesRegex(ValueError, "scheduled grid"):
            monitor.analyze(monitor.HEADER + row(17280, "0"), START)

    def test_rejects_bad_complete_records(self):
        for record in (
            row(1, "1") + row(1, "0"), row(0.5, "0"), row(-1, "1"),
            row(2, "0", "7"), row(2, "1", "NaN"), row(2, "maybe"),
            b"2026-01-01T00:00:00,1,1,missing UTC\n",
        ):
            with self.subTest(record=record), self.assertRaises(ValueError):
                monitor.analyze(monitor.HEADER + record, START)

    def test_incomplete_tail_does_not_add_a_measurement(self):
        data = monitor.HEADER + row(0, "1", "1.5") + row(1, "0").rstrip(b"\n")
        report = monitor.analyze(data, START)
        self.assertTrue(report["ignored_incomplete_tail"])
        self.assertEqual(report["recorded_checks"], 1)
        self.assertEqual(report["observed_outages"], 0)


class ProbeTests(unittest.TestCase):
    def probe(self, completed=None, error=None):
        target = monitor.live_parameters("testwg", "192.0.2.1", 3)
        runner = Mock(return_value=completed, side_effect=error)
        result = monitor.ping_once(target, "testwg", 3, run=runner)
        args, kwargs = runner.call_args
        self.assertEqual(args[0], ["ping", "-4", "-n", "-I", "testwg", "-c", "1",
                                   "-W", "3", "192.0.2.1"])
        self.assertEqual(kwargs["timeout"], 4)
        self.assertEqual(kwargs["env"]["LC_ALL"], "C")
        return result

    def test_reply_and_confirmed_no_reply(self):
        reply = subprocess.CompletedProcess([], 0,
            "1 packets transmitted, 1 received, 0% packet loss, time 0ms\n"
            "rtt min/avg/max/mdev = 0.250/0.250/0.250/0.000 ms\n", "")
        self.assertEqual(self.probe(reply), ("1", "0.250", "reply"))
        no_reply = subprocess.CompletedProcess([], 1,
            "1 packets transmitted, 0 received, 100% packet loss, time 0ms\n", "")
        self.assertEqual(self.probe(no_reply), ("0", "", "no_reply"))

    def test_errors_are_unknown_and_sanitized(self):
        for result, error in (
            (subprocess.CompletedProcess([], 2, "", "private diagnostic"), None),
            (subprocess.CompletedProcess([], 1,
              "1 packets transmitted, 0 received, +1 errors, 100% packet loss, time 0ms\n", ""), None),
            (subprocess.CompletedProcess([], 1, "unrecognized output", ""), None),
            (None, subprocess.TimeoutExpired("private diagnostic", 4)),
            (None, OSError("private diagnostic")),
        ):
            with self.subTest(error=type(error)):
                sample = self.probe(result, error)
                self.assertEqual(sample[:2], ("", ""))
                self.assertNotIn("private", sample.notes)


def ip_result(record):
    return subprocess.CompletedProcess([], 0, json.dumps([record]), "")


def wireguard_link(interface="testwg"):
    return ip_result({"ifname": interface, "flags": ["UP"], "linkinfo": {"info_kind": "wireguard"}})


def wireguard_route(interface="testwg"):
    return ip_result({"dev": interface})


class PathTests(unittest.TestCase):
    target = monitor.live_parameters("testwg", "192.0.2.1", 3)
    no_reply = subprocess.CompletedProcess([], 1,
        "1 packets transmitted, 0 received, 100% packet loss, time 0ms\n", "")

    def test_eth0_is_rejected_before_opening_journal_or_ping(self):
        runner = Mock(return_value=ip_result({"ifname": "eth0", "flags": ["UP"],
                                               "linkinfo": {"info_kind": "veth"}}))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.csv"
            with self.assertRaisesRegex(ValueError, "wireguard_interface_unverified"):
                monitor.monitor(path, START, "eth0", self.target, 3, run=runner)
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(runner.call_args.args[0], ["ip", "-j", "-d", "link", "show", "dev", "eth0"])

    def test_verified_wireguard_path_accepts_confirmed_no_reply(self):
        runner = Mock(side_effect=[wireguard_link(), wireguard_route(), self.no_reply,
                                   wireguard_link(), wireguard_route()])
        self.assertEqual(monitor.verified_probe(self.target, "testwg", 3, runner),
                         ("0", "", "no_reply"))
        self.assertEqual([call.args[0][0] for call in runner.call_args_list],
                         ["ip", "ip", "ping", "ip", "ip"])
        self.assertEqual(runner.call_args_list[1].args[0],
                         ["ip", "-j", "-4", "route", "get", "192.0.2.1"])

    def test_route_disappears_during_monitoring(self):
        for failure in (
            ip_result({"dev": "eth0"}), ip_result({"dev": "testwg", "type": "local"}),
            subprocess.CompletedProcess([], 2, "", "private diagnostic"),
            subprocess.TimeoutExpired("private diagnostic", 1),
        ):
            with self.subTest(failure=type(failure)):
                runner = Mock(side_effect=[wireguard_link(), wireguard_route(), self.no_reply,
                                           wireguard_link(), failure])
                self.assertEqual(monitor.verified_probe(self.target, "testwg", 3, runner),
                                 ("", "", "wireguard_route_unverified"))
        runner = Mock(side_effect=[wireguard_link(), wireguard_route("eth0")])
        self.assertEqual(monitor.verified_probe(self.target, "testwg", 3, runner),
                         ("", "", "wireguard_route_unverified"))
        self.assertEqual([call.args[0][0] for call in runner.call_args_list], ["ip", "ip"])

    def test_monitor_records_lost_route_as_unknown(self):
        slot = START + monitor.WINDOW - monitor.STEP
        collect = monitor.collect

        def one_slot(*args, **kwargs):
            collect(*args, **kwargs, now=lambda: slot)

        runner = Mock(side_effect=[
            wireguard_link(), wireguard_route(),  # Startup.
            wireguard_link(), wireguard_route(), self.no_reply,  # Probe.
            wireguard_link(), wireguard_route("eth0"),  # Path changed.
        ])
        with tempfile.TemporaryDirectory() as directory, patch.object(monitor, "collect", one_slot):
            path = Path(directory) / "journal.csv"
            monitor.monitor(path, START, "testwg", self.target, 3, run=runner)
            report = monitor.analyze(path.read_bytes(), START)
            self.assertEqual(report["recorded_checks"], 1)
            self.assertEqual(report["recorded_unknown_checks"], 1)
            self.assertEqual(report["observed_outages"], 0)
        self.assertEqual(runner.call_count, 7)


class CollectionTests(unittest.TestCase):
    def test_restarts_without_repeating_elapsed_slots_and_repairs_tail(self):
        end = START + monitor.WINDOW
        clock = [end - timedelta(seconds=25)]
        seen = []

        def sleep(seconds):
            clock[0] += timedelta(seconds=seconds)

        def probe():
            seen.append(clock[0])
            return monitor.Sample("", "", "synthetic_unknown")

        prefix = monitor.HEADER + row(17276, "1", "1")
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile() as file:
            state = Path(directory) / "journal.state.json"
            monitor.save_attempt(state, META, 17277)
            file.write(prefix + row(17277, "0")[:-8])
            monitor.collect(file, START, META, probe, state_path=state,
                            now=lambda: clock[0], sleep=sleep)
            file.seek(0)
            data = file.read()
            self.assertTrue(data.startswith(prefix))
            report = monitor.analyze(data, START)
            self.assertEqual(report["recorded_checks"], 3)
            self.assertEqual(report["recorded_unknown_checks"], 2)
            self.assertEqual(report["observed_outages"], 0)
            self.assertEqual(seen, [end - timedelta(seconds=20), end - timedelta(seconds=10)])
            clock[0] = end - timedelta(seconds=10)
            monitor.collect(file, START, META, probe, state_path=state,
                            now=lambda: clock[0], sleep=sleep)
            self.assertEqual(len(seen), 2)

    def test_late_wake_skips_slot_without_catch_up_probes(self):
        end = START + monitor.WINDOW
        clock = [end - timedelta(seconds=21)]
        seen = []

        def sleep(seconds):
            clock[0] += timedelta(seconds=seconds + 11)

        def probe():
            seen.append(clock[0])
            return monitor.Sample("1", "0.5", "synthetic_reply")

        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile() as file:
            monitor.collect(file, START, META, probe, state_path=Path(directory) / "state.json",
                            now=lambda: clock[0], sleep=sleep)
            file.seek(0)
            rows, _ = monitor.read_journal(file.read(), START)
        self.assertEqual(list(rows), [end - timedelta(seconds=10)])
        self.assertEqual(seen, [end - timedelta(seconds=9)])

    def test_resume_rejects_different_parameters_without_editing_file(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile() as file:
            state = Path(directory) / "state.json"
            monitor.save_attempt(state, META, 0)
            data = monitor.HEADER + row(0, "0") + b"partial"
            file.write(data)
            probe = Mock()
            with self.assertRaisesRegex(ValueError, "parameters"):
                monitor.collect(file, START, "different-run", probe, state_path=state)
            probe.assert_not_called()
            file.seek(0)
            self.assertEqual(file.read(), data)

    def test_crash_after_mark_before_probe_does_not_repeat_slot(self):
        slot = START + monitor.WINDOW - monitor.STEP
        probe = Mock()
        save = monitor.save_attempt

        def interrupted_save(state, notes, index):
            save(state, notes, index)
            if index >= 0:
                raise InterruptedError("synthetic crash before probe")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.csv"
            state = path.with_suffix(".state.json")
            with path.open("w+b") as file, patch.object(monitor, "save_attempt", interrupted_save):
                with self.assertRaises(InterruptedError):
                    monitor.collect(file, START, META, probe, state_path=state, now=lambda: slot)
            with path.open("r+b") as file:
                monitor.collect(file, START, META, probe, state_path=state, now=lambda: slot)
            probe.assert_not_called()
            self.assertEqual(path.read_bytes(), monitor.HEADER)
            self.assertEqual(monitor.analyze(path.read_bytes(), START)["missing_intervals"], 17280)

    def test_crash_after_probe_before_append_with_clock_rollback(self):
        slot = START + monitor.WINDOW - monitor.STEP
        probe = Mock(return_value=monitor.Sample("1", "0.5", "synthetic"))
        durable = monitor.write_durable

        def interrupted_append(file, content):
            if content.startswith(b"2026-"):
                raise InterruptedError("synthetic crash before CSV append")
            durable(file, content)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.csv"
            state = path.with_suffix(".state.json")
            with path.open("w+b") as file, patch.object(monitor, "write_durable", interrupted_append):
                with self.assertRaises(InterruptedError):
                    monitor.collect(file, START, META, probe, state_path=state, now=lambda: slot)
            with path.open("r+b") as file:
                monitor.collect(file, START, META, probe, state_path=state,
                                now=lambda: slot - timedelta(seconds=1))
            probe.assert_called_once_with()
            self.assertEqual(path.read_bytes(), monitor.HEADER)

    def test_completed_slot_survives_restart_with_clock_rollback(self):
        slot = START + monitor.WINDOW - monitor.STEP
        probe = Mock(return_value=monitor.Sample("0", "", "synthetic"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.csv"
            state = path.with_suffix(".state.json")
            with path.open("w+b") as file:
                monitor.collect(file, START, META, probe, state_path=state, now=lambda: slot)
            before = path.read_bytes()
            with path.open("r+b") as file:
                monitor.collect(file, START, META, probe, state_path=state,
                                now=lambda: slot - timedelta(seconds=1))
            probe.assert_called_once_with()
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(monitor.analyze(before, START)["recorded_checks"], 1)

    def test_missing_sidecar_for_existing_journal_is_not_recreated(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile() as file:
            state = Path(directory) / "state.json"
            file.write(monitor.HEADER)
            probe = Mock()
            with self.assertRaisesRegex(ValueError, "no attempt state"):
                monitor.collect(file, START, META, probe, state_path=state)
            probe.assert_not_called()
            self.assertFalse(state.exists())
            file.seek(0)
            self.assertEqual(file.read(), monitor.HEADER)

    def test_resume_checks_target_and_interface_even_without_csv_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.csv"
            state = path.with_name(path.name + ".state.json")
            notes = (f"start={monitor.iso(START)};end={monitor.iso(START + monitor.WINDOW)};"
                     "method=icmp;interface=testwg;target=192.0.2.1;timeout_s=3")
            monitor.save_attempt(state, notes, 0)
            path.write_bytes(monitor.HEADER + b"incomplete")
            before = state.read_bytes(), path.read_bytes()
            for interface, address in (("testwg", "192.0.2.2"), ("otherwg", "192.0.2.1")):
                with self.subTest(interface=interface, address=address):
                    target = monitor.live_parameters(interface, address, 3)
                    runner = Mock(side_effect=[wireguard_link(interface), wireguard_route(interface)])
                    with self.assertRaisesRegex(ValueError, "parameters"):
                        monitor.monitor(path, START, interface, target, 3, run=runner)
                    self.assertEqual(runner.call_count, 2)
                    self.assertEqual((state.read_bytes(), path.read_bytes()), before)

    def test_journal_lock_also_protects_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.csv"
            state = path.with_name(path.name + ".state.json")
            path.write_bytes(monitor.HEADER + b"incomplete")
            monitor.save_attempt(state, META, 0)
            before = state.read_bytes(), path.read_bytes()
            target = monitor.live_parameters("testwg", "192.0.2.1", 3)
            runner = Mock(side_effect=[wireguard_link(), wireguard_route()])
            with path.open("rb") as owner:
                fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    monitor.monitor(path, START, "testwg", target, 3, run=runner)
            self.assertEqual(runner.call_count, 2)
            self.assertEqual((state.read_bytes(), path.read_bytes()), before)

    def test_invalid_48_hour_window_is_rejected_before_io(self):
        invalid = "9999-12-31T00:00:00Z"
        start = monitor.utc_timestamp(invalid)
        with self.assertRaisesRegex(ValueError, "48-hour UTC window"):
            monitor.analyze(monitor.HEADER, start)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.csv"
            target = monitor.live_parameters("testwg", "192.0.2.1", 3)
            runner = Mock()
            with self.assertRaisesRegex(ValueError, "48-hour UTC window"):
                monitor.monitor(path, start, "testwg", target, 3, run=runner)
            runner.assert_not_called()
            for args in (
                ["analyze"],
                ["monitor", "--allow-live", "--interface", "testwg",
                 "--target", "192.0.2.1", "--timeout", "3"],
            ):
                with redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit) as raised:
                    monitor.main(args + ["--log", str(path), "--start", invalid])
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("48-hour UTC window", stderr.getvalue())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_live_cli_requires_opt_in_and_does_not_create_log(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.csv"
            with patch.object(monitor.sys, "platform", "linux"), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    monitor.main(["monitor", "--log", str(path), "--start", monitor.iso(START),
                                  "--interface", "testwg", "--target", "192.0.2.1", "--timeout", "3"])
            self.assertEqual(raised.exception.code, 2)
            self.assertFalse(path.exists())

    def test_official_template_cannot_be_used_for_output(self):
        target = monitor.live_parameters("testwg", "192.0.2.1", 3)
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "template.csv"
            template.write_bytes(monitor.HEADER)
            alias = Path(directory) / "alias.csv"
            os.link(template, alias)
            with patch.object(monitor, "TEMPLATE", template), patch.object(monitor, "collect") as collect:
                for path in (template, alias):
                    with self.assertRaisesRegex(ValueError, "template"):
                        monitor.monitor(path, START, "testwg", target, 3)
                collect.assert_not_called()
            self.assertEqual(template.read_bytes(), monitor.HEADER)


if __name__ == "__main__":
    unittest.main()
