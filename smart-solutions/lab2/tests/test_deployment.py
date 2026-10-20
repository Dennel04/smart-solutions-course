import os
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from server.app import _development_bind


LAB2_ROOT = Path(__file__).resolve().parents[1]
DEPLOY = LAB2_ROOT / "deploy"


def test_development_server_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv("POST_OFFICE_BIND", raising=False)
    assert _development_bind() == "127.0.0.1"


def test_development_server_requires_explicit_lan_bind(monkeypatch):
    monkeypatch.setenv("POST_OFFICE_BIND", "0.0.0.0")
    assert _development_bind() == "0.0.0.0"
    monkeypatch.setenv("POST_OFFICE_BIND", "192.0.2.10")
    with pytest.raises(RuntimeError, match="POST_OFFICE_BIND"):
        _development_bind()


def test_firmware_guards_normal_missing_active_id_before_nvs_read():
    source = (LAB2_ROOT / "firmware" / "src" / "persistent_state.cpp").read_text()
    guard = 'preferences_.isKey("activeId")'
    read = 'preferences_.getString("activeId", "")'
    assert guard in source
    assert source.index(guard) < source.index(read)


def parse_example_environment():
    values = {}
    for raw_line in (DEPLOY / "env.example").read_text().splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def test_wsgi_entrypoint_loads_existing_app_with_production_environment(tmp_path):
    environment = os.environ.copy()
    environment.update(
        {
            "ATOM_API_KEY": "deployment-test-atom-key",
            "POST_OFFICE_USER": "deployment-test-user",
            "POST_OFFICE_PASSWORD": "deployment-test-password",
            "POST_OFFICE_DB": str(tmp_path / "post-office.sqlite3"),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", "from server.wsgi import app; assert app.name == 'server.app'"],
        cwd=LAB2_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_production_wsgi_fails_closed_without_secrets(tmp_path):
    environment = os.environ.copy()
    for key in ("ATOM_API_KEY", "POST_OFFICE_PASSWORD"):
        environment.pop(key, None)
    environment["POST_OFFICE_DB"] = str(tmp_path / "unused.sqlite3")
    result = subprocess.run(
        [sys.executable, "-c", "import server.wsgi"],
        cwd=LAB2_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "ATOM_API_KEY is required" in result.stderr


def test_environment_template_has_only_required_runtime_values():
    values = parse_example_environment()
    assert {"POST_OFFICE_USER", "POST_OFFICE_PASSWORD", "ATOM_API_KEY"} <= values.keys()
    assert values["POST_OFFICE_DB"] == "/var/lib/smart-solutions-lab2/post-office.sqlite3"
    assert values["POST_OFFICE_PASSWORD"].startswith("<")
    assert values["ATOM_API_KEY"].startswith("<")
    assert values["PUBLIC_HOSTNAME"] == "<TEAM_HOSTNAME>"
    assert not any("STATION" in key or "MG400" in key or "CAMERA" in key for key in values)


def test_systemd_uses_local_gunicorn_and_separate_writable_state():
    unit = (DEPLOY / "smart-solutions-lab2.service").read_text()
    assert "User=smart-solutions-lab2" in unit
    assert "server.wsgi:app" in unit
    assert "--bind 127.0.0.1:5001" in unit
    assert "EnvironmentFile=/etc/smart-solutions-lab2/env" in unit
    assert "ReadWritePaths=/var/lib/smart-solutions-lab2" in unit
    assert "0.0.0.0" not in unit


def test_caddy_proxies_only_the_local_post_office():
    caddyfile = (DEPLOY / "Caddyfile.example").read_text()
    assert "<TEAM_HOSTNAME>" in caddyfile
    assert "reverse_proxy 127.0.0.1:5001" in caddyfile
    assert "tls internal" not in caddyfile
    assert "/stream" not in caddyfile
    assert "/camera" not in caddyfile
    assert "station" not in caddyfile.lower()


def test_backup_script_uses_sqlite_backup_api(tmp_path):
    database = tmp_path / "live.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE evidence(value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES ('preserved')")
    env_file = tmp_path / "env"
    env_file.write_text(f"POST_OFFICE_DB={database}\n")
    backup_dir = tmp_path / "backups"
    environment = os.environ.copy()
    environment.update({"ENV_FILE": str(env_file), "BACKUP_DIR": str(backup_dir)})

    result = subprocess.run(
        ["sh", str(DEPLOY / "backup.sh")],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    backups = list(backup_dir.glob("post-office-*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("SELECT value FROM evidence").fetchone()[0] == "preserved"


def test_deployment_scripts_avoid_destructive_or_lockout_actions():
    scripts = "\n".join(
        (DEPLOY / name).read_text()
        for name in ("install.sh", "update.sh", "verify.sh", "backup.sh")
    )
    assert "reset --hard" not in scripts
    assert "PasswordAuthentication no" not in scripts
    assert "ufw enable" not in scripts
    assert "pio run -t upload" not in scripts


def test_verify_checks_production_file_and_proxy_boundaries():
    verify = (DEPLOY / "verify.sh").read_text()
    assert "stat -c '%U:%G'" in verify
    assert "root:root" in verify
    assert "EXPECTED_DB_PATH=/var/lib/smart-solutions-lab2/post-office.sqlite3" in verify
    assert 'caddy validate --config "$CADDY_FILE"' in verify
    assert "127\\.0\\.0\\.1:5001" in verify
    assert "Caddy has no additional public reverse_proxy target" in verify


@pytest.fixture
def mock_update(tmp_path):
    """Run a copy with a temp base and fake OS tools; no root or network access."""
    base = tmp_path / "deployment"
    lab = base / "app" / "smart-solutions" / "lab2"
    deploy = lab / "deploy"
    deploy.mkdir(parents=True)
    (base / "app" / ".git").mkdir()
    venv_bin = base / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    log = tmp_path / "calls.jsonl"
    count = tmp_path / "curl-count"
    source = (DEPLOY / "update.sh").read_text()
    original_base = "BASE_DIR=/opt/smart-solutions-lab2"
    assert source.count(original_base) == 1
    script = deploy / "update.sh"
    script.write_text(source.replace(original_base, f'BASE_DIR="{base}"'))

    mock_tool = f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
with open(os.environ["MOCK_UPDATE_LOG"], "a") as output:
    output.write(json.dumps([name] + sys.argv[1:]) + "\\n")
if name == "id":
    print("0")
elif name == "curl":
    count_path = Path(os.environ["MOCK_CURL_COUNT"])
    attempt = int(count_path.read_text()) + 1 if count_path.exists() else 1
    count_path.write_text(str(attempt))
    if attempt <= int(os.environ["MOCK_READY_AFTER"]):
        print("000", end="")
        sys.exit(28)
    print(os.environ["MOCK_HTTP_CODE"], end="")
elif name == "verify.sh":
    sys.exit(int(os.environ["MOCK_VERIFY_EXIT"]))
'''
    for tool in [*(mock_bin / name for name in ("id", "git", "systemctl", "curl", "sleep")),
                 venv_bin / "python", deploy / "backup.sh", deploy / "verify.sh"]:
        tool.write_text(mock_tool)
        tool.chmod(0o755)

    def run(*, ready_after=0, http_code="200", verify_exit=0):
        env = os.environ.copy()
        env.update({
            "PATH": str(mock_bin) + os.pathsep + env.get("PATH", ""),
            "MOCK_UPDATE_LOG": str(log), "MOCK_CURL_COUNT": str(count),
            "MOCK_READY_AFTER": str(ready_after), "MOCK_HTTP_CODE": http_code,
            "MOCK_VERIFY_EXIT": str(verify_exit),
        })
        result = subprocess.run(
            ["/bin/sh", str(script), "origin/main"], env=env,
            capture_output=True, text=True, timeout=10, check=False,
        )
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        return result, calls

    return run


@pytest.mark.parametrize("ready_after", [0, 2, 14])
def test_update_waits_until_health_is_ready_before_full_verification(mock_update, ready_after):
    result, calls = mock_update(ready_after=ready_after)
    assert result.returncode == 0, result.stderr
    names = [call[0] for call in calls]
    assert names.count("curl") == ready_after + 1
    assert names.count("sleep") == ready_after
    assert names.count("verify.sh") == 1
    assert names.index("backup.sh") < names.index("systemctl") < names.index("curl")
    assert names[-1] == "verify.sh"
    repo = next(call[2] for call in calls if call[0] == "git")
    assert ["git", "-C", repo, "merge", "--ff-only", "origin/main"] in calls
    assert ["systemctl", "restart", "smart-solutions-lab2"] in calls
    for call in (call for call in calls if call[0] == "curl"):
        assert call[-1] == "http://127.0.0.1:5001/health"
        assert call[call.index("--connect-timeout") + 1] == "1"
        assert call[call.index("--max-time") + 1] == "1"
        assert call[call.index("--noproxy") + 1] == "*"
    assert "running full deployment verification" in result.stdout


@pytest.mark.parametrize("ready_after,http_code", [(100, "200"), (0, "502"), (0, "301")])
def test_update_times_out_without_running_verify_on_unready_health(
    mock_update, ready_after, http_code
):
    result, calls = mock_update(ready_after=ready_after, http_code=http_code)
    assert result.returncode != 0
    assert sum(call[0] == "curl" for call in calls) == 15
    assert sum(call[0] == "sleep" for call in calls) == 14
    assert not any(call[0] == "verify.sh" for call in calls)
    assert "did not become ready" in result.stderr


def test_update_keeps_full_verification_failure_fatal(mock_update):
    result, calls = mock_update(verify_exit=7)
    assert calls[-1][0] == "verify.sh"
    assert result.returncode == 7
