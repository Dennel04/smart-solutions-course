"""Host-only tests. All input is synthetic; no serial or network is opened."""
import configparser
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

FW = Path(__file__).resolve().parents[1] / "firmware"


def module(name):
    spec = importlib.util.spec_from_file_location(name, FW / "tools" / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.fixture(scope="module")
def protocol(tmp_path_factory):
    folder = tmp_path_factory.mktemp("health-host")
    source = folder / "protocol.cpp"
    source.write_text('''#include <iostream>
#include <string>
#include "health_only_protocol.h"
int main(int argc,char**argv){std::string s((std::istreambuf_iterator<char>(std::cin)),{});
std::vector<char> b(s.begin(),s.end());b.push_back(0);
healthonly::Credentials c;
bool ok=argv[1][0]=='f'?healthonly::parseFrame(b.data(),"0123456789abcdef",c):
healthonly::responseValid(b.data(),s.size());
healthonly::wipe(b.data(),b.size());healthonly::wipe(&c,sizeof(c));return ok?0:1;}'''.replace(
        '#include <string>', '#include <string>\n#include <vector>'))
    compiler = shutil.which("c++")
    assert compiler, "Host compiler required for actual protocol tests"
    library = FW / ".pio/libdeps/atoms3r/ArduinoJson/src"
    assert library.is_dir(), "Run existing bench dependency build first"
    binary = folder / "protocol"
    subprocess.run([compiler, "-std=c++17", "-I", str(FW / "include"),
                    "-I", str(library), str(source), "-o", str(binary)],
                   check=True, capture_output=True)

    def run(data, kind="frame"):
        return subprocess.run([str(binary), kind], input=data.encode(),
                              capture_output=True).returncode == 0
    return run


def frame(**updates):
    data = dict(action="health_once", challenge="0123456789abcdef", ssid="synthetic-only",
                password="synthetic-pass", utc=1792756800, confirm=True)
    data.update(updates)
    return json.dumps(data)


def response(body='{"ok":true,"service":"lab2-post-office"}', status="200 OK", **headers):
    fields = {"Content-Type": "application/json", "Content-Length": str(len(body.encode()))}
    fields.update(headers)
    return f"HTTP/1.1 {status}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in fields.items()) + "\r\n" + body


def test_actual_protocol_accepts_only_explicit_frame(protocol):
    assert protocol(frame())
    assert protocol(frame(ssid="s"*32, password="p"*63))


@pytest.mark.parametrize("updates", [
    {"ssid":""}, {"ssid":"x"*33}, {"ssid":"a\nb"}, {"password":"short"},
    {"password":"x"*64}, {"password":"synthetic\0bad"}, {"ssid":"võrk"},
    {"action":"poll"}, {"challenge":"fedcba9876543210"}, {"confirm":False},
    {"utc":0}, {"utc":True}, {"utc":1792756800.5}, {"utc":"1792756800"},
    {"job":"letter"}, {"url":"https://other.invalid/"},
])
def test_actual_protocol_rejects_unsafe_input(protocol, updates):
    assert not protocol(frame(**updates))


@pytest.mark.parametrize("data", ["", "{}", "{", "[]", "HELLO", frame()+"junk", frame()[:-1]])
def test_incomplete_or_extra_serial_input(protocol, data):
    assert not protocol(data)


def test_actual_response_parser_accepts_health(protocol):
    assert protocol(response(), "response")
    assert protocol(response('{ "service": "lab2-post-office", "ok": true }'), "response")


@pytest.mark.parametrize("body", ["", "{", "null", "[]", '{"ok":false,"service":"lab2-post-office"}',
    '{"ok":1,"service":"lab2-post-office"}', '{"ok":true,"service":"other"}',
    '{"ok":true,"service":"lab2-post-office","job":{}}',
    '{"ok":true,"service":"lab2-post-office\\u0000x"}',
    '{"ok":true,"service":"lab2-post-office"}junk'])
def test_actual_response_rejects_invalid_json(protocol, body):
    assert not protocol(response(body), "response")


@pytest.mark.parametrize("status", ["301 Moved", "302 Found", "401 Unauthorized", "500 Error", "2000 Bad"])
def test_redirect_and_non_200_stop(protocol, status):
    assert not protocol(response(status=status), "response")


@pytest.mark.parametrize("headers", [{"Content-Length":"0"}, {"Content-Length":"999999999999999999999"},
    {"Transfer-Encoding":"chunked"}, {"Content-Type":"text/html"}, {"Content-Type":"application/jsonx"}])
def test_bad_framing_is_rejected(protocol, headers):
    assert not protocol(response(**headers), "response")


def test_exact_environment_and_no_normal_startup():
    config = configparser.ConfigParser(interpolation=None)
    config.read(FW / "platformio.ini")
    assert config["platformio"]["default_envs"] == "atoms3r"
    health = config["env:atoms3r_health"]
    assert "-DHEALTH_ONLY=1" in health["build_flags"].split()
    assert "${env:atoms3r.build_flags}" in health["build_flags"]
    assert health["build_src_filter"].split() == ["-<*>", "+<health_only_main.cpp>", "+<bench_nvs_guard.cpp>"]
    source = (FW / "src/health_only_main.cpp").read_text()
    assert source.startswith("// Excluded")
    assert "#if defined(HEALTH_ONLY) && HEALTH_ONLY == 1" in source
    for value in ("init.nvs_enable = 0", "WIFI_STORAGE_RAM", "WIFI_MODE_STA",
                  "esp_log_level_set", "client.setHandshakeTimeout(8)", "client.setTimeout(5)",
                  "mbedtls_x509_crt_verify", "client.getPeerCertificate()", "HEALTH ONLY"):
        assert value in source
    for value in ("PostOfficeClient", "PersistentState", "SettingsStore", "Preferences",
                  "StationBridge", "setInsecure", "configTime", "WiFi.begin", "WIFI_MODE_AP",
                  "Serial.printf", "recoverAmbiguousClaim"):
        assert value not in source
    assert source.count("client.write(") == 1
    assert source.count("esp_wifi_connect()") == 1
    setup = source.split("void setup()", 1)[1].split("void loop()", 1)[0]
    assert "esp_wifi" not in setup and "HealthIo" not in setup
    assert "gate.take(); stopped = true;" in source
    assert "millis()-inputStarted >= 10000" in source
    assert "millis()-helloAt >= 60000" in source


class FakePort:
    def __init__(self, lines):
        self.lines = iter(lines)
        self.writes = []
    def reset_input_buffer(self):
        pass
    def write(self, data):
        self.writes.append(data)
        return len(data)
    def readline(self, limit):
        return next(self.lines, b"")


def ticker():
    count = iter(range(200))
    return lambda: next(count)


def test_helper_authorizes_once_and_never_echoes_secrets():
    helper = module("health_only_session")
    port = FakePort([b"# HEALTH CHALLENGE 0123456789abcdef\n", b"synthetic-pass\n",
                     b"# HEALTH WIFI CONNECTED\n", b"# HEALTH TLS VERIFIED\n", b"# HEALTH HEALTH OK\n"])
    output = []
    assert helper.session(port, "synthetic-only", "synthetic-pass", clock=ticker(),
                          utc=lambda:1792756800, display=output.append)
    assert len(port.writes) == 2
    assert port.writes[0] == b"HELLO\n"
    assert "synthetic-pass" not in repr(output)


@pytest.mark.parametrize("state", [b"# HEALTH TLS ERROR", b"# HEALTH CERT OR UTC ERROR", b"# HEALTH HEALTH ERROR"])
def test_helper_never_retries_error(state):
    helper = module("health_only_session")
    port = FakePort([b"# HEALTH CHALLENGE 0123456789abcdef", state])
    assert not helper.session(port,"synthetic-only","synthetic-pass",clock=ticker(),utc=lambda:1792756800,display=lambda _:None)
    assert len(port.writes) == 2


def test_helper_reconnect_or_reset_without_challenge_cannot_authorize():
    helper = module("health_only_session")
    port = FakePort([b"# HEALTH WAITING FOR USB"])
    with pytest.raises(RuntimeError, match="No health-only challenge"):
        helper.session(port,"synthetic-only","synthetic-pass",clock=ticker())
    assert port.writes == [b"HELLO\n"]


def test_helper_timeout_does_not_retry():
    helper = module("health_only_session")
    port = FakePort([b"# HEALTH CHALLENGE 0123456789abcdef"])
    with pytest.raises(RuntimeError, match="result timeout"):
        helper.session(port,"synthetic-only","synthetic-pass",clock=ticker(),utc=lambda:1792756800)
    assert len(port.writes) == 2


def test_helper_has_no_reset_or_network_interface():
    source = (FW / "tools/health_only_session.py").read_text()
    for forbidden in ("requests.", "urllib", "socket.", "setDTR", "setRTS"):
        assert forbidden not in source
    assert "port.dtr = False" in source and "port.rts = False" in source
    assert 'getpass.getpass("Wi-Fi password' in source
    assert 'warnings.simplefilter("error", getpass.GetPassWarning)' in source


def test_artifact_verifier_rejects_wrong_marker():
    verifier = module("verify_health_only")
    with pytest.raises(ValueError, match="marker"):
        verifier.inspect(b"synthetic", "", "")


def artifact_fixture():
    verifier = module("verify_health_only")
    image = verifier.MARKER + b" GET /health HTTP/1.1 narva2.roboarena.org -----BEGIN CERTIFICATE-----"
    symbols = "".join(f"00000000 T __wrap_{name}\n" for name in
        ("nvs_flash_init", "nvs_flash_init_partition", "nvs_open", "nvs_open_from_partition"))
    symbols += "\n".join(("mbedtls_x509_crt_verify", "mbedtls_ssl_set_hostname", "mbedtls_x509_crt_parse",
                           "healthonly::checkCertificate", "healthonly::responseValid"))
    sdk = "CONFIG_MBEDTLS_SSL_KEEP_PEER_CERTIFICATE=y\nCONFIG_ESP_COREDUMP_ENABLE_TO_FLASH=y\n"
    return verifier, image, symbols, sdk


@pytest.mark.parametrize("bad", ["postoffice::poll", "Preferences::begin", "StationBridge",
                                "configTime", "nvs_open"])
def test_verifier_rejects_live_or_original_nvs_symbols(bad):
    verifier, image, symbols, sdk = artifact_fixture()
    with pytest.raises(ValueError):
        verifier.inspect(image, symbols + f"\n00000000 T {bad}\n", sdk)


def test_verifier_requires_peer_chain_and_reports_coredump():
    verifier, image, symbols, sdk = artifact_fixture()
    assert verifier.inspect(image, symbols, sdk) is True
    with pytest.raises(ValueError, match="retain"):
        verifier.inspect(image, symbols, "")
    with pytest.raises(ValueError, match="verification"):
        verifier.inspect(image, symbols.replace("healthonly::checkCertificate", "removed"), sdk)


def test_new_entry_point_is_empty_in_existing_environments():
    compiler = shutil.which("c++")
    assert compiler
    # No SDK include directories: preprocessing must remove the ENTIRE new file.
    for flag in ("-DBENCH_MODE=1", "-DBENCH_MODE=0"):
        subprocess.run([compiler, "-std=c++11", "-fsyntax-only", flag,
                        str(FW / "src/health_only_main.cpp")], check=True, capture_output=True)
