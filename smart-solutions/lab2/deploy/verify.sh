#!/bin/sh
set -eu

SERVICE=smart-solutions-lab2
SERVICE_USER=smart-solutions-lab2
ENV_FILE=${ENV_FILE:-/etc/smart-solutions-lab2/env}
CADDY_FILE=${CADDY_FILE:-/etc/caddy/Caddyfile}
INTERNAL_URL=http://127.0.0.1:5001/health
EXPECTED_DB_PATH=/var/lib/smart-solutions-lab2/post-office.sqlite3
FAILURES=0

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*" >&2; FAILURES=$((FAILURES + 1)); }
skip() { echo "SKIP: $*"; }

if [ "$(uname -s)" != "Linux" ] || ! command -v systemctl >/dev/null 2>&1; then
    skip "systemd deployment checks apply only on the Ubuntu droplet"
    exit 0
fi

if [ ! -f "$ENV_FILE" ]; then
    fail "missing environment file: $ENV_FILE"
else
    MODE=$(stat -c '%a' "$ENV_FILE")
    [ "$MODE" = "600" ] && pass "environment file mode is 600" || \
        fail "environment file mode is $MODE, expected 600"
    OWNER=$(stat -c '%U:%G' "$ENV_FILE")
    [ "$OWNER" = "root:root" ] && pass "environment file owner is root:root" || \
        fail "environment file owner is $OWNER, expected root:root"
    for key in POST_OFFICE_USER POST_OFFICE_PASSWORD ATOM_API_KEY \
        POST_OFFICE_DB PUBLIC_HOSTNAME; do
        grep -q "^$key=..*" "$ENV_FILE" || fail "missing required setting: $key"
    done
    if grep -Eq '^[A-Z0-9_]+=<[^>]+>$' "$ENV_FILE"; then
        fail "environment file still contains placeholders"
    fi

    DB_PATH=$(sed -n 's/^POST_OFFICE_DB=//p' "$ENV_FILE" | tail -n 1)
    if [ "$DB_PATH" = "$EXPECTED_DB_PATH" ]; then
        pass "database uses the expected persistent path"
    else
        fail "database path is not the expected persistent path"
    fi
    if [ -n "$DB_PATH" ]; then
        DB_DIR=$(dirname "$DB_PATH")
        if id "$SERVICE_USER" >/dev/null 2>&1 && \
            runuser -u "$SERVICE_USER" -- test -w "$DB_DIR"; then
            pass "database directory is writable by the service user"
        else
            fail "database directory is not writable by the service user"
        fi
    fi
fi

if systemctl is-active --quiet "$SERVICE"; then
    pass "$SERVICE service is active"
else
    fail "$SERVICE service is not active"
fi

if curl --fail --silent --show-error "$INTERNAL_URL" >/dev/null; then
    pass "localhost health endpoint responds"
else
    fail "localhost health endpoint failed"
fi

if command -v ss >/dev/null 2>&1; then
    LISTENERS=$(ss -ltnH | awk '$4 ~ /:5001$/ {print $4}')
    if printf '%s\n' "$LISTENERS" | grep -Eq '(^|\[)0\.0\.0\.0:5001$|^\[::\]:5001$'; then
        fail "Gunicorn port is publicly bound"
    elif printf '%s\n' "$LISTENERS" | grep -q '127.0.0.1:5001$'; then
        pass "Gunicorn listens only on IPv4 loopback"
    else
        fail "expected loopback listener 127.0.0.1:5001 was not found"
    fi
else
    skip "ss command unavailable; socket binding not inspected"
fi

if systemctl is-active --quiet caddy; then
    pass "Caddy service is active"
else
    fail "Caddy service is not active"
fi

if [ ! -f "$CADDY_FILE" ]; then
    fail "missing Caddy configuration: $CADDY_FILE"
elif ! command -v caddy >/dev/null 2>&1; then
    fail "caddy command is unavailable; configuration was not validated"
elif caddy validate --config "$CADDY_FILE" >/dev/null 2>&1; then
    pass "Caddy configuration validates"
else
    fail "Caddy configuration validation failed"
fi

if [ -f "$CADDY_FILE" ] && grep -Eq \
    '^[[:space:]]*reverse_proxy[[:space:]]+127\.0\.0\.1:5001[[:space:]]*$' \
    "$CADDY_FILE"; then
    pass "Caddy proxies to the loopback post-office backend"
else
    fail "Caddy loopback post-office reverse_proxy was not found"
fi

if [ -f "$CADDY_FILE" ]; then
    UNEXPECTED_PROXIES=$(grep -E '^[[:space:]]*reverse_proxy[[:space:]]+' \
        "$CADDY_FILE" | grep -Ev \
        '^[[:space:]]*reverse_proxy[[:space:]]+127\.0\.0\.1:5001[[:space:]]*$' || true)
    if [ -z "$UNEXPECTED_PROXIES" ]; then
        pass "Caddy has no additional public reverse_proxy target"
    else
        fail "Caddy contains an unexpected reverse_proxy target"
    fi
fi

if [ -f "$ENV_FILE" ]; then
    PUBLIC_HOST_VALUE=$(sed -n 's/^PUBLIC_HOSTNAME=//p' "$ENV_FILE" | tail -n 1)
    case "$PUBLIC_HOST_VALUE" in
        ""|*'<'*|*'>'*) skip "public hostname is not configured" ;;
        *)
            if curl --fail --silent --show-error \
                "https://$PUBLIC_HOST_VALUE/health" >/dev/null; then
                pass "public HTTPS health endpoint and certificate validate"
            else
                fail "public HTTPS health endpoint failed"
            fi
            ;;
    esac
fi

[ "$FAILURES" -eq 0 ] || exit 1
