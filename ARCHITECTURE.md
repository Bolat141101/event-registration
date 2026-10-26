# Architecture

This describes the implemented application. Earlier proposals are historical decisions in [DECISIONS.md](DECISIONS.md); they do not describe missing current functionality. UI, SSE, HTTP notification delivery and SMTP through Mailpit are implemented. The authoritative assignment is the unchanged [PDF](<docs/Задания Agentic Developer (2).pdf>); [REQUIREMENTS.md](REQUIREMENTS.md) separates it from project choices.

## 1. Components and ownership

```text
Browser -> Nginx / React -> Core FastAPI
                              | AsyncSession + asyncpg
                              v
                        Core database / core_app
                        events, registrations, email_outbox
                              |
                        one async HTTP relay
                              |
                      protected internal HTTP API
                              v
                       Notifications FastAPI
                              | AsyncSession + asyncpg
                              v
                  Notifications database / notifications_app
                         notification_jobs
                              |
                       one async SMTP sender
                              v
                       Mailpit mail emulator
```

One PostgreSQL instance, two databases and two ordinary application roles. The administrative bootstrap role creates databases/roles and configures ownership, CONNECT/schema privileges and default privileges. Neither service queries the other database. Core owns participation, schedule versions and the decision that a notification is ready; Notifications owns durable acceptance, MIME and SMTP attempts. React has no direct database access. No Redis, Celery, Kafka or additional coordinator is required.

## 2. Code boundaries

| Path | Responsibility |
| --- | --- |
| `backend/app/api` | HTTP validation, access checks, statuses and serialization |
| `backend/app/services` | Registration, cancellation, resuming, rescheduling and check-in transactions |
| `backend/app/db` | SQLAlchemy models/engine, schema readiness and waitlist allocation |
| `backend/app/notifications` | Atomic outbox creation, payload preparation, relay and explicit retry |
| `backend/app/live.py` | Shared public snapshots; not a business lock or an authoritative cache |
| `backend/app/operations.py`, `worker_health.py` | Safe queue diagnostics and worker heartbeat |
| `notifications/notifications_app` | Independent settings/DB, contract validation, acceptance, MIME, SMTP sender and retry |
| `frontend/src/api` | Fetch/error translation and actual API contracts |
| `frontend/src/hooks` | Request lifecycle, server-time anchors, private participation and SSE cleanup |
| `frontend/src/components`, `pages` | Small shared components and user/organizer screens |
| `infrastructure/postgres` | Repeatable bootstrap and SQL role isolation |
| `infrastructure/checks`, `tests` | Real HTTP/SMTP fault probes, load measurements and infrastructure regressions |

The API delegates to services; business operations do not call HTTP or SMTP. There are no generic repositories, unused interfaces or separate users/tickets/waitlist services. Runtime entry points are `app.main:create_app`, `app.worker`, `notifications_app.main:create_app` and `notifications_app.worker`.

## 3. Data model

Core has **three tables, 24 columns** (Alembic metadata excluded):

- `events`: `id` PK, `description`, `starts_at` timestamptz, `capacity`, `schedule_version`.
- `registrations`: `id` PK, `event_id` FK, `email`, `status`, `participation_no`, `waitlist_seq` nullable, `ticket_code` nullable, `manage_token_hash`, `checked_in_at` nullable.
- `email_outbox`: `id` PK, `registration_id` FK, `kind`, `dedup_key` UNIQUE, `payload` JSONB, `prepared_at` nullable, `available_at`, `status`, `attempts`, `last_error` nullable.

Notifications has **one table, seven columns**: `notification_jobs(id PK, payload JSONB, mime BYTEA nullable, status, available_at, attempts, last_error nullable)`. There is no cross-database FK.

Core constraints enforce unique `(event_id,email)`, unique non-null `(event_id,waitlist_seq)`, unique ticket/hash, positive capacity/versions/generation and consistent status/ticket/queue/check-in combinations. These protect stored state but do not implement FIFO, idempotent API behavior or last-place allocation by themselves.

Email is normalized once using email-validator ASCII output, lowercase local-part/domain, IDNA2008 and no SMTPUTF8. Dots and plus suffixes remain significant. Unicode/Punycode domains identify the same address. See [canonicalization](docs/EMAIL_CANONICALIZATION.md).

Indexes cover event status/counts, active waitlist order, pending outbox order, event `(starts_at,id)` pages and outbox `registration_id` lookup. `0005_scale_indexes` only adds the latter two; it changes no columns or rows. A normal CREATE INDEX can block writes during an upgrade; plan maintenance for a large production database.

## 4. Access and public contracts

