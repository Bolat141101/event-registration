#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${CORE_DB:?CORE_DB is required}"
: "${CORE_USER:?CORE_USER is required}"
: "${CORE_PASSWORD:?CORE_PASSWORD is required}"
: "${NOTIFICATIONS_DB:?NOTIFICATIONS_DB is required}"
: "${NOTIFICATIONS_USER:?NOTIFICATIONS_USER is required}"
: "${NOTIFICATIONS_PASSWORD:?NOTIFICATIONS_PASSWORD is required}"

if [ "$CORE_DB" = "$NOTIFICATIONS_DB" ] || [ "$CORE_USER" = "$NOTIFICATIONS_USER" ] ||
   [ "$CORE_USER" = "$PGUSER" ] || [ "$NOTIFICATIONS_USER" = "$PGUSER" ]; then
    echo "Bootstrap requires distinct databases and distinct non-admin application roles" >&2
    exit 1
fi

# psql quotes identifiers/literals with format(%I/%L); never interpolate SQL in shell.
# This client runs on every requested bootstrap, including an existing PGDATA volume.
psql -X --set=ON_ERROR_STOP=1 --dbname=postgres \
    --set=core_db="$CORE_DB" --set=core_user="$CORE_USER" --set=core_password="$CORE_PASSWORD" \
    --set=notifications_db="$NOTIFICATIONS_DB" --set=notifications_user="$NOTIFICATIONS_USER" \
    --set=notifications_password="$NOTIFICATIONS_PASSWORD" --file=/bootstrap/databases.sql

configure_schema() {
    psql -X --set=ON_ERROR_STOP=1 --dbname="$1" --set=app_user="$2" --file=/bootstrap/schema.sql
}
configure_schema "$CORE_DB" "$CORE_USER"
configure_schema "$NOTIFICATIONS_DB" "$NOTIFICATIONS_USER"
echo "Application databases and role isolation are ready"
