# Decision history

All timestamps are recorded clock observations converted to Asia/Almaty UTC+05:00. Recording a proposal is not approval, and unknown earlier chat times have not been reconstructed. This English edition preserves the sequence, decisions and material verification facts; the original wording remains in Git at [dff7a3766075453d6987256ef6d92f45d77e7f0d](https://github.com/Bolat141101/event-registration/blob/dff7a3766075453d6987256ef6d92f45d77e7f0d/DECISIONS.md). Historical omissions below describe their stage, **not** current missing UI/SSE/SMTP. Current design is ARCHITECTURE.md.

## Initial conditions:2026-10-19T22:37:22+05:00

The user selected assignment9, the PDF as the only reviewer requirements source, Python/FastAPI/PostgreSQL/SQLAlchemy/Alembic/React/TypeScript/Compose/Pytest, minimal reliable design and SOLID/KISS/DRY without unnecessary abstractions. No paid accounts/external runtime APIs; “Mailpi” was confirmed to mean Mailpit. Git progression and a separate10-sentence essay were additional user deliverables, not a PDF essay requirement. Architecture/documents were authorized first; no functionality/commits until approval.

### Original D01–D10 proposals, pending at that timestamp

| ID | Proposal | Rationale / consequence |
| --- | --- | --- |
| D01 | Modular FastAPI, React SPA, PostgreSQL, same-image worker and Compose | Separate client/server, one business-rule implementation; no unnecessary Redis/Celery/services at that stage |
| D02 | Shared organizer secret and participant management tokens, no accounts | Prevent cancellation by knowing email, avoid a password/account subsystem; individual audit/RBAC deferred |
| D03 | events/registrations/email_outbox; ticket/queue on registration, calculated aggregates | UNIQUE event/email, no redundant counters or tickets/waitlist tables; explicit CHECK/service invariants |
| D04 | READ COMMITTED + event FOR UPDATE, one Session per operation | Fresh state after lock, works between processes; Python mutex inadequate, SERIALIZABLE needs retries; only one event serialized |
| D05 | Event-locked waitlist sequence, atomic cancel/promotion | Unambiguous FIFO; no stolen-place window, untrusted client timestamps or SKIP LOCKED participant skipping; rejoin at tail |
| D06 | Persistent outbox with leases/retries/stable Message-ID; Mailpit dedup/store | Atomic business/task commit, disclose SMTP ambiguity and prove local dedup with faults; **leases proposal later removed** |
| D07 | One reminder for confirmed/waiting across moves; catch up only before start | Proposed interpretations A01–A03; alternatives change recipients/dedup and needed approval |
| D08 | One-second SSE snapshots including initial/reconnect | Simple one-way live statistics, local target<=2s, no broker/replay log; polling/NOTIFY were alternatives after measurement |
| D09 | UTC storage, Almaty display, pre-start registration/cancel/move, check-in from start, fixed capacity | Project interpretation of unspecified boundaries, not extra PDF text |
| D10 | Real PostgreSQL, Mailpit, two browsers and staged evidence | SQLite/mocks/one tab cannot prove core invariants; real history, README and essay at their proper stages |

Traceability: D01->G01–G04/G08–G10/U01–U03; D02->G05/C02/C03/C05/C06/A08; D03–D05->C03–C11/C14/A04/A05; D06–D07->C08/C10/C12/C13/C16/A01–A03; D08->G11/C07/C15/A09; D09->C01/C12/C14/C16/A06/A07; D10->G06/G07/G12–G18/U04–U07.

### Tool/model facts recorded during initial analysis

Codex desktop was already the user's workspace/tool. The session identified the agent as GPT-6 based, but did not establish an exact serving model identifier. No model benchmark or invented quality/speed comparison was used; exact displayed model metadata remains to be confirmed if available. Local PDF reading/editing/testing in one workspace motivated continued use of the tool.

PDF extraction used pypdf after unavailable PyMuPDF, with Poppler visual inspection. The PDF skill and an openai-docs reference were read; public documentation was not used to guess a private runtime model ID. No subagents, copied application/scaffold or generator was used. PostgreSQL/Mailpit primary references informed engineering choices. Later borrowing/generation would need explicit attribution.

## Revision2:2026-10-20T08:49:34+05:00

The user requested one background worker/outbox, removal of unnecessary coordination, no secret reissue by email and explicit alternatives. These were authorized constraints; implementation/A01–A09 approval was not inferred merely from the new message.

| ID | Revised proposal / reason |
| --- | --- |
| D01 | One sequential sender, no scheduler; persisted due reminders survive restart |
| D02 | First token by email only; any public existing-email repeat is no-op; resume needs token/generation |
| D03 | Three tables, then12outbox fields; remove redundant event FK/recipient/version/message-ID/leases/updated_at, combine deadlines as available_at |
| D04 | Keep READ COMMITTED/event lock; remove extra explicit registration/outbox row locks; fresh post-lock reads and bounded DB failure handling |
| D05 | Promotion stays in cancellation commit, independent of worker/mail |
| D06 | Remove leases/processing, retain prepared_at and computed stable Message-ID; test kill-before/after acceptance |
| D07 | One reminder with explicit prepare boundary: unprepared can change/cancel, attempted must retry unchanged |
| D08 | Keep SSE after WebSocket comparison; transport alone does not reduce SQL polling latency |
| D09 | Time/fixed-capacity proposals unchanged pending their approval |
| D10 | Test singleton operation/token safety and real DB races instead of unimplemented multi-worker lease expiry |
| D11 | Remove redundant stats and liveness/readiness pair; retain distinct cancel/resume/check-in/move operations |
| D12 | PostgreSQL outbox; no broker/Celery/notifications service at that stage; a broker does not close DB/publish or SMTP ambiguity |
| D13 | Preserve access/business/notification boundaries for later growth without speculative users/organizers/interfaces |
| D14 | Initially singleton by deployment: stop old before new, no rolling overlap; later superseded by DB enforcement |

Links: D01/D03/D06/D14->U08/C08/C12/C13; D02/D11->U09/A04; D04/D05->C09–C11/C14; D08/D12/D13->U10/C15. Single-sender throughput, Mailpit privacy, no RBAC and dedup limits remained explicit. Primary PostgreSQL/Celery/Redis/WHATWG/Mailpit sources informed the comparison, not a claim that alternatives are universally inferior. No application code/tests were added in this proposal stage.

## CI:2026-10-20T15:14:14+05:00

One ubuntu-24.04 job for push/main and PR/main used existing Dockerfiles/Compose/manifests/locks, no extra GitHub PostgreSQL/setup stacks. Ruff/format/Mypy/full Pytest, upgrade/test/check, frontend TypeScript/Vite and proxied health ran without suppressing errors. Separate project/.env.example/random ports kept main data independent; PostgreSQL default5433 was preserved/configurable. Checkout was pinned to SHA3d3c42e5aac5ba805825da76410c181273ba90b1 with contents:read and no credential persistence.

Actionlint1.7.12 was temporary, not an app dependency. Run blocks/environment were extracted for local execution; checkout/GitHub runner itself was not emulated. Initial CI cleanup removed only its test containers/volumes; later tmpfs CI cleanup no longer removes volumes. No push/remote run was claimed. [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [checkout commit](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1).

## Schema revision3:2026-10-21T21:31:30+05:00

The user authorized variant3 implementation. Earlier12outbox fields were superseded by10, total5+9+10=24. No users table without accounts/profiles. Remove title/audit dates/next sequence; copy normalized email into email and enforce CHECK/UNIQUE. The original spelling is lost; future services would own format/identity rules.

MAX(active waitlist_seq)+1 uses a **separate SELECT after event-lock**, with insertion in the same transaction and no helper commit. Tail reuse is allowed. Retain participation_no, schedule_version, prepared_at, stable outbox ID, dedup keys and typed payload. Queue numbers cannot substitute for participation generations or move versions. ticket:registration:participation, reminder:registration and rescheduled:registration:version remain separate identities.

0001 stayed unchanged;0002 handles the simplification. Populated downgrade is forbidden under locks on all three tables because title/original email/audit/history cannot be honestly reconstructed; use a pre-upgrade backup, never invented dates. Tests cover empty round-trip, populated preservation/refusal and independent connections observing blocking/commit/rollback/MAX. At that historical stage only infrastructure/health existed; unchanged API/worker/frontend contracts were not evidence of registration/FIFO/check-in/SMTP implementation.

## Business API:2026-10-22T11:27:56+05:00

User authorization covered services/API/access/outbox, not yet SMTP/SSE/full screens. Keep24columns and existing migrations. Services are functions accepting Session/Clock, one begin/commit per operation, no repository/UoW. Event-lock covers registration/cancel/resume/move/check-in; fresh reads after waiting and separate MAX helper preserve cross-process last-place/FIFO behavior.

Bearer management tokens are256random bits, stored as SHA-256 for lookup; tickets are separate192-bit random values with UNIQUE and replacement on reassignment. Secrets stay out of URLs/query/public bundles/responses/logs. Email-validator2.3.0 and dnspython2.9.0 were locked with external checks disabled; dots/+suffixes and local.test remain. Later IDNA correction superseded trim/lower-only identity.

One SQL aggregate produces all counts; checked-in is a subset of confirmed. Outbox identities are generation/version based, not queue based. Only the first ticket/waitlist contains manage_path. Prepared payload/identity/deadline/state remain immutable; unprepared failed context can refresh without automatically resetting attempts/error or reactivating it. One reminder lasts across rejoin/moves, including waiting; unprepared cancellation/resume adjusts the same row, prepared/sent do not reset.

Same current date is a no-op before version/time rejection; another date with stale version conflicts. A->B->A uses schedule_version. Old-generation cancel conflicts; idempotent resume can return the resulting active generation but cannot resurrect a subsequently cancelled cycle. Time is checked after event-lock in UTC. Lock timeout2s/statement timeout3s map temporary DB failures to safe503 without blind retries. An ambiguous COMMIT is not proof of rollback; event creation has no separate idempotency key.

At2026-10-22T11:36:03+05:00, privacy review chose the same neutral202 after event start for new/existing valid public emails, without creating participation/outbox.202-versus409 would reveal prior registration. Other prohibited time transitions retain409; regression checks unchanged rows and post-lock clock use.

At2026-10-22T11:42:36+05:00, recreated API caused Nginx502 from a cached obsolete upstream IP. Docker resolver127.0.0.11, valid5s/timeout2s and variable proxy_pass without URI fixed rediscovery; temporary outage/DNS-cache502 remains possible. [proxy_pass](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass), [resolver](https://nginx.org/en/docs/http/ngx_http_core_module.html#resolver).

## Async Core:2026-10-22T16:20:48+05:00

AsyncSession/asyncpg and only postgresql+asyncpg DSNs replaced synchronous psycopg without changing business contracts. Each task owns a Session/transaction, expire_on_commit=False avoids implicit reload; async does not remove event serialization. Alembic uses AsyncConnection.run_sync, old revisions unchanged; only the synchronous public test harness runs Alembic in a thread. Cancellation rolls back participation/outbox; asyncpg OSError/TimeoutError before SQLAlchemy wrapping still map to safe503.

The infrastructure worker became asyncio based, but delivery/leases/Celery remained outside that stage. Full PostgreSQL concurrency/migration/type checks confirmed behavior. [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html), [Alembic cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic), [asyncpg dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#asyncpg).

## Service infrastructure split:2026-10-22T22:42:22+05:00

The user authorized infrastructure only and clarified ownership: Core immutable logical payload, Notifications future MIME. An earlier proposal of MIME in Core was never implemented. Existing backend/frontend hashes/OpenAPI remained unchanged; Notifications gained its independent namespace/dependencies/Alembic/tests.

One PostgreSQL/two ordinary roles/databases minimized containers but shared server failures. Core/worker/migrate stopped using the administrator;129Core tests also passed under core_app_test. Repeatable db-bootstrap replaced initdb-only assumptions, preserves seeded rows on existing volume, uses quoted psql SQL and targeted ownership changes. Real reverse connections failed42501 and role privilege flags were false.

Seven-field notification_jobs included nullable MIME but did not yet implement inbox/delivery guarantees. Only own-DB health was exposed at that stage. Core worked with Notifications stopped: event, two participants/FIFO/four outbox rows and health/events200. Only Notifications gained a migration then; Core stayed0002. No SMTP/HTTP relay/UI/SSE was claimed yet. Later sections explicitly implement them.

## Ordinary-role CI/bootstrap:2026-10-22T23:09:28+05:00

Core tests use core_app_test, reject admin flags/memberships and retain own-DB DDL for migrations. A separate test-only bootstrap target uses isolated administrative credentials/psql, not a Docker socket or main volume. The real shell/SQL bootstrap is invoked twice with rows in both DBs, checking payload/MIME/Alembic, owners/ACL/default privileges/indexes/constraints and42501denials. Notifications migrations mount read-only.

Core, Notifications and bootstrap suites run sequentially because migration tests share the test DB. This proves repeated bootstrap on populated running PostgreSQL, not crash-atomic CREATE DATABASE of the whole cluster or failure halfway through bootstrap. Business rules/schema/old migrations stayed unchanged.

## HTTP relay/inboxv1:2026-10-22T23:53:58+05:00

The user authorized async HTTP delivery, not yet SMTP/Kafka. Existing worker became a sequential relay. Short prepare/finish transactions surround network; test handlers prove no idle transaction and free event FOR UPDATE NOWAIT during HTTP. Core freezes the completev1 envelope/prepared_at before sending; same ID/content survives ACK loss, cancellation/resume/moves and crashes.

0003 adds forwarded without columns; downgrade rejects forwarded rows instead of relabeling SMTP sent. Protected Notifications insert-on-conflict plus normalized JSON comparison commits before202; concurrent identical IDs give202/one row, conflicting content409, missing auth401. Entire envelope stays in existing payload: no hash/recipient/version columns or shared runtime package. Both DTO schemas are tested against the docs artifact.

Persisted bounded backoff/deadline handles408/429/5xx/transport/invalid ACK; other errors remain failed. Older generations/versions are accepted as historical snapshots without latest-wins, preserving the initial management link and each move. Unprepared stale/cancelled/post-start reminders are suppressed under event-lock; frozen commands repeat unchanged because remote commit may already have happened. Failed can mean unknown acceptance; default8started attempts, explicit intervention beyond budget. Real TCP response-loss/restart/concurrent-ID probes were added to CI; no SMTP-sent claim, MIME rendering or leases yet.

## Relay head-of-line fix:2026-10-23T09:06:53+05:00

A bounded page selects heads of distinct events (default20,1–100), preserving due `(available_at,id)` within an event. UUID round-robin/cutoff replaces global oldest-event dominance so many locked events do not starve an independent one. New work joins the next finite traversal; one HTTP action per run_once, false/pause if blocked.

Prepare alone uses NOWAIT.55P03 from NOWAIT or lock_timeout is skipped only after transaction rollback, preserving attempts/deadline/payload/prepared_at/error; other DB failures propagate. Every new candidate has a new session. Cursor is not durable ownership, lease or blacklist; restart rediscovers pending. Tests cover A/B ordered messages, blocked prefixes beyond page size, outbox update timeout, rollback/unlocked event and division-by-zero propagation. No participant FIFO/API/schema change; network backoff still means no global strict delivery order after failures.

## SMTP:2026-10-23T09:59:38+05:00

Clean starting HEADc4215d3 (`add reliable async notification delivery`). The user authorized local Mailpit SMTP without adding UI/SSE then. One separate notifications-sender uses aiosmtplib5.1.3, not a second lifespan sender. Persist MIME and attempt/backoff before network; render/load are distinct freeze boundaries without another migration.

SMTP sendmail receives saved bytes/envelope; Date/Message-ID/From/To survive retry/settings/time changes. A configured local_hostname avoids synchronous getfqdn. Four plain-text templates put description only in body and explain historical state. Core remains readiness/freshness authority; even cancellation after Core freeze but before MIME cannot retract acceptance or reactivate Core state.

DATA accept marks Notifications sent; HTTP202 marks only Core forwarded. Retry is bounded, permanent5xx fail, temporary errors remain pending; crash consumes a persisted attempt. Explicit failed-ID CLI requires duplicate-risk acknowledgement and keeps all evidence; invalid/sent/pending are not reset. Safe categories/settings validation avoid leaking SMTP responses/recipients/tokens. Mailpit duplicate suppression/quiet/current-store limits and test-mailpit tmpfs were explicit. Real TCP proxy loses DATA response after actual accept and verifies identical MIME/current-store one-copy recovery. No broker, leases, immutable DB trigger or cancellation HTTP protocol was added; exhaustion requires intervention, not a promise of eventual delivery.

## Email canonicalization:2026-10-23T15:51:52+05:00

Clean starting HEAD57aab8b. User confirmed faß->fass and distinct Unicode/Punycode registration defects, approved a new audited migration. A read-only main preflight saw0registrations/0collisions; no main upgrade occurred.

Use email-validator2.3.0 ascii_email, no SMTPUTF8/DNS, prior lowercase policy, no casefold, preserve dots/+suffixes. Small independent helpers plus cross-service reference tests replace IDNA2003. Core normalizes before lookup/ORM; accepted HTTP DTO is not rewritten. On every retry compare canonical frozen To with canonical payload; wrong fass/IDNA or non-ASCII frozen envelope fails without SMTP, preserves evidence and lets the next valid job run. Correct legacy ASCII casing/Message-ID bytes remain unchanged.

Read-only IDs-only audit and0004 repeat checks under event/registration ACCESS EXCLUSIVE, including cancelled rows/event scope. Any invalid/collision aborts before UPDATE, no merge/delete. Update email and ASCII CHECK only, retain3/24columns, UNIQUE, tickets/tokens/FIFO/versions/outbox. Downgrade removes ASCII CHECK but cannot recover original spelling; exact restoration needs backup. Alembic hide_parameters protects SQL errors. Sent messages cannot be retracted; main update requires backup/audit and stopping old writers. [Policy](docs/EMAIL_CANONICALIZATION.md).

## Safe configuration diagnostics:2026-10-23T16:07:17+05:00

Preserve prior IDNA changes; no business/schema/data mutation. Both Settings hide input in formatted ValidationError and DSN/token/sensitive URLs in repr, retaining field/cause and nonzero startup. Notifications Alembic also hides bind parameters. Subprocess Uvicorn/worker/operator/Alembic tests use fictitious secrets before network; health caplog checks actual handlers. No global exception suppression/logging framework. model_dump/errors()/json() and external env/locals collectors are not sanitized and must not be logged.

## Backend readiness before UI:2026-10-23T16:30:50+05:00

PDF pages1–2/9 reread; SHA2563b7934746efef38066c6164c68df93ee6a0175c7ac7af8472372537a609539d7unchanged. Remove unused Core smtp_host/port/from and Compose declarations after reference audit; real SMTP belongs to Notifications. Current-at-that-time heads0004/0001,24/7columns. Prepared boundaries, forwarded-versus-sent and duplicate risk unchanged. PDF requires outcomes/two clients, not microservices/SSE/private tokens/resume/IDNA or the user essay.

UI/SSE/two-browser acceptance were still **historically pending at this stage**. Negative controls restored old defects only in disposable copies: Core trim/lower3failures, Notifications IDNA2003two, repr/input5Core/fourNotifications. They proved sensitivity, not disabled tests. By2026-10-23T16:39:52+05:00,331Pytest/0skips, all static/type/migration/Compose/API/HTTP/SMTP-fault checks passed;13accepted/sent MIME,failed0. This was backend evidence, not complete PDF/UI handover.

## Frontend/SSE:2026-10-23T21:46:26+05:00

Start recorded19:55:44+05:00, clean HEADbef709c. User authorized actual screens/SSE and routine design decisions. React/TypeScript/Vite used small history/Link routing, API client/hooks and reusable action lifecycle, no large UI kit/state manager. Warm paper/graphite/blue, real descriptions/dates/capacity only, local fonts, responsive390–1440 and accessible labels/focus/status.

Public EventSource carries only public EventView/server_time; private/organizer requests use Authorization. Full snapshots provide initial/reconnect recovery; the original per-client read was later superseded by shared producers. Organizer access verifies an existing key without side effects. Tokens are consumed before render/hashchange/popstate, remain memory-only and require reentry after reload. No optimistic success;409 rereads real generation/date. Almaty input is explicit+05, not device timezone. Offline closes streams, online/focus reconnect, watchdog8s, retry2s; slow private reads are not cancelled by every tick.

Vitest/Playwright/Prettier are dev-only; E2E uses actual Core/Notifications/Mailpit, intentional network abort/offline, no fake successful operations or secret traces/video. Guarded tmpfs overlay preserves actual public origin and port on rebuild; sender starts after origin resolution, frozen MIME remains unchanged. Cross-browser/a11y audit and final user acceptance remain open; Playwright was local-only then, later added to CI.

At2026-10-23T21:55:05+05:00, real logs exposed AnyIO level cancellation interrupting asyncpg cleanup on disconnect. Shield only the short read_event/session cleanup; no cancel scope crosses yield, no global CancelledError/log suppression. Existing pinned AnyIO became explicit, without version/hash changes. PostgreSQL cancellation regression fails without the fix and checks completed read/checkedout0/no termination error. [AnyIO shielding](https://anyio.readthedocs.io/en/stable/cancellation.html).

## Reliability/load:2026-10-24T14:29:20+05:00

Server-time/performance anchors disable time-sensitive actions while unknown/offline; initial transient REST can recover via real SSE,404 stays visible. Browser±365day tests leave OS clocks unchanged.

Minimum singleton is session advisory ownership in each DB on an AUTOCOMMIT connection with watchdog/cleanup. Lost session cancels in-flight work but cannot retract accepted SMTP DATA; no leases/Redis/Celery/tables or fencing claim. Queue/failed-ID/overdue/heartbeat diagnostics and explicit failed retry avoid exposing PII. [PostgreSQL advisory locks](https://www.postgresql.org/docs/17/explicit-locking.html#ADVISORY-LOCKS).

SSE coalesces per event/process into latest-state queue1 with last-listener cleanup. Private state reads on changes/reconnect plus10s fallback rather than every heartbeat; rare private-only changes can display late. Pagination20/max100/offset is intentionally minimal, not a snapshot across moves.0005 indexes retain24columns. Three typed set-based SQL statements replace per-row reschedule loops while preserving freeze/dedup/generation/reminder and rollback.

Nginx30r/s/burst1000per real IP and shared SSE2000 accommodate NAT; API has its own process budget and incoming XFF is overwritten. These are local budgets, not distributed anti-bot/production capacity. [limit_req](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html), [limit_conn](https://nginx.org/en/docs/http/ngx_http_limit_conn_module.html). CI adds real tmpfs PG/Mailpit/Node24/Chromium/readiness/always-cleanup; actual PUBLIC_APP_URL persists between steps. [Playwright CI](https://playwright.dev/docs/ci).

At2026-10-24T18:12:14+05:00, controlled baseline/current measurements/EXPLAIN and populated0005 preservation were recorded. Registration/queue speedup is not claimed: one400-email drain48.606s, variable p95, unexplained outlier. Shared SSE/reschedule improvement is local, not production SLA. The initial exploratory baseline is not controlled comparison. Remote workflow/Linux browser step remained unrun pending allowed publication.

## Audit fixes:2026-10-24T19:44:27+05:00

1. A failed LiveHub producer retained ready/latest until HTTP cleanup, so reconnect attached to a dead topic. Retire only that producer's registry identity before reconnect; late old cleanup cannot remove a new topic. Real SQL failures reproduce initial and post-snapshot cases, deliberately reconnecting before old close.
2. Old probe checks allowed200×500/partial registration, unchecked SSE/deadlocks/outbox. Require200×202,10/190,600pending for this event, no duplicates/deadlocks, all active fresh valid expected-state snapshots and collected child errors; UTCZ/+00equivalent. Old raw runs remain historical weaker checks, not retroactively strict proof.
3. Pagination E2E trusted a page number before rows loaded. Hold a real request with a Promise, assert loading, then wait for200and exact response hrefs in both directions/public/organizer. No sleeps or raised timeouts.
4. Availability still used Date.now. Pass serverNow/null; unknown neutral. Lists get server_time in EventPage and advance with performance; detail uses SSE. Component/Chrome tests cover±year/start/offline/reconnect without changing business/schema rules.


## English submission review: 2026-10-26T03:11:57+05:00

The user requested a full English project and reviewer-oriented cleanup. Translate current human-facing UI/API messages, newly prepared email templates, tests and documentation while preserving routes, error codes, business transactions, schema and stored data. Existing immutable MIME/payload remain byte-identical; intentional Unicode fixtures stay as regression data. The original assignment PDF remains unchanged. Historical decisions/logs keep their recorded times and material outcomes in an explicitly condensed English edition; their original verbatim wording remains at the existing linked Git revision.

Remove only the proven-unused empty root main.py, useAction.clear, duplicate LoadState branch and explicitly allowed local caches/build reports. Keep service modules, .env, IDE files, dependency directories/locks, migration sources, tests, SQL/probes and raw load measurements. Page-specific readiness plus font completion must precede E2E overflow assertions/screenshots. Tests use isolated tmpfs projects and PostgreSQL/Mailpit; no migration is needed, no main data/volumes are changed, and commit/push/deployment remain unauthorized. Final pass counts and exact local checks are recorded in DEVELOPMENT_LOG.md; Mailpit remains an emulator and SMTP remains at-least-once with an ambiguous-accept duplicate risk.
