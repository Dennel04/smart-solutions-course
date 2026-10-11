#!/bin/sh
set -eu

BASE_DIR=/opt/smart-solutions-lab2
REPO_DIR=$BASE_DIR/app
LAB_DIR=$REPO_DIR/smart-solutions/lab2
VENV_DIR=$BASE_DIR/venv

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run update.sh as root on the intended droplet." >&2
    exit 1
fi
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <explicit-git-ref>" >&2
    echo "Example after review: $0 origin/main" >&2
    exit 2
fi
REVISION=$1

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "ERROR: expected Git checkout at $REPO_DIR" >&2
    exit 1
fi
if [ -n "$(git -C "$REPO_DIR" status --porcelain)" ]; then
    echo "ERROR: checkout has local changes; update aborted." >&2
    exit 1
fi

"$LAB_DIR/deploy/backup.sh"
git -C "$REPO_DIR" fetch --prune origin
git -C "$REPO_DIR" merge --ff-only "$REVISION"
"$VENV_DIR/bin/python" -m pip install -r "$LAB_DIR/server/requirements.txt"
systemctl restart smart-solutions-lab2
"$LAB_DIR/deploy/verify.sh"
