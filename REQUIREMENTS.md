# Requirements and acceptance evidence

Source: the unchanged [original PDF](<docs/Задания Agentic Developer (2).pdf>), general requirements on pages1–2 and **all of assignment9 on page9**. Rechecked on2026-10-26. The PDF is readable; no requirement was inferred from its filename alone. IDs below are project traceability labels, not numbering printed in the PDF.

Current implementation includes UI, SSE, HTTP relay and SMTP through Mailpit. A database column/constraint alone is not proof of business behavior. Historical verification belongs to [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md); the latest readiness run is recorded there, without declaring tests successful before execution.

## Mandatory general PDF requirements

| ID | Requirement | Implementation | Verification |
| --- | --- | --- | --- |
| G01 | Separate backend and frontend communicating over a network | FastAPI services and React, HTTP through Nginx | Compose services, actual browser/API requests |
| G02 | Backend language choice and reasons | Python, async FastAPI/SQLAlchemy/asyncpg | Manifests, architecture and decision record |
| G03 | Vue or React frontend | React/TypeScript/Vite | Frontend manifests, production build, E2E |
| G04 | Relational storage, preferably PostgreSQL | PostgreSQL, two isolated databases | Real integration tests and role isolation |
| G05 | Accounts/login model may be chosen | Shared organizer key; private participation tokens; no accounts | Unauthorized/wrong-key tests, private-link flows |
| G06 | Prompts or decision log delivered with code | DECISIONS and DEVELOPMENT_LOG | Files and traceable real timestamps |
| G07 | AI use is expected and disclosed | README provenance and logs | Honest tool/model disclosure without invented metadata |
| G08 | Deployment prerequisites documented | Docker/Compose, ports, initial downloads, settings | README and clean isolated startup |
| G09 | Quick local startup | Compose bootstrap/migrations/health ordering | Build and start with empty tmpfs DB |
| G10 | External services may be emulated | Mailpit local mail emulator; no paid runtime APIs | Actual SMTP submission and inbox inspection |
| G11 | Works with two simultaneous clients | Independent participant/staff contexts, PostgreSQL locking | Two-process API tests and actual Chrome E2E |
| G12 | Honest current state | Implemented features and explicit limitations | README, load report and readiness results |
| G13 | Demonstrable correctness | Automated checks plus manual review scenario | Full service/infrastructure/frontend tests and smoke probes |
| G14 | GitHub repository link | Actual origin in README | Read-only git remote/ls-remote verification |
| G15 | State model/tool and why | Codex desktop disclosure, exact model uncertainty stated | README/DECISIONS; do not invent serving build |
| G16 | Show gradual work over time | Git history and dated development/decision records | Existing commit history and original historical records |
| G17 | Deployment/current-state description and next improvements | README and operations guide | Follow documented setup and acceptance flow |
| G18 | Credit borrowed solutions/templates/generators | No application/scaffold copied; dependencies documented | README provenance and manifests/lockfiles |

## Mandatory assignment9 requirements

| ID | Requirement | Implementation | Verification |
| --- | --- | --- | --- |
| C01 | Event description, date/time and capacity | events model and organizer form/API | API validation, saved values and E2E creation |
| C02 | Register by email | Canonical email registration service/API/form | ASCII/IDN, repeated email and real HTTP tests |
| C03 | Cancel participation | Token-authorized cancellation, ticket invalidation | API/private UI, stale/foreign token and time checks |
| C04 | Waitlist when full | Status and locked MAX+1 active sequence | PostgreSQL business/FIFO tests and independent clients |
| C05 | Ticket with code | Random code only for confirmed participation | Ticket page/email and invalidated-code checks |
| C06 | Entrance check-in screen; scanner may be replaced by code entry | Organizer code input and check-in API | Actual browser and two separate staff/API processes |
| C07 | Organizer confirmed/waiting/arrived counts | One MVCC aggregate snapshot and three UI counters | Counts after registration/cancellation/promotion/check-in |
| C08 | Registered participant receives a ticket email | Atomic outbox on place allocation | Core -> HTTP -> Notifications -> SMTP -> Mailpit; no mail after business rollback |
| C09 | Repeating an email does not create a second place | Canonical email, UNIQUE(event_id,email), neutral public no-op | Sequential/concurrent repeats retain one registration/place/token/ticket/outbox; email alone cannot resume |
| C10 | Cancellation automatically promotes the first waiting person and emails them | Promotion/ticket/outbox in the same cancellation transaction | FIFO order, rollback and real Mailpit promotion email |
| C11 | Simultaneous last-place requests yield one place and one waiter | READ COMMITTED + event FOR UPDATE + fresh reads | Separate connections and two API processes; confirmed1/waiting1 |
| C12 | All participants receive a reminder24hours before, exactly one logical reminder | One dedup identity per registration; confirmed/waitlisted, not cancelled | Exact time boundaries, late joins, rescheduling, restart and dedup tests |
| C13 | Exactly one logical reminder | Unique reminder identity, immutable payload/MIME, stable Message-ID | Commit/ACK/SMTP failure and restart tests; Mailpit duplicate suppression is limited to its current store, not general exactly-once SMTP |
| C14 | A ticket checks in only once | Conditional update and event synchronization | Concurrent200/409, unchanged timestamp/count on second attempt |
| C15 | Organizer's arrived count updates live | Shared SSE snapshots, fresh reconnect and server time | Two browsers/processes, check-in update, transient SQL error and cleanup |
| C16 | All active participants are emailed after rescheduling | Versioned event update and separate deduplicated rescheduling jobs | Repeated/stale/concurrent moves and Mailpit for confirmed/waitlisted recipients |

