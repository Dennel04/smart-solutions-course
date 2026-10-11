#!/bin/sh
set -eu

SERVICE_USER=smart-solutions-lab2
BASE_DIR=/opt/smart-solutions-lab2
REPO_DIR=$BASE_DIR/app
LAB_DIR=$REPO_DIR/smart-solutions/lab2
VENV_DIR=$BASE_DIR/venv
DATA_DIR=/var/lib/smart-solutions-lab2
CONFIG_DIR=/etc/smart-solutions-lab2
ENV_FILE=$CONFIG_DIR/env
BACKUP_DIR=/var/backups/smart-solutions-lab2
UNIT_FILE=/etc/systemd/system/smart-solutions-lab2.service

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run install.sh as root on the intended Ubuntu droplet." >&2
    exit 1
fi

for command in git python3 systemctl; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "ERROR: required command is missing: $command" >&2
        exit 1
    fi
done

if [ ! -f "$LAB_DIR/server/requirements.txt" ]; then
    echo "ERROR: clone the repository to $REPO_DIR before running this script." >&2
    exit 1
fi

if ! getent group "$SERVICE_USER" >/dev/null 2>&1; then
    groupadd --system "$SERVICE_USER"
fi
if ! getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --gid "$SERVICE_USER" --home-dir /nonexistent \
        --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -o root -g root -m 755 "$BASE_DIR"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 750 "$DATA_DIR"
install -d -o root -g root -m 700 "$CONFIG_DIR" "$BACKUP_DIR"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$LAB_DIR/server/requirements.txt"

install -o root -g root -m 644 \
    "$LAB_DIR/deploy/smart-solutions-lab2.service" "$UNIT_FILE"
if [ ! -f "$ENV_FILE" ]; then
    install -o root -g root -m 600 "$LAB_DIR/deploy/env.example" "$ENV_FILE"
    echo "CREATED: $ENV_FILE still contains placeholders; edit it before start."
else
    chmod 600 "$ENV_FILE"
fi

systemctl daemon-reload

echo "Prepared service files without starting the application."
echo "Next: edit $ENV_FILE, install/configure Caddy, then run:"
echo "  systemctl enable --now smart-solutions-lab2"
echo "  $LAB_DIR/deploy/verify.sh"
