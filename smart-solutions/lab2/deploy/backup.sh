#!/bin/sh
set -eu

ENV_FILE=${ENV_FILE:-/etc/smart-solutions-lab2/env}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/smart-solutions-lab2}

if [ ! -r "$ENV_FILE" ]; then
    echo "ERROR: environment file is not readable: $ENV_FILE" >&2
    exit 1
fi

DB_PATH=$(sed -n 's/^POST_OFFICE_DB=//p' "$ENV_FILE" | tail -n 1)
case "$DB_PATH" in
    /*) ;;
    *)
        echo "ERROR: POST_OFFICE_DB must be an absolute path." >&2
        exit 1
        ;;
esac

if [ ! -f "$DB_PATH" ]; then
    echo "SKIP: database does not exist yet: $DB_PATH"
    exit 0
fi

install -d -m 700 "$BACKUP_DIR"
umask 077
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
DESTINATION=$BACKUP_DIR/post-office-$TIMESTAMP.sqlite3

python3 - "$DB_PATH" "$DESTINATION" <<'PY'
import sqlite3
import sys

source_path, destination_path = sys.argv[1:]
source = sqlite3.connect(source_path)
destination = sqlite3.connect(destination_path)
try:
    source.backup(destination)
    result = destination.execute("PRAGMA quick_check").fetchone()[0]
    if result != "ok":
        raise RuntimeError("backup quick_check failed: " + result)
finally:
    destination.close()
    source.close()
PY

echo "SQLite backup created: $DESTINATION"