The PDF's “exactly one reminder” is implemented as one logical notification identity, not an impossible promise of exactly-once SMTP acceptance after an ambiguous network failure. Mailpit's current-store deduplication is a local verification aid.

## Additional user/project requirements

These are not additional text discovered in the PDF.

| ID | Choice | Implementation / verification |
| --- | --- | --- |
| U01 | FastAPI, PostgreSQL, SQLAlchemy, Alembic, React, TypeScript, Compose and Pytest | Manifests/locks, actual containers and tests |
| U02 | No paid accounts/external runtime APIs; Mailpit | All runtime dependencies local; initial package/image download needs internet |
| U03 | SOLID/KISS/DRY/YAGNI where useful | Small responsibilities, no speculative repositories/interfaces/broker; readable tested transactions |
| U04 | Real Git commit progression | Existing history; this task creates no commit/push or invented dates |
| U05 | Separate ten-sentence essay | ESSAY.md, based on recorded experience; manually count10 sentences |
| U06 | Staged work and user architecture approval | Implement only authorized changes; preserve prior work/data |
| U07 | Real Almaty timestamps | Clock observations converted to Asia/Almaty +05; no reconstruction of unknown earlier times |
| U08 | One relay/sender, transactional outbox, no distributed leases | PostgreSQL session singleton, no SQL transaction during network, crash/ownership tests |
| U09 | Never recover a management secret merely from email | Public duplicates are no-op for every state; resume needs token/generation |
| U10 | Compare queue/transport/isolation alternatives; permit later growth without adding speculative systems | Decision history and architecture; Core/Notifications HTTP split later explicitly approved |
| U11 | Three Core tables/24columns, canonical email, locked MAX+1 and new migrations only | Real information_schema and populated migration tests; no users table, old revisions intact |

## Agreed interpretations where the PDF is not specific

| ID | Rule | Verification |
| --- | --- | --- |
| A01 | Active participants means confirmed and waitlisted; cancelled excluded | Recipient selection and wording, no ticket for waiting |
| A02 | One logical reminder across resume/rescheduling; unprepared can change, prepared immutable | Before/after-freeze changes and send retries |
| A03 | Late unprepared reminders may run before start, are suppressed after start; prepared retries remain historical | −24h/start boundaries, outage/restart and frozen retry |
| A04 | Resume retains registration/token, increments participation_no, uses new ticket or queue tail | Stale actions/old ticket rejected, no restored queue priority |
| A05 | Lowercase email with email-validator ASCII domain, no SMTPUTF8; preserve dots/+suffixes | IDNA ß/Punycode/concurrent duplicate and ASCII tests |
| A06 | Registration/cancel/resume/reschedule before start; check-in from start; checked-in cannot cancel | Time after event-lock, concurrent cancel/check-in, device-clock E2E |
| A07 | Capacity cannot be edited after creation | API rejects unspecified mutation, UI offers date change only |
| A08 | No accounts; organizer secret and participant capability links | No public secret exposure/storage, unauthorized actions rejected |
| A09 | Live updates use one-second snapshots per event/process; small healthy queues should be prompt | Observed latency/E2E, not an invented PDF timing or production SLA |

## Later approved reliability, UI and scale work

- All required screens, SSE and asynchronous SMTP are implemented; user review remains part of handover.
- Extra server_time on event pages and SSE anchors actions/availability with performance.now. Unknown/offline time stays neutral/disabled; reconnect gets fresh data. Rendering uses English and explicit Almaty timezone.
- Shared SSE producers, bounded queues, identity-safe retirement after SQL failure and resource cleanup replace per-client SQL polling.
- Paginated lists, indexes and three-statement atomic rescheduling reduce unbounded work; offset limitations remain explicit.
- Single-iteration relay/sender mutex, ownership-loss cancellation, safe retry and heartbeat/failed/backlog diagnostics preserve immutable delivery evidence.
- Nginx resource budgets account for NAT and overwrite untrusted proxy headers; multiple API-process correctness stays in PostgreSQL.
- CI includes real PostgreSQL/Mailpit, migrations/static/types/builds, HTTP/SMTP failures and browser tests. Corrected load probes reject partial success/invalid snapshots; raw historical measurements are retained with their limitations.
- Original PDF/data, tests, migrations, locks, SQL bootstrap and measurement artifacts are preserved. Translation does not rewrite already prepared payload/MIME. English history is an editorial translation of recorded actions, not fabricated new timestamps.

Submission requires an actual GitHub project, reproducible setup, approved history/changes, real verification, provenance, limits and the user-requested essay. Passing constraints or agreeing an architecture does not replace those checks; an unpushed working copy is not yet the submitted GitHub revision.
