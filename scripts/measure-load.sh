#!/bin/sh
# Never run against the main project. Before/after must start with empty tmpfs databases.
set -eu
cd "$(dirname "$0")/.."
: "${BROWSER_TEST_PROJECT:?Choose a new event-registration-relay-check-ui-* project}"
case "$BROWSER_TEST_PROJECT" in event-registration-relay-check-ui-*) ;; *) exit 1 ;; esac
export COMPOSE_PROJECT_NAME="$BROWSER_TEST_PROJECT" COMPOSE_ENV_FILES=.env.example COMPOSE_PROFILES=test
export POSTGRES_PORT=0 FRONTEND_PORT=0 MAILPIT_PORT=0
compose() { docker compose -f compose.yaml -f compose.browser-test.yaml "$@"; }
if [ -n "$(compose ps -q db 2>/dev/null)" ]; then echo 'Use a fresh project with no existing DB container.' >&2; exit 1; fi
cleanup() {
  diagnostics="${LOAD_DIAGNOSTICS_DIR:-/tmp/maddevs-load-diagnostics}"
  mkdir -p "$diagnostics"
  compose logs --no-color --tail=200 api worker notifications-sender > "$diagnostics/$BROWSER_TEST_PROJECT.log" 2>&1 || true
  compose down --remove-orphans
}
trap cleanup EXIT HUP INT TERM
scripts/browser-test.sh start
compose stop worker notifications-sender
load_status=0
compose run --rm --no-deps -T -e LOAD_PROJECT="$BROWSER_TEST_PROJECT" -e LOAD_LABEL="${LOAD_LABEL:-sample}" \
  -e LOAD_VISITORS="${LOAD_VISITORS:-100}" worker python - < infrastructure/checks/load_probe.py || load_status=$?
compose run --rm --no-deps -T -e LOAD_PROJECT="$BROWSER_TEST_PROJECT" -e LOAD_LABEL="${LOAD_LABEL:-sample}" worker python - < infrastructure/checks/explain_probe.py
export PUBLIC_APP_URL="http://$(compose port frontend 80)"
export LOAD_DRAIN_STARTED="$(python3 -c 'import time; print(time.time())')"
compose up --no-build --no-deps -d worker notifications-sender
compose run --rm --no-deps -T -e LOAD_PROJECT="$BROWSER_TEST_PROJECT" -e LOAD_DRAIN_STARTED worker python - < infrastructure/checks/delivery_probe.py

exit "$load_status"
