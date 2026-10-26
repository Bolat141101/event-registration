# Event Registration

A client/server application for **MadDevs Agentic Developer assignment 9**: organizers create events with a capacity limit, people register by email, and staff check tickets at the entrance.

Repository: [github.com/Bolat141101/event-registration](https://github.com/Bolat141101/event-registration). The remote was verified during the readiness review. This working copy can contain changes not yet committed or pushed; see [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) for actual verification results.

## What works

- Event creation, descriptions, dates and fixed capacity; paginated public and organizer lists.
- Case-insensitive email registration, including equivalent Unicode/Punycode domains without SMTPUTF8. Repeating an email does not take another place or disclose someone else's registration.
- Transactional allocation of the last place, FIFO waiting, cancellation and automatic promotion with email.
- Private participation links, rejoining after cancellation, tickets and single-use check-in by code.
- Organizer counters for confirmed, waiting and checked-in participants, updated through SSE.
- One logical reminder per registration, scheduled 24 hours before the event, and separate notifications for rescheduling.
- Durable HTTP delivery to Notifications, stored MIME, asynchronous SMTP submission, bounded retries, failed-job diagnostics and explicit manual retry.
- English UI, API messages and newly prepared emails; responsive layouts, keyboard navigation, loading/error states and recovery after network/SQL errors.

The original [assignment PDF](<docs/Задания Agentic Developer (2).pdf>) is unchanged. [REQUIREMENTS.md](REQUIREMENTS.md) separates its mandatory requirements from additional choices such as rejoining, private tokens and the service split. Existing user descriptions and already prepared payload/MIME are never translated in storage.

## Architecture

```text
React / Nginx -> Core API -> Core PostgreSQL database
                              | business transaction + outbox
                              v
                       async HTTP relay
                              |
                              v
                       Notifications API -> Notifications PostgreSQL database
                                                     | accepted jobs + frozen MIME
                                                     v
                                               async SMTP sender -> Mailpit
```

One PostgreSQL instance hosts **two independent databases and application roles**. Core owns events, registrations and the transactional outbox; Notifications owns accepted notification jobs and prepared MIME. Neither application role can access the other database. HTTP acceptance means `forwarded` in Core; it does not mean SMTP delivery. Core remains available when Notifications or SMTP is unavailable.

Business operations use `READ COMMITTED` and `SELECT ... FOR UPDATE` on the event. FIFO promotion happens inside cancellation's transaction. There is one active relay and one active sender, enforced with PostgreSQL session advisory locks; no SQL transaction stays open during HTTP or SMTP. There is no Redis, Celery or Kafka.

**Mailpit is a local mail emulator.** Its web inbox proves local SMTP submission, not delivery to a real recipient. SMTP is not exactly-once: a crash after acceptance can cause a retry. Frozen MIME/Message-ID and Mailpit's configured deduplication reduce duplicates only within their documented limits. Details: [architecture](ARCHITECTURE.md), [notification protocol](docs/NOTIFICATION_PROTOCOL.md), [SMTP](docs/SMTP_DELIVERY.md).

## Start from a clean clone

Requirements: Git, Docker Engine/Desktop running Linux containers, and **Docker Compose v2 with `!reset` support**. The first build needs internet access to download images and locked packages. Runtime requires no paid accounts or external API. Python and Node on the host are optional; allow several GB of free disk space and enough Docker memory for PostgreSQL, builds and browsers.

```sh
git clone https://github.com/Bolat141101/event-registration.git
cd event-registration
cp .env.example .env
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

If `.env` already exists, **keep it rather than copying over it**. Before starting, edit your local `.env`: replace the example `POSTGRES_PASSWORD`, `CORE_DB_PASSWORD`, `NOTIFICATIONS_DB_PASSWORD`, `ORGANIZER_TOKEN` and `NOTIFICATIONS_INTERNAL_TOKEN`. Tokens need at least 32 characters. The checked-in values are public local examples, not production credentials. Current Compose DSNs interpolate passwords into URLs: use URI-safe letters, digits, `_` and `-`, or supply correctly encoded connection settings. Never commit `.env`.

Compose waits for PostgreSQL, runs the repeatable database/role bootstrap and both migration services, then starts the APIs and workers. A migration container exiting with code 0 is normal. Core's current migration head is `0005_scale_indexes`; Notifications uses `0001_notification_jobs`. There is no manual SQL setup step.

| Address | Purpose |
| --- | --- |
| [localhost:8080](http://localhost:8080) | Public event list and frontend |
| [localhost:8080/organizer](http://localhost:8080/organizer) | Organizer workspace |
| [localhost:8080/api/health](http://localhost:8080/api/health) | Core readiness; healthy response: `{"status":"ok","database":"ready"}` |
| [localhost:8080/api/openapi.json](http://localhost:8080/api/openapi.json) | Actual API contract; Core has no separately published port |
| [localhost:8025](http://localhost:8025) | Mailpit web inbox |
| `127.0.0.1:5433` | Optional local PostgreSQL access; container-to-container address is `db:5432` |

Open **Organizer**, copy `ORGANIZER_TOKEN` from your own local `.env`, and enter it in **Organizer key**. There are no accounts or generated default passwords. The key stays in memory in that tab, is cleared on reload/sign-out, and is not embedded in the frontend bundle. Participants use the private link in their first email; knowing an email alone cannot recover that token.

Ports are configurable with `FRONTEND_PORT`, `MAILPIT_PORT` and `POSTGRES_PORT`. When changing the site port, set `PUBLIC_APP_URL` to that same site origin **before preparing emails**. Existing frozen links/MIME are not rewritten.

```sh
docker compose logs --tail=100 api worker notifications notifications-sender migrate notifications-migrate db-bootstrap
docker compose down
```

The main environment uses persistent PostgreSQL/Mailpit named volumes; `down` keeps them. Do not remove volumes to repair an upgrade. Back up an existing installation before applying migrations. The bootstrap also works with an existing volume and preserves rows; application role passwords are set during bootstrap, while changing the PostgreSQL administrator's `.env` password does not rotate an existing server password by itself. [Upgrade and isolation notes](docs/NOTIFICATIONS_INFRASTRUCTURE.md).

## Review the application with two clients

1. Create an event in Organizer with capacity **1** and a future date. All displayed/input dates use **Almaty, UTC+5**, independent of the device timezone.
2. Open its public page in two independent browser contexts. Register two different emails, concurrently if desired. Both public responses are neutral; one person gets the place and the other joins the waitlist.
3. Open Mailpit and follow each first registration email's private link. The confirmed participant has a ticket; the waiting participant has no ticket or invented queue position.
4. Cancel the confirmed participant's attendance before the start. The first waiting participant is promoted atomically and receives a ticket email. Repeating an email takes no additional place. Rejoining uses the private link and joins the queue tail if full.
5. Reschedule to a nearby **future** time. Both active participants receive a rescheduling email. Keep Organizer open and wait for the start; check-in is allowed **from the start**, while registration/cancellation/rescheduling are only allowed before it.
6. Open **Check-in**, enter the valid ticket, and submit. A second submission is rejected; the organizer's checked-in counter updates live. Use two staff tabs to check that the same code cannot succeed twice.

To observe the 24-hour reminder manually, create an event a little over 24 hours away and reschedule it a little under 24 hours away; an unprepared reminder becomes due. Its logical identity is retained through further changes. Automated tests cover exact boundaries, waiting/confirmed recipients, cancellation, rescheduling and crash recovery without waiting a day.

## Tests: use an isolated environment

The main environment is for persistent data. **Never run downgrade, truncation, failure injection or load scripts against it.** The test overlay replaces application storage with tmpfs, uses `.env.example`, a separate Compose project, distinct `_test` databases/ordinary roles, and random localhost ports. It does not read your `.env`.

```sh
export BROWSER_TEST_PROJECT=event-registration-relay-check-ui-review
export COMPOSE_PROJECT_NAME="$BROWSER_TEST_PROJECT"
export COMPOSE_FILE=compose.yaml:compose.browser-test.yaml
export COMPOSE_ENV_FILES=.env.example COMPOSE_PROFILES=test
export POSTGRES_PORT=0 FRONTEND_PORT=0 MAILPIT_PORT=0

docker compose config --quiet
docker compose build api test notifications notifications-test bootstrap-test frontend
docker compose run --rm test
docker compose run --rm notifications-test
docker compose run --rm bootstrap-test

docker compose run --rm --no-deps test ruff check .
docker compose run --rm --no-deps test ruff format --check .
docker compose run --rm --no-deps test mypy app tests/conftest.py tests/integration/test_relay_blocking.py tests/integration/test_live.py
docker compose run --rm --no-deps notifications-test sh -c 'ruff check . && ruff format --check . && mypy notifications_app'
docker compose run --rm --no-deps bootstrap-test sh -c 'ruff check --config /app/pyproject.toml /bootstrap-tests /checks && ruff format --check --config /app/pyproject.toml /bootstrap-tests /checks && mypy --config-file /app/pyproject.toml /bootstrap-tests /checks'
```

These Python services use real PostgreSQL/Mailpit, apply migrations and run `alembic check`. Their migration regressions also exercise upgrade/downgrade on **isolated `_test` databases only**. Never point `TEST_DATABASE_URL` at real data. Running Pytest without integration settings is not a complete verification.

The frontend Docker build runs Prettier, Vitest, TypeScript and Vite. For frontend development use Node **24**, `cd frontend && npm ci`, then `npm run format:check`, `npm test` and `npm run build`. This rebuilds native dependencies for the current OS; use Docker if local packages were installed for another platform. Do not delete `.venv` or `node_modules` as a substitute for diagnosing a dependency issue.

For actual browser verification with Node 24 installed:

```sh
BROWSER_TEST_PROJECT="$COMPOSE_PROJECT_NAME" scripts/browser-test.sh start
BROWSER_TEST_PROJECT="$COMPOSE_PROJECT_NAME" scripts/browser-test.sh test
BROWSER_TEST_PROJECT="$COMPOSE_PROJECT_NAME" scripts/browser-test.sh stop
```

The script prints the temporary site/Mailpit addresses and uses the public test-only organizer key from `.env.example`. Stop removes only that temporary project's containers/network; tmpfs data disappears. It does not delete main volumes. Browser screenshots are taken only after page-specific data loads and fonts settle; then width/overflow is checked. Traces/video are disabled to avoid recording private tokens.

[GitHub Actions](.github/workflows/ci.yml) runs static checks, all service/infrastructure tests, migration checks, frontend builds, real HTTP/SMTP failure scenarios, edge admission checks and Playwright. Exact locally executed commands, failures and final counts are recorded in [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md); a local run is not a claim that the remote workflow ran.

## Limits and next improvements

- Shared organizer key, no per-organizer accounts/RBAC, and no recovery flow for a lost private link. The first email remains the source of that link.
- Fixed capacity after creation, code entry instead of a QR scanner, offset pagination without a historical snapshot during concurrent rescheduling.
- One active relay/sender. SSE is shared per event **per API process**; multiple processes still rely on PostgreSQL for business synchronization. Ingress budgets are local to one Nginx and need retuning behind a trusted production proxy.
- Stored MIME is immutable, even after cancellation/rescheduling. SMTP acceptance is not end-recipient delivery and cannot guarantee exactly-once. Safe manual retry explicitly acknowledges duplicate risk.
- Local measurements with 1000 SSE connections are **not** proof of 1000 registrations per second or a production SLA. Registration latency/queue delay varied; longer arrival-rate/soak tests on target hardware are still needed. [Method and raw measurements](docs/LOAD_TESTING.md).
- Production needs HTTPS, real SMTP/TLS credentials and domain reputation, trusted ingress rules, backups plus a restore drill, monitoring/alerts and time synchronization. External SMTP and CD have not been deployed.
- Final handover still requires reviewer acceptance, an approved commit/push of this working copy and a remote CI result. No commit or push is performed by this readiness task.

## AI and implementation provenance

The project was developed with an AI coding assistant in **Codex desktop**, with architecture decisions reviewed by the user. The session identifies the assistant as GPT-6 based; the precise serving model/build was not independently captured in repository metadata, so no more specific model name or comparison is claimed. The tool was chosen for working directly with source, tests, containers and reviewable diffs; generated changes were verified rather than treated as evidence by themselves.

No third-party application was copied as a starting solution, and no Vite/FastAPI scaffold generator was used. Standard dependencies are listed and pinned in the manifests/lockfiles. [DECISIONS.md](DECISIONS.md) and [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) preserve the recorded progression and actual Almaty timestamps. The separate [ten-sentence reflection](ESSAY.md) is a user-requested deliverable, not a requirement found in the PDF.
