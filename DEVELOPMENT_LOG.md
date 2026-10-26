# Development log

Timezone: Asia/Almaty, UTC+05:00. Timestamps are actual clock observations/recording points, not invented command durations or reconstructed times of earlier chat messages. A proposal timestamp is not its approval time.

This English edition retains the historical sequence, timestamps, material outcomes and failures. Long historical command transcripts are summarized for readability; their original verbatim wording/commands remain in the existing Git history at [dff7a3766075453d6987256ef6d92f45d77e7f0d](https://github.com/Bolat141101/event-registration/blob/dff7a3766075453d6987256ef6d92f45d77e7f0d/DEVELOPMENT_LOG.md). No commits/dates were rewritten. Statements that UI/SSE/SMTP were absent refer only to the explicitly dated old stage. Current functionality is documented in README/ARCHITECTURE. New2026-10-26 actions are appended separately below.

## Initial analysis:2026-10-19

| Almaty observation | Actual work and result |
| --- | --- |
| 2026-10-19T22:29:41+05:00 | Started workspace/PDF-skill inspection; one original PDF found. |
| 2026-10-19T22:30:34+05:00 | Checked initial Git; no commits, PDF already staged, root main.py empty/untracked. PyMuPDF unavailable; pypdf read13pages, including complete1/2/9. No essay requirement found. Asked whether Mailpi meant Mailpit. |
| 2026-10-19T22:31:07+05:00 | Visually checked pages1/2/9, PostgreSQL locking/Mailpit primary references and PDF SHA256. Relevant text readable; original unchanged. |
| 2026-10-19T22:33:04+05:00 | Created requirements matrix/acceptance/A01–A09. User confirmed Mailpit; functionality still planned only. |
| 2026-10-19T22:37:22+05:00 | Created architecture: components/schema/transactions/FIFO/check-in/outbox/reminders/SSE/API/tests/risks. Requirements91lines, architecture308lines. Diff whitespace clean; untracked files need separate checking. |
| 2026-10-19T22:39:18+05:00 | Created decisions/log; checked Markdown/newlines/fences and unique sequential18G/16C/7U/9A/D01–D10. PDF hash unchanged; no application checks or commits. |
| 2026-10-19T22:39:58+05:00 | Clarified reminder reactivation and prepared-message immutability; local links/format checked. Architecture opening queued in Codex; stopped for approval, implementation not begun. |

Primary references were PostgreSQL explicit locking/isolation and Mailpit runtime/import options. They informed engineering proposals, not runtime external dependencies or extra assignment requirements. Temporary PDF images lived under /tmp/maddevs-requirements-review, outside Git. No applicable AGENTS.md was found in workspace/checked parents. PDF/openai-docs instructions were read; no model version guessed from public availability and no subagents used.

## Architecture revision and CI:2026-10-20

| Observation | Actual work and result |
| --- | --- |
| 2026-10-20T08:42:03+05:00 | Reviewed new user feedback/Git; main now had upstream origin/main and user-created ecc4273 first_commit. Root main.py still untracked. |
| 2026-10-20T08:43:20+05:00 | Checked PostgreSQL/Celery/Redis/WHATWG/RabbitMQ/Mailpit sources for isolation/ACK/redelivery and SMTP limitations. |
| 2026-10-20T08:47:15+05:00 | Simplified outbox, tokens/routes/ACID/SSE: removed leases/processing/multi-sender coordination; computed Message-ID, retained prepared_at; public email cannot restore cancelled participation. |
| 2026-10-20T08:49:34+05:00 | Added queue alternatives/future migration/extension boundaries/tradeoffs; U08–U10; implementation/tests not authorized yet. |
| 2026-10-20T08:51:18+05:00 | Four-doc verification: G18/C16/U10/A9, sections1–14, then12outbox fields, removed fields/routes absent. Only Markdown changed; HEAD/index/PDF/main.py unchanged, diff check passed. |
| 2026-10-20T15:09:43+05:00 | Inspected manifests/Compose/tests/Git and official Actions syntax. No workflow existed; preserved user's default DB port5433. |
| 2026-10-20T15:12:08+05:00 | Created workflow push/PR-main, one job, existing images/locks, isolated project/health/cleanup; made POSTGRES_PORT configurable. |
| 2026-10-20T15:13:09+05:00 | Actionlint1.7.12 and run-block bash checks passed. Ruby Psych used because PyYAML absent; no app dependency added. Local reproduction script only in /tmp. |
| 2026-10-20T15:14:14+05:00 | Complete local CI exit0: Ruff/format/Mypy,30tests0.54s, migration round-trip/check, frontend build, clean Compose and exact health JSON. Pinned images support Linuxamd64. Removed only this historical CI project's containers/volumes. |
| 2026-10-20T15:15:40+05:00 | README/decisions/diff/isolation verified. HEAD/index unchanged, ordinary services health200, no CI resources left, no push/remote Actions/next stage. |

At that historical infrastructure stage, registration/FIFO/check-in/delivery/SSE were not implemented; this is not the present state. Checkout was pinned, permissions contents:read, no credential persistence. Exact workflow commands were locally reproduced, not a claim of running GitHub's checkout/runner.

## Schema simplification:2026-10-21

| Observation | Actual work and result |
| --- | --- |
| 2026-10-21T21:23:51+05:00 | Clean HEADeb34b8c; infrastructure/health existed, no business services. |
| 2026-10-21T21:26:32+05:00 | Ordinary services running, all three domain tables empty, old schema34fields. |
| 2026-10-21T21:31:06+05:00 | Models5+9+10, new0002 and locked sequence helper/tests; local Ruff/format/Mypy passed after long-line/nested-with fixes;0001 unchanged. |
| 2026-10-21T21:31:30+05:00 | Updated docs, started full PostgreSQL/frontend no-cache checks; saved private /tmp/MadDevs-before-0002-20261021.dump outside Git. Running checks not yet claimed PASS. |
| 2026-10-21T21:32:46+05:00 |43passed/0skips; fresh tsc/Vite, container Ruff/format passed; Mypy still running at observation. |
| 2026-10-21T21:34:07+05:00 | Mypy13files, main db/api/frontend/Mailpit healthy, worker up/migrate0. Revision0002,24columns; health/OpenAPI/frontend200; main schema check matched. |
| 2026-10-21T21:35:28+05:00 | Dedicated empty test-DB CLI downgradebase/upgradehead/check passed. Populated downgrade regression explicitly refused without partial DDL; no old-revision changes or unresolved check errors. |
| 2026-10-21T21:36:40+05:00 | Verified actual names/nullability5+9+10. Existing services/ORM normalization/locked MAX helper ready; business registration/worker delivery remained future at that time. |

Executed local/container Ruff/format/Mypy, full `docker compose --profile test run --rm test`, no-cache frontend tsc/Vite, explicit test-only Alembic downgrade/upgrade/check, main upgrade/start and SQL information_schema count. New0002 retained data and forbade lossy populated rollback; no users table. Removed fields included title, duplicate email spelling, next sequence and redundant audit timestamps; backup is needed to recover those values. Presence of a schema/helper was not claimed as business correctness. No invented rollback dates, fake commit or push.

## Business services/API/outbox:2026-10-22

| Observation | Actual work and result |
| --- | --- |
| 2026-10-22T11:10:42+05:00 | Read attachment/status/diff/contracts; clean HEAD2649399 refactor db. User had saved schema/MAX helper; services absent. |
| 2026-10-22T11:11:12+05:00 |24columns sufficient; keep migrations/MAX helper/event-lock. |
| 2026-10-22T11:17:29+05:00 | Created services/outbox/HTTP/access/errors, installed validator. Initial Ruff import/format and Mypy missing-email_validator issues resolved after installation. |
| 2026-10-22T11:21:19+05:00 | Local static checks passed; started real concurrent PostgreSQL rollback/time/version/outbox tests, no worker/SQLite. |
| 2026-10-22T11:24:41+05:00 |67tests passed; added HTTP/concurrency/time cases, retaining old tests. Prepared state was only a fixture for the future sender. |
| 2026-10-22T11:27:00+05:00 |108passed/1failed of109: rollback test compared confirmed count to a pre-registration snapshot. HTTP/auth/real lock-timeout checks passed. |
| 2026-10-22T11:27:56+05:00 | Corrected that fixture snapshot and strengthened failure after outbox flush; static/config/isolation passed, reran all. No user volumes removed. |
| 2026-10-22T11:31:23+05:00 |109passed3.87s/0skips; separate business-check project with clean DB/random ports/migrate0. |
| 2026-10-22T11:32:48+05:00 | Real proxied smoke: create/register/FIFO/resume/move/check-in, expected200/201/202/401/404/409/422, counts1/1/1, one reminder per registration. SMTP not yet called. Container static passed, test downgrade done/upgrade running. |
| 2026-10-22T11:35:22+05:00 | CLI upgrade/check passed and ordinary environment updated preserving data. Review found post-start202existing/409new email disclosed registration existence. |
| 2026-10-22T11:36:03+05:00 | Unified post-start neutral202 without inserting participation/outbox; HTTP regression and time tests added. Static passed; full suite still running. |
| 2026-10-22T11:38:24+05:00 |110passed4.13s, no skip/xfail; Alembic check clean; fresh smoke started. |
| 2026-10-22T11:40:20+05:00 | Smoke/static passed, but ordinary proxy returned502 despite healthy API; main schema check passed. Only new historical smoke volumes removed. |
| 2026-10-22T11:41:09+05:00 | Logs proved stale upstream IP; added Docker DNS resolver, read official Nginx guidance, rebuilt/tested. |
| 2026-10-22T11:42:36+05:00 | Rebuilt frontend/nginx-t/health200; fresh isolated proxy regression. Backend unchanged after110passes. |
| 2026-10-22T11:45:05+05:00 | Recreated API changed192.168.16.4->.5 while frontend ID stayed; health recovered200. Main read-only schema5/9/10/head0002. |
| 2026-10-22T11:47:42+05:00 | Final110tests/all smoke passed; main healthy, test DB stopped, only new smoke resources removed. Models/migrations/helper/index/HEAD unchanged,18new files not staged; no commit/push. |

Executed `docker compose --profile test run --rm --no-deps test ruff check .`, formatcheck40files, Mypy25files, full test upgrade/Pytest/check110(102integration+8unit), dedicated test CLI downgrade/upgrade/check, Compose config/build/start, nginx-t, curl health and /tmp/MadDevs-backend-smoke.py plus /tmp/MadDevs-proxy-recovery.py in the separate business-check project. The proxy regression proved real IP change without frontend restart; initial502 was fixed, not ignored. Tests cover real event-lock waits, last place/canonical email/FIFO/cancel-vs-new/two cancels/resumes/check-ins/post-lock clock, prepared immutability, late reminder, rollback/access/hash/privacy. No schema change; SMTP/SSE/full UI were outside this historical stage. Ambiguous COMMIT/event-create idempotency limitations remained explicit.

## UTC boundaries and null descriptions

| Observation | Actual work and result |
| --- | --- |
| 2026-10-22T12:18:34+05:00 | Preserved uncommitted business changes; found astimezone OverflowError and missing description NUL validation. |
| 2026-10-22T12:21:04+05:00 | UTCDateTime/AfterValidator(as_utc), overflow->ValueError and API/service NUL validation; seven API regressions for create/move boundaries and unchanged state. Fixed Ruff long line and reran static. |
| 2026-10-22T12:21:54+05:00 |117passed4.38s/no skips; check clean on separate PostgreSQL/read-only app/tests mounts. No main data/schema/dependency change. |

Dates0001-01-01T00:00:00+01:00 and9999-12-31T23:59:59-01:00 now return422 before service execution. README removed registration/FIFO/check-in from future work. Local Ruff40/Mypy25 passed; full Docker test ran upgrade/Pytest/check. No volume deletion/commit/push.

## AsyncSession/asyncpg conversion

| Observation | Actual work and result |
| --- | --- |
| 2026-10-22T16:06:25+05:00 | Clean HEAD9a5694a; saved OpenAPI/model/revision hashes before async conversion. |
| 2026-10-22T16:18:31+05:00 | Converted endpoints/services/DB/dependency/worker/Alembic/fixtures; static passed and OpenAPI matched. Isolated async-check project/tmpfs test DB/random port55012. |
| 2026-10-22T16:20:48+05:00 | First run122passed/2failed plus teardown error: missing await in callback and cached pg_stat_activity observer. Added await and pg_stat_clear_snapshot, no weaker assertions. |
| 2026-10-22T16:23:34+05:00 |124passed8.13s, check/static/fresh tsc/Vite and clean full stack passed. |
| 2026-10-22T16:24:25+05:00 | Native container suite124passed6.19s/no skips, real HTTP contracts/codes passed; OpenAPI/models/revisions byte-identical. |
| 2026-10-22T16:26:03+05:00 | Empty test-only CLI downgrade/upgrade/current/check,24columns/head0002; DB unavailable503/503 then healthy200, worker SIGTERM clean. Initial restart omitted random-port env/conflicted5433, corrected without touching main. |
| 2026-10-22T16:28:28+05:00 | Cleanup after22m03s removed only temporary containers/network without --volumes; test volumes retained. Main environment unchanged; all previous tests preserved, no remaining failures/commit/push. |

create_async_engine/sessionmaker retained READ COMMITTED/pre_ping/hide_parameters/expire_on_commitFalse; asyncpg connect3s/lock2s/statement3s. Async SQL/transactions do not change event-first/MAX/FIFO/generation/token/reminder/freeze behavior. Core error handlers include raw asyncpg OSError/TimeoutError. Worker uses asyncio.Event; it was still a readiness probe then, not delivery. Alembic uses AsyncConnection.run_sync; test harness to_thread avoids nested asyncio.run. DSNs became postgresql+asyncpg, asyncpg0.32.0 and SQLAlchemy asyncio extras replaced psycopg without unrelated version changes; greenlet retained. Each task/session is independent, engines disposed after DDL/event-loop changes.

Executed local and Docker Ruff40/Mypy25, local pytest1248.13s, `P run --rm test`1246.19s, test-only Alembic round-trip/check, fresh isolated frontend tsc/Vite8.3.4(17modules,2.53s), complete Compose/HTTP business smoke and DB failure/recovery. P was the async-check project plus /tmp/MadDevs-async-test-port.yaml; no main volumes. Seven added tests covered sync-DSN rejection, API/readiness during locking, OSError/TimeoutError, cancellation rollback/lock release and connection failures. Workflow steps unchanged, remote Actions unrun.

## Ticket validation and two actual API processes

| Observation | Actual work and result |
| --- | --- |
| 2026-10-22T17:10:29+05:00 | Preserved uncommitted async work; recorded business/DB/revision hashes. |
| 2026-10-22T17:14:02+05:00 | Added ticket NUL validator/three regressions, read-only verification after registration POST, spawned two Uvicorn processes with separate engines/PIDs/ports. Unsupported Compose run --no-build flag removed before execution. |
| 2026-10-22T17:15:22+05:00 |129passed10.24s/check/static passed; improved process teardown and DB ticket comparison, reran. |
| 2026-10-22T17:15:45+05:00 |129passed9.81s/no skips, hashes unchanged and AST confirms no business.join creating the HTTP result. |
| 2026-10-22T17:17:57+05:00 | Offset process clocks1s to identify winner timestamp; verified no overwrite after losers/repeats. Final129passed8.73s/static/check; business/schema/migration hashes still match. |

Ruff41/Mypy25 and full read-only-mounted test suite ran against async-check tmpfs only. Two real HTTP processes wait on a held event lock, observed via refreshed PostgreSQL stats; capacity1 gives202/202,1confirmed/1waiting,one ticket/queue1/four outbox identities. Check-in gives200/409, one winner timestamp/count, repeats409 through both. Teardown treats forced kill as failure. NUL returns422 before SQL. Existing registration HTTP test performs SELECTs for one registration/two ticket-reminder outbox rows instead of calling join to manufacture its result. No new dependencies/schema/infrastructure, main data access, git add/commit/push.

## Core/Notifications infrastructure split

| Observation | Actual work and result |
| --- | --- |
| 2026-10-22T22:24:48+05:00 | Clean HEAD6c20757; saved backend/frontend/OpenAPI hashes. Core still used administrator events; chose separate bootstrap/two ordinary roles without recreating volume. |
| 2026-10-22T22:31:02+05:00 | Created independent Notifications/storage/migration/tests/bootstrap/Compose, pinned existing-compatible dependencies; local static passed, builds/Core suite started. |
| 2026-10-22T22:33:48+05:00 | Core129passed9.09s, Notifications21passed0.86s/check. Saved private main backups/hashes; main had0rows, so separately seeded a persistent test volume to prove populated preservation. |
| 2026-10-22T22:35:34+05:00 | Core129passed13.64s under core_app_test. Seeded2events/4registrations/5outbox plus Notifications payload/MIME survived first/repeated bootstrap by hashes. After backup, historical main bootstrap ran with same PostgreSQL container/volume. |
| 2026-10-22T22:36:56+05:00 | Both services on existing volume; ordinary roles, reverse CONNECT42501, heads0002/0001/check passed. Core health/events200 with Notifications stopped; isolated HTTP proved201/202/202,FIFO,fourpending outbox. |
| 2026-10-22T22:41:22+05:00 | Extra real health checks: ownPASS, foreign/missing DB/wrong-password3FAIL due raw asyncpg errors. Fixed safe503/readiness class-only logging; test_health collection-name collision fixed with test packages, no tests deleted. |
| 2026-10-22T22:42:22+05:00 | Notifications25passed0.71s/check; final image built; tracked Core/frontend/OpenAPI/old revision hashes unchanged. |
| 2026-10-22T22:43:55+05:00 | Final image25passed1.51s/static18files/Mypy6, Core41/25static; fresh tsc/Vite17modules1.21s. Historical main Notifications updated/healthy200. |
| 2026-10-22T22:46:27+05:00 |24Core/7Notifications columns, original rows/container/mount hashes retained; bootstrap/migrations0. Temporary project down without volumes; main .env/index unchanged,29newuntracked files, no commit/push. Relay/SMTP/UI not started in that stage. |

Notifications gained own namespace/dependencies/Docker/Alembic and seven-field jobs with nullable MIME; no storage column was claimed as inbox/sender correctness. Repeatable shell/psql bootstrap creates/isolate roles/DBs and transfers known ownership without DROP/data deletion/cluster-wide REASSIGN. Secret values were not printed. Historical /tmp/MadDevs-notifications-backup-20261022 dumps were0600/outside Git. Main bootstrap during this earlier authorized stage is recorded honestly; **the2026-10-26 readiness task does not repeat it**.

Checks used notifications-check-20261022 with .env.example/random ports: all Core129 and Notifications25, static, migrations/guards, fresh frontend build, populated bootstrap hashes, reverse42501, Core independence and business writes without Notifications. Original literal commands and backup/upgrade details remain in the cited Git revision. No main downgrade/deletion/volume recreation or agent commit/push.

## Ordinary-role CI and repeated bootstrap

| Observation | Actual work and result |
| --- | --- |
| 2026-10-22T22:59:20+05:00 | Preserved dirty infrastructure changes; found core_app_test existed but normal Core test still used events_test administrator. |
| 2026-10-22T23:04:52+05:00 | Switched role/added privilege fixture/separate bootstrap target; built bootstrap-check project with tmpfs !reset override and separate image tags, no main volumes. |
| 2026-10-22T23:06:05+05:00 | Core129/12911.32s, Notifications25/251.14s, migration checks passed. Fixed Ruff import order/rebuilt. |
| 2026-10-22T23:08:02+05:00 | New repeated-bootstrap1/1passed2.68s. First diagnostic query needed relkind::text because asyncpg returned bytes; exact42501 checks retained, strict Mypy clean. |
| 2026-10-22T23:09:28+05:00 | Final Core129/12910.43s/no skips, static/fresh tsc/Vite/startup/health/stop-service independence passed; both runtime schema checks clean. |
| 2026-10-22T23:12:53+05:00 | Inspect proved tmpfs/0named mounts for db/test-db/mailpit; project-scoped down exited0 without --volumes. Only test infrastructure/workflow/docs changed; no main/old SQL/migration/business/frontend mutation or commit/push. |

The test seeds schedule_version3, confirmed/waitlisted/cancelled generation2, tickets/check-in/hash/queue7, sent/pending/failed outbox and three Notifications jobs with MIME/attempt errors. Two actual bootstrap.sh calls compare complete rows/Alembic/owners/ACL/indexes/constraints/default privileges, ordinary-role DML/DDL/READ COMMITTED and real cross-DB denials before/after. Cleanup targets its own UUIDs only. Total155unique tests(129+25+1), no disabled checks. C=/tmp/maddevs-bootstrap-ci-compose used only its guarded tmpfs override and .env.example; runtime/static/full/migration/smoke commands locally matched CI, not a remote run.

## Async HTTP relay and durable inboxv1

| Observation | Actual work and result |
| --- | --- |
| 2026-10-22T23:24:43+05:00 | Clean Git; inspected Core probe worker/outbox and Notifications without inbox. |
| 2026-10-22T23:29:10+05:00 | Addedv1DTOs/async relay/commit-before-ACK/new0003forwarded. Existing business/API/scheduling untouched. httpx0.28.1 moved to runtime, pip-compile locks retained pinned versions. |
| 2026-10-22T23:33:23+05:00 | Core strict Mypy passed; real DB/API regressions/schema and separate project created. |
| 2026-10-22T23:36:12+05:00 | Notifications48/48. First Core upgrade double-applied CHECK naming convention; fixed only new0003withop.f after rollback. Core149/149, then data-preserving/guard regression added. |
| 2026-10-22T23:43:59+05:00 | Real outage/SIGKILL/restart/duplicate202/conflict409/auth401 passed. TCP proxy lost response after committed inbox; Corepending then forwarded on retry/restart. Added total asyncio deadline beyond phase timeouts. |
| 2026-10-22T23:48:01+05:00 | Core152/152 incl deadline/crash-after-prepare, static passed; docs prepared, numeric date rejection strengthened to match JSON Schema. |
| 2026-10-22T23:53:58+05:00 | Final Core152/15228.09s and all static passed; repeated real smoke with final images. |
| 2026-10-22T23:55:54+05:00 | Notifications52/521.30s, infrastructure3/33.88s/no skips. Actual Core24cols,4forwarded+4futurepending/sent0; Notifications7cols/4unique pending/mimeNULL/attempts0; both schema checks clean. |
| 2026-10-22T23:58:48+05:00 | Health200/diff clean, tmpfs/0named mounts verified; down0withoutvolumes. Main unused,14newuntracked files, no commit/push. |

Ruff/import formatting and infrastructure MYPYPATH namespace issues were fixed without ignores. New modules: relay prepare/run_once/finish/backoff, independent contract DTOs/schema, inbox insert-on-conflict/normalized JSON, protected API, worker network lifecycle and forwarded migration. ID/JSON froze before HTTP; SQL did not span network. Repeated inbox acceptance never resets MIME/status/attempts. Core prepared retries remain historical through business changes because ACK may be lost; exhaustion after8started attempts stays failed for explicit intervention. No SMTP/MIME rendering/leases/Redis/Kafka/Celery yet at that historical point.

C=/tmp/maddevs-relay-compose selected relay-check-20261022, tmpfs/random ports/separate tags; only its smoke worker used poll0.2/backoffcap10/max20. Executed config/build, Core static46/Mypy28/full152, Notifications22/Mypy9/full52, infrastructure4files/full3, runtime start/check/health and complete relay_smoke.py phases create/outage/recover/lost-response/recover. Total207Pytest/no skips plus actual TCP smoke. Business/old migrations/frontend unchanged; remote Actions unrun.

## Relay head-of-line blocking

| Observation | Actual work and result |
| --- | --- |
| 2026-10-23T08:38:01+05:00 | Preserved20tracked changes/14new files from HTTP stage; reviewed relay/worker/tests. |
| 2026-10-23T08:44:13+05:00 | Added bounded distinct-event heads, UUIDcursor/cutoff/NOWAIT and post-rollback55P03 handling. Other DB errors propagate; FIFO/API/schema unchanged. |
| 2026-10-23T08:50:07+05:00 | Started own hol-check build, tmpfs/random ports/separate tags. |
| 2026-10-23T08:54:32+05:00 | Core160/160; remaining suites and negative old-algorithm control started. |
| 2026-10-23T08:57:46+05:00 | Notifications52/52,infrastructure3/3; eight new PostgreSQL regressions pass. Old selection in disposable read-only mount failed expected TimeoutError1.68s; restored implementation passed all8. |
| 2026-10-23T09:00:57+05:00 | Running-service lockA did not stop Bforwarded; after unlock Aforwarded. Started old CI TCP failure/restart/ACK-loss suite. |
| 2026-10-23T09:02:39+05:00 | TCP suite passed. Extended strict Mypy found two nullable accesses in imported old test; explicit row existence asserts added, no suppressions. |
| 2026-10-23T09:04:36+05:00 | Final Core160/16016.52s/static clean; runtime Alembic both clean. |
| 2026-10-23T09:06:53+05:00 | Final diff/status/settings/docs recorded. |
| 2026-10-23T09:08:44+05:00 | Tmpfs/no named mounts verified; down0withoutvolumes. Main untouched,15untracked paths excluded by normal stat, no commit/push. |

DISTINCT ON gives one ready `(available_at,id)` head per event; UUIDround-robin/cutoff traverses bounded pages fairly, one HTTP per call. Busy pages pause then continue rather than blacklist/spin. Only55P03after full rollback is skipped; skipped row payload/prepared_at/attempts/deadline/error do not change. Tests cover pending/prepared/multiplemessages/multipleblockedpages/update locktimeout/otherDBerrors/new arrivals/idle/restart. Relative retry backoff remains; global oldest order across independent events was deliberately replaced, not strict delivery ordering after faults.

Executed CoreRuff47/Mypy29/full16016.52s; Notifications22/9/full523.81s; infrastructure4/full35.75s; new8tests0.90s; fresh tsc/Vite17modules; all Compose/migration/health/independence/HOL/TCP smoke passed. Total215unique/no skips, expected old negative FAIL separate; no SMTP implemented by this fix.

### Independent repeat verification

| Observation | Actual work and result |
| --- | --- |
| 2026-10-23T09:11:41+05:00 | User requested recheck; dirty tree preserved, no app changes. |
| 2026-10-23T09:12:59+05:00 | Rebuilt isolated images; Core160passed13.58s, check/static47/29passed, all business/migration/two-process/relay regressions. |
| 2026-10-23T09:13:41+05:00 | Notifications52passed1.18s/infrastructure3passed3.99s, all static/fresh tsc/Vite/startup. Real HOL: lockedApending/attempt0/unprepared, Bforwarded, thenAforwarded/attempt1. |
| 2026-10-23T09:14:23+05:00 | Complete real outage/SIGKILL/ACKloss/restart/duplicate202/conflict409/auth401 smoke passed; Core still200/201/202during outage. |
| 2026-10-23T09:15:19+05:00 | Five repetitions of10blocking/API-process tests passed4.15/4.21/4.13/4.43/3.62s, not50new unique tests. Both schemas clean;4forwarded/4futurepending/no failed orsent, all health/assets200,Mailpit0. Tmpfs/no named mounts/logs clean. |
| 2026-10-23T09:15:38+05:00 | Notifications4unique pending/mimeNULL/attempts0. One-off diagnostic import used wrong namespace; corrected to notifications_app.models/db, no service code change. |
| 2026-10-23T09:16:26+05:00 | Down0withoutvolumes, main untouched/diff clean.215unique passes plus50repeat executions, journal only changed in recheck; no commit/push. |

The original HOL defect was not reproduced after the fix. This was still a historical pre-SMTP/UI stage; no claim of whole-project completion or remote Actions was made.

## Async SMTP sender

| Observation | Actual work and result |
| --- | --- |
| 2026-10-23T09:39:07+05:00 | Clean HEADc4215d3; reviewed outbox/relay/inbox7fields/CI and retainedv1historical commands. User authorized SMTP only then. |
| 2026-10-23T09:42:50+05:00 | Implemented render/load/async adapter/prepare-send-finish; MIME/attempt/backoff commit precedes SMTP. First pip-compile cache path unavailable; /tmpcache succeeded, only aiosmtplib5.1.3 added, other pins retained. |
| 2026-10-23T09:44:52+05:00 | Settings/worker/retry/Compose/test-mailpit/tests ready; strict Mypy passed; checked official aiosmtplib raw-send/error and Mailpit docs. |
| 2026-10-23T09:47:53+05:00 | Isolated images built; Core160passed10.73s/check; main data untouched. |
| 2026-10-23T09:48:28+05:00 | Notifications89passed/3failed: real lazy HeaderParseError plus two incorrect async-with pytest.raises tests. Fixed both causes. Infrastructure8passed/1failed searched raw quoted-printable instead of decoded MIME; corrected test, no disabling. |
| 2026-10-23T09:50:22+05:00 | Notifications92/92; real SMTP4xx/5xx/disconnect/timeout/dedup/restart/MIME/budget/replay passed; safe failed/pending diagnostics. |
| 2026-10-23T09:52:08+05:00 | Existing real HTTP outage/SIGKILL/ACKloss/restart/ID conflict smoke passed; new two-role/test-Mailpit Core time/cancel/resume/move integration ran. |
| 2026-10-23T09:53:11+05:00 | Infrastructure11passed18.16s; real SMTP pause->pending, kill->restart->sent and accepted DATA/lost reply recovery passed. Four runtime emails matched stored headers/decoded body, one current-store copy each. |
| 2026-10-23T09:57:40+05:00 | Subprocess retry denied without acknowledgement, requeued only failed without ID/JSON/MIME change, repeated pending reset rejected. Notifications93passed4.28s; unchanged frontend fresh tsc/Vite passed. |
| 2026-10-23T09:58:48+05:00 | Core24cols/4forwarded+4futurepending, Notifications7cols/4sent/MIME; both checks/health200, nine services running, four tmpfs stores/no named mounts/log failures. |
| 2026-10-23T09:59:38+05:00 | Added hide_input_in_errors/startup regression; rebuilt final Notifications. Public contract/business/migrations unchanged. |
| 2026-10-23T10:01:26+05:00 | Final Notifications94passed4.03s/static31/Mypy15; new API/sender SMTP recover retained four sent MIME/copies. Final infrastructure repeat started. |
| 2026-10-23T10:02:57+05:00 | Infrastructure11passed14.96s; total265unique/no skips(160+94+11), static/schema/health/HTTP/SMTP all successful. |
| 2026-10-23T10:03:54+05:00 | Logs/4tmpfs/no paused stores verified; down0withoutvolumes.18tracked+12new files, no main data/schema changes/commit/push. |

New MIME/SMTP/sender/worker/clock/retry modules, test-only Mailpit, settings and aiosmtplib were separate from Core business. Core's worker startup wording was updated; bootstrap test alone acquired Notifications runtime dependencies through build context. Real tests prove immutable Date/ID/envelope, transaction-free SMTP, permanent/temporary error policy, explicit CLI and double freeze semantics. SMTP DATA accept before lost response remains ambiguous; no general exactly-once/eventual guarantee beyond the automatic attempt budget. No UI/SSE was added in this historical SMTP stage. Exact static/full/runtime commands used smtp-check tmpfs/separate tags, including original relay_smoke.py and new smtp_smoke.py, and are retained in the original command transcript.

## Damaged MIME cannot block sender

| Observation | Actual work and result |
| --- | --- |
| 2026-10-23T13:47:32+05:00 | Preserved uncommitted SMTP work; inspected load_prepared/Sender/tests, no schema/business change. |
| 2026-10-23T13:48:51+05:00 | Seven new pre-fix tests all failed: lazy From/To quote/a@[ parsing caused IndexError/AttributeError, plus explicit parser exception cases. Expected negative control, not disabled tests. |
| 2026-10-23T13:50:39+05:00 | Local parse/header guard converts IndexError/AttributeError/HeaderParseError to safe ValueError.18MIME units passed0.10s/static clean; no global sender catch. |
| 2026-10-23T13:51:32+05:00 | Core160passed13.39s, migration/static checks passed. |
| 2026-10-23T13:53:08+05:00 | Infrastructure11passed16.19s on real test-DB/Mailpit; dependency download took time, no new package added. |
| 2026-10-23T13:53:50+05:00 | Notifications105passed4.70s/static/check; total276unique/no skips(160+105+11). |
| 2026-10-23T13:55:10+05:00 | Tmpfs/no named mounts verified, isolated down0withoutvolumes, main untouched/diff clean, no commit/push. |

Only MIME parser, unit/sender regressions and log changed in that fix; existing Sender ValueError handling already marked failed with safe error and continued. Eleven cases: four damaged-header units, three parser-error units, four real PostgreSQL queue cases. The damaged job preserves payload/MIME/attempt/deadline, invokes neither SMTP nor renderer, and the following valid job sends. The negative command selected damaged_address/parser_errors before repair; all full suites passed afterward.

## IDNA2008 email identity

| Observation | Actual work and result |
| --- | --- |
| 2026-10-23T15:34:37+05:00 | Clean HEAD57aab8b; found Core ignored validated ascii_email while Notifications used IDNA2003. User authorized collision-audited migration, no merge/delete/message rewriting. |
| 2026-10-23T15:36:47+05:00 | Historical main own-role READ ONLY preflight:0registrations/changed/invalid/collisions, no addresses printed or main upgrade/restart. Validator confirmed faßIDNA distinct fromfass, dots/+suffixes retained. |
| 2026-10-23T15:38:45+05:00 | Independent canonical helpers, pre-lookup/ORM normalization, new0004frozen-policy atomic audit/ASCII CHECK/email-only UPDATE. Outbox/Notifications messages untouched; validator2.3.0/dnspython2.9.0 pins aligned, others unchanged; Alembic hides binds. |
| 2026-10-23T15:42:26+05:00 | Read-only audit CLI/migration/HTTP/two-process/legacy tests and isolated IDNA build; fixed SQL-string formatting without skipping checks. |
| 2026-10-23T15:44:45+05:00 |9Core email units/25MIME units and strict Mypy all services/infra passed; cross-service references/SMTP RCPT added. |
| 2026-10-23T15:45:34+05:00 | Core177passed26.62s, populated preservation/abort collision including cancelled/invalid legacy/read-only audit/round-trip; concurrent Unicode/Punycode requests yield one confirmed/two logical jobs. |
| 2026-10-23T15:46:29+05:00 | Notifications116passed7.26s; legacy JSON and correct MIME casing/bytes retained; wrongfass failed/noSMTP/nextsent/manualretryrejected. Real RCPT user@xn--fa-hia.de without SMTPUTF8. |
| 2026-10-23T15:47:31+05:00 | Infrastructure21passed32.85s, four full-path parameters/reference policy/roles/bootstrap. Real service smoke: equivalent identity and four distinct correct ASCII emails includingfass/dots/+tag. |
| 2026-10-23T15:50:57+05:00 | Existing real HTTP/SMTP outage/kill/ACKloss/DATA-loss/recovery passed; runtime audit8total/changed0/invalid0/collisions0, both schema checks clean. |
| 2026-10-23T15:53:30+05:00 | Corehead0004/24cols/8ASCII registrations/8forwarded+8futurepending; Notifications7cols/8sentfrozen. Old revisions/business/API/relay/frontend unchanged. |
| 2026-10-23T15:56:54+05:00 | Nine services healthy/health200/logs clean/four tmpfs/no named or paused mounts; down0withoutvolumes.20tracked+8new files, main not migrated/restarted, no commit/push. |

Total314unique(177+116+21)/0skips. No automatic merge/winner selection or frozen recipient repair.0004 updates only registration email after complete locked audit; downgrade cannot reconstruct prior spelling without backup. Already sent wrong mail cannot be retracted. New modules/tests cover audit, canonical identity and every retry's frozen recipient comparison; cross-service SMTP reaches actual Mailpit. Main inspection was historical read-only only, and no UI/SSE was added by this step.

## Configuration diagnostics without secrets

| Observation | Actual work and result |
| --- | --- |
| 2026-10-23T16:02:28+05:00 | Inspected Settings/API/worker/CLI/Alembic while preserving IDNA20tracked+8new files; no main data access. |
| 2026-10-23T16:07:17+05:00 | Pre-fix Core config9failed/6passed exposed real startup stderr leaks; an initial wrong root test path ran nothing, corrected invocation reproduced them. Added hide_input/repr protection and Alembic bind hiding. Targeted20Core/33Notifications passed, strict Mypy33/18/static clean; isolated config project built. |
| 2026-10-23T16:09:00+05:00 | Core186passed19.99s and existing IDNA/concurrency/migrations/check/static passed. |
| 2026-10-23T16:09:44+05:00 | Notifications124passed12.69s/check and infrastructure static6files passed. |
| 2026-10-23T16:10:50+05:00 | Infrastructure21passed24.77s/two DBs/Mailpit/HTTP/SMTP/bootstrap; runtime health200, logs clean/fourtmpfs/no named mounts. |
| 2026-10-23T16:12:09+05:00 | Down0withoutvolumes/diff clean,27tracked+8priornew files; old revisions/business/API/relay/sender/inbox/Compose/frontend unchanged, no commit/push. |

Total331unique(186+124+21),0skips;17added regressions(9Core+8Notifications). Eight subprocess startup paths reject invalid DSNs/tokens before network while retaining field/cause/traceback but not fictitious secrets. Formatted errors/repr protection is not model_dump/errors()/environment collector sanitization. No broad exception suppression/new dependencies/schema changes; prior IDNA work retained. This diagnostic stage did not rerun the full fault-smoke scripts; the following backend readiness stage did.

## Backend readiness before the UI stage

| Observation | Actual work and result |
| --- | --- |
| 2026-10-23T16:26:40+05:00 | Preserved27tracked+8new prior changes. Reread/rendered PDF1/2/9 via bundled pypdf/Poppler, original hash matched; pdftotext unavailable but PDF readable. No main access/commit/push. |
| 2026-10-23T16:30:50+05:00 | Final isolated tmpfs build completed; removed unused Core SMTP declarations only after reference audit; Notifications SMTP unchanged. Docs separated mandatory UI/live/two-client evidence from extra service/token/version/IDNA choices. |
| 2026-10-23T16:35:46+05:00 |186Core19.57s+124Notifications6.66s+21infrastructure22.15s,0skips; explicit test-only upgrade/downgradebase/upgrade/check and all static53/32/6formatted,33/18/6Mypy passed. Runtime pipeline exit0. |
| 2026-10-23T16:36:55+05:00 | All four stores tmpfs/no named mounts/log failures; docs honest that UI/SSE/browser acceptance were still pending. |
| 2026-10-23T16:39:52+05:00 | Core0004/24cols,13forwarded/4futurepending/1cancelled, no SMTP settings. Notifications0001/7cols/13sentfrozen/failed0; both schema checks/health good. Down0withoutvolumes; main untouched,29tracked+8new prior changes retained. |

The API smoke covered create/list/detail, neutral IDN repeats, cancel/repeat/FIFO, resume/tail/stale generation, repeated/stale moves,401/422 including UTC extremes/NUL, concurrent200/409check-in, old ticket404, counts1/1/1 and post-start neutral202without insertion. Actual Mailpit delivered all active tasks including two reminders/two moves. Original CI outage/SIGKILL/commit-before-ACK/duplicate/conflict/auth and SMTP pause/DATA-loss/frozen-retry scenarios passed unchanged. Negative old-defect controls in disposable copies produced3Core-email,2Notifications-email,5Core-secret and4Notifications-secret expected failures; import/collection failures were not accepted as sensitivity.331unique tests and real faults were backend evidence, not a then-absent frontend. Remote Actions unrun.

## Frontend and live SSE

| Observation | Actual work and result |
| --- | --- |
| 2026-10-23T19:55:44+05:00 | Clean HEADbef709c, user had committed prior work. Read actual API/services/access/frontend/PDF; authorized UI/SSE, preserved business rules. |
| 2026-10-23T20:09:05+05:00 | Public EventView/server_time SSE and organizer key verification, SQL closed before yield; built real React screens with warm date rows/no invented fields or fake operations. |
| 2026-10-23T20:18:02+05:00 | After Ruff/type-fixture fixes and replacing obsolete “SSE absent” assertion(187passed/1failed),188Core28.48s+124Notifications6.50s+21infra29.77s/check/static55/33passed. Tmpfs UI project ready at55052/Mailpit55051. |
| 2026-10-23T20:19:24+05:00 | First actual Chrome1passed/3failed: two tests reloaded memory-only organizer key, fixed login at target route; real missing hashchange handling fixed fragment consumption/remount without token storage. Screenshots/CUA empty state reviewed, no overflow. |
| 2026-10-23T20:26:23+05:00 |16Vitest/Prettier/tsc/Vite passed. Dev-only test/format dependencies; fixed formatter stops and slow private GET starvation without cancelling every heartbeat read.409refreshes real generation, malformedJSON/network errors remain honest. |
| 2026-10-23T20:31:31+05:00 | E2E2passed/2failed; full business/mail path passed, but initial autofocus skipped skip-link and offline did not close SSE. Fixed focus/scroll and offline/online handling. |
| 2026-10-23T20:34:07+05:00 | Stronger E2E checked actual emailed origin and exposed random port vs PUBLIC_APP_URL. Added guarded tmpfs overlay/start script, resolve origin before sender; only disposable old-origin test stores recreated, frozen MIME never rewritten. |
| 2026-10-23T20:38:11+05:00 |4E2Epassed34.8s: real email origin/two clients/FIFO/resume/move/check-in/live/IDN/invalidtoken/keyboard/404/network409. Notifications32/16 and infrastructure6/6static passed. |
| 2026-10-23T20:41:41+05:00 | Reviewed wide/narrow actual list/event/ticket/organizer/check-in; CUA empty/login/detail. Fixed preventScroll focus/scroll-to-top capture and used-ticket copy; removed unused old api/health.ts.16units/static/build passed. |
| 2026-10-23T21:46:26+05:00 | Final script rebuild/start retained55056/publicorigin; docs updated, last browser check started. No continuous work history invented between observations. |
| 2026-10-23T21:48:05+05:00 | E2E3passed/1failed: datetime-local omits zero seconds, fill rejected full form. dateInput now omits :00 when appropriate; added round-trip unit, timezone/business rules unchanged. |
| 2026-10-23T21:50:05+05:00 |17units/format/tsc/Vite/rebuild and4E2E34.5s passed, one header/no overflow, port retained. |
| 2026-10-23T21:51:08+05:00 | Extra runtime log check failed on asyncpg termination cancellation. Real cancellation regression reproduced1failed/2deselected; not ignored or suppressed. |
| 2026-10-23T21:55:05+05:00 | Shield only short read/session cleanup, no scope across yield; existing pinned AnyIO4.15.1 declared direct. Strict cancellation branch/type checks fixed without ignore; static passed. |
| 2026-10-23T21:56:45+05:00 | Final sequential backend/static/migration/browser/log pipeline started; no premature PASS claim. Old CUA stream closed, preview retained. |
| 2026-10-23T22:02:04+05:00 | Pipeline exit0:189Core+124Notifications+21infra=334unique,no skips;17Vitest/tsc/Vite and4E2E35.3s. Collect-only confirmed189. Fresh logs/health200/cleanup/pool regression passed, tmpfs/no named stores; later changes documentation only. |

Executed C=/tmp/maddevs-ui-compose static/full upgrade/test/check, frontend pinned Node24 formatting/Vitest/TypeScript/Vite and actual host Chrome through /tmp/maddevs-run-ui-e2e.py. New cancellation test failed on previous code then passed. Secrets never in browser storage/query/trace/video; successful operations never mocked. Actual screenshots under /tmp/maddevs-ui-visual were reviewed. At stage completion a disposable preview remained at55056/Mailpit55054 for user review; main installation unchanged. Cross-browser/full assistive-technology audit, clean handover, exact model metadata, essay and approved publication were still open then.

## Server time, queue ownership and load:2026-10-24

| Observation | Actual work and result |
| --- | --- |
| 2026-10-24T13:35:22+05:00 | Clean HEADe64a564; inspected frontend/SSE/transactions/relay/sender/CI and created separate baseline/stages tmpfs projects. |
| 2026-10-24T13:42:43+05:00 | Exploratory baseline200POST->200×202,10/190,45.72req/s,p502672.66ms/p954145.73ms,14lockwaiters,move1465.73ms,100SSE/8s530commits,duplicates/deadlocks0. Under other Docker activity; not controlled comparison or production proof. |
| 2026-10-24T13:44:33+05:00 | Frontend17units/format/tsc/Vite and6ChromeE2E1.2m;±365day device-clock tests/cancel/resume/move/start/offline/reconnect. Actions use server_time/performance; unknown disabled, Core authoritative. |
| 2026-10-24T14:29:20+05:00 | Recorded stage2/3 choices: reserved AUTOCOMMIT session mutex/watchdog for relay/sender, safe queue/failed-ID/age/heartbeat/manualretry. No leases/broker/tables/exactly-once. Tests cover other process, concurrent iteration, cancellation/restart and killed ownership connection/frozenMIME. |
| 2026-10-24T18:03:11+05:00 | Continued after user message; two controlled old/current repetitions and2API/1000SSE all exit0. Preliminary both-version SSE errors from reusing POST pool fixed by fresh pool without retries or relaxed all-client requirement. |
| 2026-10-24T18:12:14+05:00 | Added populated0005index round-trip/full-tablehash/index/24cols/check regression.196Corepassed25.62s; ticket/check-in/frozenpayload preserved, infrastructure10files static passed, old revisions untouched. |
| 2026-10-24T18:13:39+05:00 | Stages runtime rebuilt/healthy; Core99forwarded/37pending/failed0/due0,Notifications99sent/failed0/due0. Heads0005/0001,5+9+10cols,health/page200, current screenshots and syntax reviewed. |
| 2026-10-24T18:16:23+05:00 | Stages cleanup down withoutvolumes/ps empty; load projects trapped cleanup. Old user preview/main untouched. Old revision diff clean;42tracked+22new, no gitadd/commit/push. |

Shared SSE queue1/per-event/process and last-listener cleanup replaced per-client reads. Private GET changes/reconnect plus10s fallback avoids merely moving the polling load. Added bounded public/organizer pages, two-index0005, three typed atomic reschedule SQL statements, rollback/query-budget tests, Nginx30r/s/burst1000/sharedSSE2000/trusted IP overwrite/process cap. Business READ COMMITTED/event-lock/FIFO stayed in PostgreSQL.

CI retained old checks/fault probes and added tmpfs Playwright/edge/readiness/alwayscleanup, correct public origin between steps. Real local outage/kill/restart/lostHTTPACK/ID202/conflict409/auth401/pausedSMTP/lostDATA/frozenMIME/NAT/XFF/429passed. Linux-container/remote Actions not claimed; actual local browser was Chrome/Node24.

Intermediate failures retained: overloaded concurrent functional/load runs yielded Core182pass/3fail/5errors and Notifications124pass/1fail; quiet corrected runs passed without increasing test deadlines. One rollback test patched a removed function and was adapted with assertions retained plus mid-SQL rollback coverage. Static type errors were fixed. Browser tests found real initial REST failure leaving the page stuck; SSE now recovers transport/503but not404. Clock boundary navigation was made deterministic using actual API timing, not sleeps. No skip/xfail/suppressed failures.

Final stage checks:195Core32.18s before the added migration-only test, then19625.62s;128Notifications10.52s;21infra24.08s;18Vitest/tsc/Vite;9ChromeE2E43.0s. Ruff63/Mypy39Core,36/19Notifications,10/10infra passed. Full explicit test-only upgrade/downgradebase/upgrade/check both DBs and populated index/data checks passed. Total345Pytest,18unit,9E2E. Exact final commands are preserved in the original Git transcript; pipeline logs were /tmp/maddevs-final-core.log and /tmp/maddevs-phase4-*.

Controlled load details and unmodified rawJSON/EXPLAIN remain docs/LOAD_TESTING.md and docs/load-results/2026-10-24.json. Before A/B:p95991.74/1167.20ms,move405.54/361.95ms,100SSE791/824commits/8s,400mail6.495/6.538s. After A/B:p951838.41/1036.31ms,move65.56/32.99ms,26/12commits,mail48.606/8.443s.2API/1000SSE:p951224.39ms,move77.27ms,34commits,mail9.129s. All recorded200×202,10/190,duplicates/deadlocks0,400forwarded/Mailpit400/failed0. The slow48.606s/maxdue93.297s outlier lacked ERROR/WARNING in the saved tail; its cause was not established. Speedup of registration/SMTP and production capacity was not claimed. Later audit below weakened the evidentiary status of the old probe's exit0; raw measurements were not rewritten.

## Four audit corrections

| Observation | Actual work and result |
| --- | --- |
| 2026-10-24T19:32:26+05:00 | Preserved42tracked+22new prior changes; created audit tmpfs project/.env.example/ordinary test roles, no main data. |
| 2026-10-24T19:50:25+05:00 |11ChromeE2Epassed51.3s plus5pagination repeats12.9s; real CI HTTP/SMTP/edge probes passed. Added actual HTTP SSE lock_timeout/EOF/unlock/reconnect/update regression; final Core199passed31.65s. |
| 2026-10-24T19:52:13+05:00 | Corrected strict probe2API/1000SSE exit0:200×202,10/190,600pending,1000active/9000valid messages/stale0/errors0/deadlocks0/duplicates0.400forwarded/Mailpit400/failed0,drain10.308s,maxdue23.458s. JSON/EXPLAIN retained, fresh project cleaned. |
| 2026-10-24T20:08:29+05:00 | Final health/page200/aware time; workers healthy,Core47forwarded/28pending/failed0/due0,Notifications47sent/failed0/due0. Audit downwithoutvolumes/ps empty; old migration/diff checks clean, main/preview unchanged, no commit/push/deploy. |

Negative controls before repair: failed SSE producer1failed/4deselected with a real SQL error and reconnect before old close; unchanged weak probe predicates8failed/2passed; clock indicator±year2failed and deliberately gated old pagination1failed. Logs /tmp/maddevs-audit-{sse,probe,clock,pagination}-before.log. They are expected sensitivity checks, not disabled normal tests.

Root causes/fixes: retire dead LiveHub topic by identity before cleanup; require complete200×202/10–190/600pending/no duplicates/deadlocks/fresh valid expected-stateSSE and collect child errors; await actual page response/exact DOM IDs after a Promise barrier; replace Availability Date.now with serverNow/null and add page server_time/performance clock. UTCZ/+00offsets compare as one instant. Initial SQL failure, reconnect-before-close, real HTTP lock-timeout, device±year/start/offline and unsafe load results are covered without sleeps masking races. Existing schema/migrations/business/SMTPfreeze remain.

Final audit:199Core31.65s+128Notifications8.64s+32infrastructure26.00s=359Pytest;22Vitest/3files/format/tsc/Vite;11ChromeE2E51.3s plus5pagination repetitions. Static/migration/Compose/health/HTTP/SMTP/edge checks all passed. The original command transcript specifies C=/tmp/maddevs-audit-compose and full explicit migration round-trips only on test DBs; logs /tmp/maddevs-audit-{core-final,notify-full,infra-full,frontend,runtime,e2e-full,pagination-repeat,load-strict}.log. Formatting/config mismatches were corrected and checks rerun, not skipped. Remote Actions/Linux-browser step remained unrun, production/long soak outside scope.


## English submission review: 2026-10-26

| Almaty clock observation | Actual work/result |
| --- | --- |
| 2026-10-26T02:32:17+05:00 | Began this task; Git was clean at dff7a3766075453d6987256ef6d92f45d77e7f0d. Inspected runtime references, Compose, source, tests and documents before editing. Root main.py was empty and unused; useAction.clear had no caller; the two EventList LoadState branches were identical. |
| 2026-10-26T03:02:37+05:00 | Rechecked original PDF pages 1/2/9, rendered and inspected page 9; SHA256 remained 3b7934746efef38066c6164c68df93ee6a0175c7ac7af8472372537a609539d7. Remote origin/HEAD were verified against the actual GitHub repository. |
| 2026-10-26T03:06:56+05:00 | Observed fresh-checkout build/start verification: local Git clone plus this task's uncommitted patch, no copied node_modules/.venv/dist, public example settings only, separate tmpfs project. This does not claim the changes have been published on GitHub. |
| 2026-10-26T03:11:27+05:00 | Observed final clean-checkout runtime and browser runs complete with exit 0: all HTTP/SMTP/edge probes and 12 Chrome E2E tests, 49.5s. Reviewed the English desktop/mobile screenshots after actual data readiness. |
| 2026-10-26T03:11:57+05:00 | Removed 26 permitted local cache/artifact paths, listed below. Existing backend/.venv, frontend/node_modules, .env and IDE settings were preserved. Root .venv did not exist. |

These are recording points, not invented start/end times for individual commands. English translation covers current UI, API errors, newly rendered emails, tests and documentation. It does not rewrite stored descriptions, payloads or MIME. Deliberate IDN/EAI/non-English legacy fixtures remain. Historical documentation was translated and condensed with all 169 existing full development timestamps and all decision timestamps retained; the linked existing Git revision retains the original verbatim transcript. Added the separate 10-sentence reflection, explicitly AI-assisted.

Cleanup removed the empty root main.py, unused returned clear property, and duplicate LoadState branch. No additional service modules, tests, migration sources, locks, bootstrap SQL or load measurements were removed. Architecture, business rules, database schema, API routes/status codes and immutable-message boundaries are unchanged. Textual error messages are intentionally English now. No dependency or migration changes were necessary.

Screenshot capture now awaits a page-specific visible data locator and document fonts before checking overflow/capturing. A regression guards evaluation order; actual two-client E2E continues to use real business APIs and Mailpit. Added English date-format and legacy prepared-MIME byte-preservation regressions. The edge probe checks the English 429 response too.

### Actual commands and results

For these commands, `C` means `/tmp/maddevs-cleanup-compose`, a shell wrapper running from this repository with `COMPOSE_PROJECT_NAME=event-registration-relay-check-ui-cleanup-20261026`, `COMPOSE_ENV_FILES=.env.example`, `COMPOSE_PROFILES=test`, random published ports, and `docker compose -f compose.yaml -f compose.browser-test.yaml`. Only isolated `_test` databases are used by Pytest and explicit migration round trips.

```sh
C config --quiet
C build api test notifications notifications-test bootstrap-test frontend
C run --rm test sh -c 'ruff check . && ruff format --check . && mypy app tests/conftest.py tests/integration/test_relay_blocking.py tests/integration/test_live.py && alembic upgrade head && alembic downgrade base && alembic upgrade head && alembic check && pytest && alembic check'
C run --rm notifications-test sh -c 'ruff check . && ruff format --check . && mypy notifications_app && alembic upgrade head && alembic downgrade base && alembic upgrade head && alembic check && pytest && alembic check'
C run --rm bootstrap-test sh -c 'ruff check --config /app/pyproject.toml /bootstrap-tests /checks && ruff format --check --config /app/pyproject.toml /bootstrap-tests /checks && mypy --config-file /app/pyproject.toml /bootstrap-tests /checks && pytest -c /app/pyproject.toml /bootstrap-tests'
docker run --rm -v /Users/billcarter/Documents/MadDevs/frontend:/app -w /app node:24-alpine@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f sh -c 'npx prettier --write src tests e2e *.ts && npm run format:check && npm test && npm run build'
```

| Check | Actual result |
| --- | --- |
| Core Ruff / formatting / Mypy | PASS; 63 formatted files, 39 typed source files |
| Core Pytest on PostgreSQL | PASS; 199 tests, 28.54s |
| Notifications Ruff / formatting / Mypy | PASS; 36 formatted files, 19 typed source files |
| Notifications Pytest on PostgreSQL/Mailpit | PASS; 129 tests, 7.57s |
| Infrastructure Ruff / formatting / Mypy | PASS; 11 files; rerun after the English edge assertion |
| Infrastructure Pytest | PASS; 32 tests, 20.50s, including bootstrap repeat/isolation and load-probe regressions |
| Total Python | PASS; 360 tests, none skipped/disabled |
| Alembic, both services | PASS; explicit upgrade head / downgrade base / upgrade head / check, then post-Pytest check; existing populated migration regressions also passed |
| Frontend | PASS; Prettier, 23 Vitest tests in 3 files, TypeScript and Vite production build |
| Compose | PASS; config/build/start/health, repeated from a fresh local checkout with the patch applied |
| Actual-browser E2E | PASS; 12 tests, first run 53.7s, final fresh-checkout run 49.5s, macOS Chrome with Node 24, en-GB locale |
| HTTP/SMTP/edge CI scenarios | PASS; repeated against fresh-checkout services; see below |

The initial formatting-fix command inside the non-root Core image could not write COPY-owned source (permission denied). Corrected the source through a scoped repository bind mount using `C run --rm --no-deps --user 0 -v /Users/billcarter/Documents/MadDevs/backend:/app test sh -c 'ruff format . && ruff check .'`, rebuilt, then ran the full checks above successfully. No check was weakened. Docker supplies locked Linux dependencies instead of using incompatible local Python packages.

Fresh checkout verification used `git clone --local --no-hardlinks /Users/billcarter/Documents/MadDevs /tmp/maddevs-submission-check-20261026`, applied `git diff --binary`, copied the new ESSAY.md and public .env.example, and ran:

```sh
BROWSER_TEST_PROJECT=event-registration-relay-check-ui-cleanclone-20261026 scripts/browser-test.sh start
bash /tmp/maddevs-phase4-runtime-body.sh
python3 /tmp/maddevs-cleanclone-e2e.py
```

The runtime body reproduces the existing CI health/HTTP/SMTP/edge steps using the fresh checkout, Compose overlay and public example settings. It verifies health 200, Core create 201/register 202 while Notifications is stopped, durable retry after outage/relay kill, receiver commit with lost response, concurrent duplicate acceptance 202, document conflict 409, missing auth 401, SMTP pause/sender kill/lost DATA response, byte-identical frozen MIME matching Mailpit, 429/Retry-After and shared-NAT/XFF/connection limits. Core availability never depends on SMTP. The Playwright driver uses the installed Chrome executable and existing frontend test dependencies, against the freshly built real services; no fake successful API calls.

Other checks: `git diff --check`; protected-assets `git diff --exit-code`; shell `sh -n` for browser/load/bootstrap scripts; workflow Ruby YAML parsing; Markdown relative links/fences; essay sentence count 10; preserved historical timestamps; unchanged PDF hash; actual `git ls-remote origin HEAD`. All passed. Remote GitHub Actions and its Linux Chromium install were not executed; local workflow-equivalent checks and real macOS Chrome were executed. No new load measurements or production throughput claims were made.

Logs remain outside Git under `/tmp/maddevs-cleanup-{build,core-full,notify-full,infra-full,infra-static-final,frontend-final}.log` and `/tmp/maddevs-cleanclone-{start,runtime,e2e}.log`; screenshots: `/tmp/maddevs-ui-visual-final-en/`. Logs/screenshots are local review artifacts, not persistent CI artifacts.

### Removed local caches/artifacts

- `.mypy_cache`
- `.pytest_cache`
- `.ruff_cache`
- `backend/.mypy_cache`
- `backend/.pytest_cache`
- `backend/.ruff_cache`
- `backend/app/__pycache__`
- `backend/app/api/__pycache__`
- `backend/app/db/__pycache__`
- `backend/app/notifications/__pycache__`
- `backend/app/services/__pycache__`
- `backend/migrations/__pycache__`
- `backend/migrations/versions/__pycache__`
- `backend/tests/__pycache__`
- `backend/tests/integration/__pycache__`
- `backend/tests/unit/__pycache__`
- `frontend/dist`
- `frontend/test-results`
- `notifications/.mypy_cache`
- `notifications/.pytest_cache`
- `notifications/.ruff_cache`
- `notifications/migrations/__pycache__`
- `notifications/migrations/versions/__pycache__`
- `notifications/notifications_app/__pycache__`
- `notifications/tests/__pycache__`
- `notifications/tests/unit/__pycache__`

### Final cleanup and changed files: 2026-10-26T03:13:22+05:00

Both dedicated test projects were stopped with their wrappers using `down --remove-orphans`, without `--volumes`; their subsequent `ps --all --quiet` was empty. Read-only Docker inventory confirmed the existing main and October 23 preview services remained running. Cache scan excluding dependencies found no remaining permitted caches; backend/.venv, frontend/node_modules, .env and .idea remain. Only tracked deletion: main.py. Protected tracked assets and diff whitespace checks passed. The first temporary Markdown-link checker had an over-greedy regex and incorrectly combined two links; correcting that checker made all links pass without changing product files. All 169 original full ISO development timestamps and 22 decision timestamps were verified again.

Tracked changes plus the new untracked essay:

- `ARCHITECTURE.md`
- `DECISIONS.md`
- `DEVELOPMENT_LOG.md`
- `README.md`
- `REQUIREMENTS.md`
- `backend/app/api/dependencies.py`
- `backend/app/api/errors.py`
- `backend/app/api/schemas.py`
- `backend/app/main.py`
- `backend/app/services/checkins.py`
- `backend/app/services/common.py`
- `backend/app/services/events.py`
- `backend/app/services/registrations.py`
- `backend/tests/integration/business_support.py`
- `backend/tests/integration/test_api.py`
- `backend/tests/integration/test_business.py`
- `backend/tests/integration/test_schema.py`
- `backend/tests/integration/test_waitlist.py`
- `docs/EMAIL_CANONICALIZATION.md`
- `docs/LOAD_TESTING.md`
- `docs/NOTIFICATIONS_INFRASTRUCTURE.md`
- `docs/NOTIFICATION_PROTOCOL.md`
- `docs/OPERATIONS.md`
- `docs/SMTP_DELIVERY.md`
- `docs/WORKER_EVOLUTION.md`
- `frontend/e2e/events.spec.ts`
- `frontend/index.html`
- `frontend/nginx.conf`
- `frontend/playwright.config.ts`
- `frontend/src/App.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/components/Pagination.tsx`
- `frontend/src/components/common.tsx`
- `frontend/src/dates.ts`
- `frontend/src/hooks/data.ts`
- `frontend/src/pages/Events.tsx`
- `frontend/src/pages/Organizer.tsx`
- `frontend/src/pages/Participation.tsx`
- `frontend/tests/availability.test.ts`
- `frontend/tests/dates.test.ts`
- `infrastructure/checks/limit_probe.py`
- `infrastructure/tests/test_bootstrap.py`
- `main.py`
- `notifications/notifications_app/mime.py`
- `notifications/tests/integration/test_inbox.py`
- `notifications/tests/unit/test_mime.py`
- `ESSAY.md`

Locally ready for reviewer acceptance; no claim of a remote CI run, public availability of the current working-copy changes, production capacity or exactly-once SMTP. Commit/push/deployment were not performed. No remaining local test failure was observed. Cross-browser/production acceptance, external SMTP/TLS, monitoring, backups/restore drills and longer target-hardware load tests remain outside this task.
