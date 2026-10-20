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

# systemd active does not mean Gunicorn has opened its listening socket yet.
# At most 15 one-second requests and 14 one-second pauses (about 30 seconds).
HEALTH_URL=http://127.0.0.1:5001/health
HEALTH_ATTEMPTS=15
attempt=1
echo "Waiting for the local post-office health endpoint..."
while :; do
    if health_code=$(curl --fail --silent --show-error --noproxy '*' \
        --connect-timeout 1 --max-time 1 --output /dev/null \
        --write-out '%{http_code}' "$HEALTH_URL" 2>/dev/null) && \
        [ "$health_code" = "200" ]; then
        echo "Local post-office is ready; running full deployment verification."
        break
    fi
    if [ "$attempt" -ge "$HEALTH_ATTEMPTS" ]; then
        echo "ERROR: local post-office did not become ready after $HEALTH_ATTEMPTS attempts; update verification aborted." >&2
        exit 1
    fi
    sleep 1
    attempt=$((attempt + 1))
done

"$LAB_DIR/deploy/verify.sh"
