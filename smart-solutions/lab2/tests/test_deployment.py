import os
from pathlib import Path
import sqlite3
import subprocess
import sys


LAB2_ROOT = Path(__file__).resolve().parents[1]
DEPLOY = LAB2_ROOT / "deploy"


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