Public event details and streams expose aggregates, never addresses, tickets, hashes or management paths. Repeated public email registration always returns a neutral acceptance, regardless of an existing registration's status. It neither issues a new secret nor restores cancelled participation.

Organizer mutations use the configured Bearer key. Private participation uses an unpredictable token whose hash is stored in Core; the first email carries `/registration#token=...`. React consumes/clears the fragment before rendering, keeps tokens only in memory and sends Authorization headers. No credentials enter query strings, localStorage, sessionStorage or frontend build variables. Reload requires reopening the email link or entering the organizer key.

Important endpoints:

| Operation | Endpoint |
| --- | --- |
| Bounded public pages | `GET /api/events?limit=20&offset=0` -> `{items,next_offset,server_time}` |
| Public event | `GET /api/events/{id}` |
| Registration | `POST /api/events/{id}/registrations` -> neutral 202 |
| Event creation / rescheduling | `POST /api/events`; `PATCH /api/events/{id}/schedule` |
| Private status / cancellation / rejoining | `GET /api/registration`; `POST /api/registration/cancel`; `POST /api/registration/resume` |
| Check-in | `POST /api/events/{id}/check-ins` |
| Live aggregates | `GET /api/events/{id}/stream` |
| Organizer key verification | `GET /api/organizer/access` |
| Readiness / contract | `GET /api/health`; `GET /api/openapi.json` |
| Internal notification acceptance | `POST /internal/v1/notifications` on Notifications only |

`participation_no` prevents delayed cancellation/resume requests from changing a later participation cycle; `schedule_version` prevents stale rescheduling. Conflicts require rereading, not blindly repeating a mutation.

## 5. Transactions, last place and FIFO

The isolation level is PostgreSQL **READ COMMITTED**. Every capacity/participation operation first acquires `SELECT ... FOR UPDATE` on the event, then performs fresh SELECTs inside that transaction. Two API processes share the same database lock; there is no Python lock replacing this guarantee.

1. Registration locks the event, checks time and the canonical email, then counts confirmed entries.
2. If a place exists, assign a random ticket; otherwise allocate `MAX(active waitlist_seq)+1` **after acquiring the event lock**.
3. Persist participation and logical notifications in one commit.
4. A competing request acquires the lock after that commit and sees fresh state. For capacity1, exactly one is confirmed and the other waits.

Clearing waitlist_seq on cancellation/promotion allows reuse of a freed tail number without violating FIFO among active entries. Timestamp ordering and cached counters are not used as a substitute.

Cancellation locks the event, validates token/generation/time, invalidates the ticket and promotes the smallest active waitlist_seq in the **same transaction**, including the promoted participant's ticket/outbox. Delaying promotion to a worker would let a new registration steal the place and would make capacity correctness depend on SMTP availability.

Rejoining is a separate token-authorized operation. It retains the registration/token, increments participation_no, gets a new ticket if confirmed or a new queue-tail number if full. Old tickets and stale-generation requests stay invalid.

## 6. Isolation alternatives and failures

Atomicity couples business changes with outbox rows. Constraints and transaction logic preserve consistency; row locks isolate conflicting operations; PostgreSQL commit/WAL provides durability subject to deployment/backup settings. ACID does not make an external HTTP/SMTP action atomic with SQL.

READ COMMITTED needs the explicit event lock and fresh post-lock reads. A pre-lock MAX/count or any writer bypassing this protocol would introduce races. SERIALIZABLE could detect broader anomalies but requires correct retries after serialization failures and does not remove SMTP ambiguity; the single aggregate lock is smaller and clearer here.

Transactions may still fail with lock timeout/deadlock/connection errors. They roll back completely. Keep lock ordering consistent and failures bounded; do not retry ambiguous external side effects as though they were SQL. Tests prove rollback and distinct API-process behavior. Relay lock contention uses a fresh transaction after rollback, never a poisoned session.

## 7. Time, reminders and rescheduling

API inputs require timezone-aware datetimes, normalized to UTC. Overflow at either UTC boundary, null characters and invalid fields return422 before PostgreSQL. UI displays Almaty UTC+5 explicitly.

Registration/cancellation/rejoining/rescheduling are allowed before the start; check-in from the start. Time is checked after the event lock. Capacity is fixed after creation. These are agreed project rules where the PDF does not specify exact boundaries.

A single reminder dedup key belongs to the registration across cancellation/resume/rescheduling. Its unprepared payload/deadline can change; prepared payload cannot. Late unprepared reminders can become due immediately before the event, but are suppressed after the start. Once preparation freezes an attempt, a retry completes the same immutable job even if circumstances subsequently change.

