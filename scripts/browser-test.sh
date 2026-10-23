#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export COMPOSE_PROJECT_NAME="${BROWSER_TEST_PROJECT:-event-registration-relay-check-ui-local}"
case "$COMPOSE_PROJECT_NAME" in event-registration-relay-check-ui-*) ;; *) echo 'Use a separate event-registration-relay-check-ui-* project.' >&2; exit 1 ;; esac
export COMPOSE_ENV_FILES=.env.example COMPOSE_PROFILES=test
export ORGANIZER_TOKEN=local_organizer_token_change_me_32_chars_minimum
export POSTGRES_PORT=0 FRONTEND_PORT=0 MAILPIT_PORT=0
compose() { docker compose -f compose.yaml -f compose.browser-test.yaml "$@"; }
urls() {
  printf 'Site: http://%s\n' "$(compose port frontend 80)"
  printf 'Mailpit: http://%s\n' "$(compose port mailpit 8025)"
}
case "${1:-start}" in
  start)
    # Retain the published site port on rebuild: frozen email links must stay valid.
    existing_site="$(compose port frontend 80 2>/dev/null || true)"
    if [ -n "$existing_site" ]; then export FRONTEND_PORT="${existing_site##*:}"; fi
    compose config --quiet
    compose build api notifications frontend
    # No sender may freeze new MIME with a stale/random frontend origin.
    compose stop notifications-sender
    compose up --no-build -d --wait --wait-timeout 120 db mailpit migrate api worker frontend notifications-migrate notifications
    export PUBLIC_APP_URL="http://$(compose port frontend 80)"
    compose up --no-build --no-deps -d --wait --wait-timeout 60 notifications-sender
    urls
    ;;
  urls) urls ;;
  stop) compose down --remove-orphans ;;
  test)
    # Obtain targets from this exact Compose project; do not accept arbitrary URLs.
    export E2E_BASE_URL="http://$(compose port frontend 80)"
    export E2E_MAILPIT_URL="http://$(compose port mailpit 8025)"
    export E2E_ISOLATED_PROJECT="$COMPOSE_PROJECT_NAME"
    export E2E_ORGANIZER_KEY=local_organizer_token_change_me_32_chars_minimum
    cd frontend
    npm ci
    npm run format:check
    npm run test
    npm run build
    if [ -z "${PLAYWRIGHT_CHROMIUM_EXECUTABLE:-}" ]; then npx playwright install chromium; fi
    npm run test:e2e
    ;;
  *) echo 'Usage: scripts/browser-test.sh [start|urls|test|stop]' >&2; exit 1 ;;
esac
