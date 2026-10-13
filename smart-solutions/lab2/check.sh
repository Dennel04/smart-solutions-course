#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="$(command -v python3)"
else
    echo "ERROR: Python 3 is required." >&2
    exit 1
fi

if command -v pio >/dev/null 2>&1; then
    PIO_CMD="$(command -v pio)"
elif command -v platformio >/dev/null 2>&1; then
    PIO_CMD="$(command -v platformio)"
elif [[ -x "${HOME}/.platformio-cli-venv/bin/platformio" ]]; then
    PIO_CMD="${HOME}/.platformio-cli-venv/bin/platformio"
else
    echo "ERROR: PlatformIO is required (expected pio or platformio in PATH)." >&2
    exit 1
fi

echo "[1/5] Python tests"
cd "$SCRIPT_DIR"
"$PYTHON_CMD" -m pytest -q

echo "[2/5] Python compile check"
PYCACHE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/smart-solutions-lab2-pycache.XXXXXX")"
trap 'rm -rf -- "$PYCACHE_DIR"' EXIT
PYTHONPYCACHEPREFIX="$PYCACHE_DIR" "$PYTHON_CMD" -m compileall -q server src tests

echo "[3/5] Software E2E"
"$PYTHON_CMD" -m src.e2e_demo

echo "[4/5] Atom native tests and build"
cd "$SCRIPT_DIR/firmware"
"$PIO_CMD" test -e native
"$PIO_CMD" run -e atoms3r

echo "[5/5] XIAO native tests and build"
cd "$SCRIPT_DIR/firmware-xiao-camera"
"$PIO_CMD" test -e native
"$PIO_CMD" run -e seeed_xiao_esp32s3

echo "All software-only regression checks passed."