Rescheduling validates expected_schedule_version, updates the event and executes three set-based outbox statements under the same event lock/transaction: refresh unprepared ticket/waitlist context or cancel a stale participation generation; upsert the unprepared reminder deadline/context; insert a separate version-deduplicated rescheduling message. Prepared rows are untouched. This replaces per-participant ORM loops without weakening atomicity. SQL parameters are explicitly typed for asyncpg/JSONB.

## 8. Check-in

Check-in locks the event, checks start time, validates an active ticket belonging to that event and performs a conditional update only when checked_in_at is NULL. A second staff process gets409; an invalid/cancelled/wrong-event ticket is rejected. Counts are read in a single MVCC statement, not independently from inconsistent snapshots.

## 9. Notification delivery and two freeze boundaries

Core prepares a due outbox job under the event lock when needed, rechecking participation, version and time. `prepared_at` freezes the full logical payload and message identity. HTTP happens after SQL closes. One async httpx relay sends the versioned contract with bounded timeout/retry/exponential backoff; a lost response repeats the same ID/content.

Notifications validates the shared contract, authenticates the internal key, and commits its own job before202. Identical ID/content repeats return202; different content for that ID returns409. Repeated acceptance never resets status, MIME or attempts; late versions remain historical commands and cannot reactivate an existing job or change Core state. It never reads Core directly.

The SMTP sender uses aiosmtplib. Before SMTP it renders and saves MIME bytes: recipient, content, Date and Message-ID become immutable. Retries load and validate those exact bytes against the canonical payload recipient. Damaged or unsafe MIME is marked failed with a safe category and does not block later jobs; the original evidence is retained. Newly prepared email copy is English; old frozen MIME is not translated.

Core `forwarded` means durable HTTP acceptance, not SMTP success. Notifications `sent` means SMTP acceptance, not guaranteed inbox delivery. A crash after SMTP accept/before local result storage can still duplicate mail. Mailpit Message-ID suppression is limited to its current configured store. See [protocol](docs/NOTIFICATION_PROTOCOL.md) and [SMTP contract](docs/SMTP_DELIVERY.md).

## 10. Worker ownership, recovery and diagnostics

One active relay/sender iteration is enforced by a session advisory lock in each independent DB, on a reserved AUTOCOMMIT connection. The lock spans HTTP/SMTP but no SQL transaction does. A watchdog checks ownership; losing the DB session cancels the attempt. Cleanup unlocks or invalidates the connection before returning it to the pool. This is singleton enforcement, not distributed leases or SMTP fencing: failover can still intersect an already accepted external action.

Relay considers a bounded page of heads of independent events. An unavailable event-lock is skipped for that pass; ordering inside an event is retained. When no candidate is available it pauses normally, rather than spinning or permanently skipping the blocked job.

Workers recover due persisted work after restart. Exhausted attempts remain failed. Explicit retry requires the existing ID/immutable data and acknowledgement of duplicate risk; unsafe MIME cannot be repaired by silently regenerating it. Heartbeat and queue CLI output expose counts, failed UUID samples and overdue age, never tokens/addresses/MIME. Core readiness depends on its DB/schema only. [Operations](docs/OPERATIONS.md).

## 11. Frontend and live recovery

React/TypeScript/Vite uses a small component set and hooks, no large UI framework/state manager. Screens include event list/detail, private participation, organizer creation/rescheduling/counters and manual check-in. Requests/error mapping live outside visual components; success is shown only after actual API confirmation.

SSE is appropriate for one-way statistics: simpler browser reconnection than a bidirectional WebSocket protocol, comparable latency with the same server snapshot schedule. WebSockets would be useful for future bidirectional collaboration, but would not solve SQL fan-out by themselves. A future multi-instance deployment needs deliberate fan-out/connection budgets, not merely a transport replacement.

LiveHub runs one short SQL read per event/process each second, broadcasts to bounded latest-state queues and releases resources after the last subscriber. It holds no SQL transaction while waiting for clients. A failed producer retires its own registry entry before old HTTP cleanup, so reconnect cannot attach to a dead cached topic. Old cleanup cannot delete a replacement topic. Reconnect receives a complete current snapshot; no event replay log is promised.

Browser availability and mutations use server_time plus performance.now, never the device wall clock. Unknown/lost time disables time-dependent actions and gives a neutral indicator. The list receives server_time with its page; the detail uses SSE. Offline/online/focus/watchdog cleanup closes/reopens streams. Initial transient REST failure can recover through real SSE;404 is not masked.

Private status refreshes on aggregate/schedule changes, reconnection and a10s fallback for private-only changes without a count change. Public counters remain live. Screenshots wait for page-specific data and fonts before checking overflow/capturing; tests use event/promise barriers rather than sleeps to hide loading races.

