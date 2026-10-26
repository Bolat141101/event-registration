# Core and Notifications infrastructure

The approved split uses two FastAPI/AsyncSession/asyncpg services and one PostgreSQL instance with **separate databases and ordinary roles**. This document describes current infrastructure, not the historical stage before HTTP relay/SMTP were implemented.

## Containers and data ownership

| Service | Responsibility |
| --- | --- |
| db | PostgreSQL; persistent main storage, tmpfs in guarded test projects |
| db-bootstrap | Repeatable administrative creation/role isolation, no row deletion |
| migrate | Core Alembic upgrade, then exit0 |
| api | Existing asynchronous business API and public SSE |
| worker | Core outbox HTTP relay |
| notifications-migrate | Independent Notifications Alembic upgrade, then exit0 |
| notifications | Protected durable internal inbox and health |
| notifications-sender | MIME preparation and async SMTP submission |
| frontend | Built React application and Nginx proxy |
| mailpit | Local SMTP emulator and inbox, not an external mail provider |

Core's default database is event_registration with role core_app. Notifications uses event_notifications with role notifications_app. The administrator events is for bootstrap, not API traffic. Application roles have no superuser/createdb/createrole/replication/bypassrls privileges or inherited memberships. Each owns only its database/schema objects and cannot CONNECT to the other's database. PUBLIC CONNECT/schema privileges are restricted and default privileges stay isolated. Superusers remain administrative exceptions; two databases on one server do not isolate infrastructure outages.

Core owns events/registrations/email_outbox. Notifications owns notification_jobs with seven fields: id,payload,mime nullable,status,available_at,attempts,last_error nullable. No cross-database FK/shared ORM or direct Core query from Notifications is allowed. The nullable MIME field is the second freeze boundary, not an unimplemented planned feature.

## Settings

.env.example contains public local examples only. Keep actual credentials in untracked .env and use distinct passwords/keys. Core Settings needs asyncpg DATABASE_URL and ORGANIZER_TOKEN; worker additionally receives NOTIFICATIONS_URL/internal token/relay settings. Notifications API/sender use their own DATABASE_URL/internal key; SMTP/public URL settings belong only to the sender. Core has no SMTP configuration.

The internal Notifications API and both SMTP ports are not exposed as public service APIs. Nginx publishes the application on localhost; Mailpit's inbox is separately bound to localhost. Changing the frontend port requires the matching PUBLIC_APP_URL before preparing emails. See README for actual defaults/addresses.

Settings repr excludes DSNs/tokens and sensitive URLs. Text ValidationError hides input values while preserving field/cause diagnostics and a nonzero startup exit. It does not sanitize model_dump/errors()/json() or third-party collectors of environment/locals: do not log those structures. SQLAlchemy runtime/Alembic hide bind parameters.

## Existing volume: bootstrap without deleting data

Docker entrypoint initialization runs only on an empty PGDATA directory, so a second database cannot rely solely on initdb scripts. The independent db-bootstrap container runs the actual shell/SQL every requested bootstrap, including an existing volume.

The scripts validate distinct names/roles, refuse to repurpose privileged roles/memberships, create missing ordinary roles/databases, set their passwords, configure ownership/CONNECT/TEMP/schema/default privileges, and preserve all application rows. Object ownership is transferred only within the intended schemas. SQL uses psql variables/format identifier/literal quoting rather than shell-interpolated SQL.

Do not delete/recreate a volume to add Notifications. Before a real upgrade, take a backup and review current settings:

```sh
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > /tmp/core-before-upgrade.dump
docker compose build api notifications
docker compose run --rm db-bootstrap
docker compose run --rm migrate
docker compose run --rm notifications-migrate
docker compose up --no-build -d --wait api worker notifications notifications-sender frontend mailpit
```

These are operator instructions, not steps executed on the main data during verification. A database dump contains private data; keep it outside Git and protect it. For a previously deployed sender/writer, coordinate stop/start and schema-specific preflight as described in [canonicalization](EMAIL_CANONICALIZATION.md). Changing the .env administrator password alone does not rotate an existing PostgreSQL server password. Application role passwords are set when bootstrap runs.

## Readiness and lifecycle

Core /api/health checks its DB and expected Alembic head; Notifications /health checks its own. HTTP200 means ready,503 means unavailable/stale schema with safe diagnostics. Core does not depend on Notifications/SMTP readiness. Frontend waits only for Core; workers recover persisted jobs independently. Worker/sender heartbeat health checks real loop liveness, not successful mail delivery.

Core head0005_scale_indexes keeps24columns and adds indexes only. Notifications head0001_notification_jobs keeps7columns. No existing migration is rewritten; downgrade/check regression commands run only on dedicated test databases. Some historical destructive downgrades explicitly require empty tables instead of inventing lost data.

## Isolated verification

Test services use tmpfs PostgreSQL/Mailpit and distinct databases ending _test. Core executes as core_app_test, not the admin; its fixture rejects privileged roles/memberships. Notifications tests use notifications_app_test. The isolated bootstrap test alone has administrative access to create seeded rows, rerun the actual bootstrap and inspect roles/owners/privileges.

The repeated-bootstrap regression stores data in **both** databases, invokes bootstrap again, and verifies row preservation, owner/default privilege correctness and denial of cross-service access. Infrastructure delivery tests then exercise both services without weakening isolation.

The browser overlay also replaces runtime volumes with tmpfs and requires the `event-registration-relay-check-ui-` prefix. scripts/browser-test.sh uses .env.example, random ports, real readiness and sets the sender's PUBLIC_APP_URL to the actual frontend origin. It preserves an already running test port during rebuild so frozen links stay valid. Never combine that overlay with the main project's name.

Use the exact commands in README/.github/workflows/ci.yml. Smoke/failure scripts require explicit test-project guards; pause/kill/restart and migration downgrade belong only in those projects. Cleanup uses project-scoped down without deleting main volumes. Tests prove infrastructure isolation, not production HA, a backup policy or unlimited throughput.