## 12. Pagination and admission budgets

List default20/max100, offset0..1000000. SQL selects a bounded ordered ID page before computing its aggregates. Offset pages are not historical snapshots during concurrent rescheduling; consider cursors only when justified by actual list size/use.

Nginx applies registration30r/s with burst1000 per remote_addr, and one shared SSE cap2000 without a small per-IP SSE limit that would punish a shared NAT. It overwrites incoming proxy IP headers. API independently caps subscribers per process.429/503 include retry guidance. These are local resource budgets, not production capacity claims or distributed bot prevention. Multiple independent ingress instances do not share zones.

## 13. Infrastructure and migrations

Docker Compose starts DB, repeatable bootstrap, independent migrations, APIs/relay/sender, frontend and Mailpit. Main data uses named volumes; browser/load/test projects use guarded names and tmpfs. Tests use ordinary core_app_test and notifications_app_test roles; bootstrap tests use an isolated admin only to verify ownership/privilege setup.

Core revisions:0001 initial34columns,0002 simplify24,0003 forwarded,0004 canonical email,0005 indexes. Notifications:0001 jobs. Old revisions are unchanged.0002/Notifications destructive downgrade require empty application tables;0004 cannot restore prior email spelling. Backups are necessary for lossy historic rollback. Only test DBs are downgraded in verification.

## 14. Testing, scale and future boundaries

Real PostgreSQL tests prove concurrency, FIFO, duplicate email, tickets/check-in, generations, rollback, migrations and isolation. Notifications/infrastructure tests exercise immutable bytes, ID conflicts, failures before/after acceptance, restart, unsafe MIME and canonical recipients. Chrome E2E uses independent contexts and actual Core -> Notifications -> Mailpit. CI includes these tests, static/type/build checks, real HTTP/SMTP fault probes and cleanup.

Historical and strict load runs are documented separately in [LOAD_TESTING.md](docs/LOAD_TESTING.md). The corrected probe requires complete HTTP success, physical logical-job counts, valid refreshing SSE and no duplicates/deadlocks/errors.1000 open streams is not1000 registrations/second; short local runs do not establish an SLA. Hot-event writes remain serialized and queue delay/registration p95 vary.

Future authorization/organizers can replace access checks without rewriting business services. Future concurrent job processing needs row claiming with FOR UPDATE SKIP LOCKED, leases/owner fencing, compare-and-set completion and idempotent remote acceptance; it is not implemented now. A Celery migration still needs an outbox-to-broker relay and cannot promise exactly-once SMTP. Microservices/brokers are not added for hypothetical growth.

Production needs TLS, authenticated real SMTP and domain setup, trusted proxy rules, synchronized clocks, backup/restore drills, monitoring/alerts and measured target-hardware budgets. Current limits and manual recovery procedures are explicit, not deferred claims of production readiness.

### Alternatives considered

| Task delivery approach | Advantages | Cost and reliability tradeoffs |
| --- | --- | --- |
| PostgreSQL outbox + owned worker, current Core relay | Business/job commit atomic in one DB, no broker, persisted recovery after restart | Custom bounded retry/diagnostics; one active worker limits throughput; remote side effects remain idempotent/ambiguous |
| Celery + Redis | Established worker routing, retries and operational tooling | Additional broker/runtime; direct DB-then-publish has a loss window, so retain an outbox relay; redelivery/ACK policy and idempotent consumers still required, no SMTP exactly-once |
| Separate notification service + message broker | Independent lifecycle/data ownership and future consumer scaling | More deployment, security, contract/version/order/observability work; broker persistence does not atomically commit Core and Notifications or eliminate SMTP duplicates |

The approved current middle ground is **Core + independent Notifications over durable HTTP acceptance**, without a broker. A future Celery/broker change can replace transport/claiming after the existing business outbox boundary; it must retain IDs, immutable payload/MIME and crash/idempotency tests. This is an engineering choice for the present scope, not a universal benchmark against other systems.

| Live transport | Current fit and clients | Reconnection, latency and expansion |
| --- | --- | --- |
| SSE | Server-to-browser counters, many independent listeners, simple public EventSource | Browser reconnect plus complete fresh snapshots; latency follows snapshot frequency. Shared SQL fan-out is per API process; proxy buffering/limits matter |
| WebSocket | Useful if future clients need continuous bidirectional collaboration | Requires connection/reconnect/protocol/auth lifecycle; with the same DB polling it does not reduce latency or SQL load automatically. Needs deliberate multi-instance fan-out too |

Both need bounded client resources and cleanup. Secrets stay in Authorization for protected HTTP operations, not live query strings. The current public SSE stream carries no private data, so it requires no secret-bearing EventSource URL.
