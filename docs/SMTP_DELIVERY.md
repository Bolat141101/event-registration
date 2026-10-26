# Asynchronous SMTP and immutable MIME

SMTP is implemented in the existing Notifications service with aiosmtplib and local Mailpit. Core owns participation and readiness; Notifications owns MIME and actual SMTP submission. UI/SSE are also implemented now; historical stages that excluded them are recorded in the decision log.

## Two freeze boundaries

1. Core prepares a complete logical JSON command under the event lock, commits payload/prepared_at and then uses HTTP outside SQL. A lost response repeats that same command.
2. Notifications accepts durably, then its separate sender renders MIME **once** and saves bytes before SMTP. Recipient, body, From/To, Date and Message-ID are frozen. Later attempts load and validate the same bytes, not a new rendering.

Message-ID derives from the command UUID and sender domain. Date is the first preparation time. New templates are English; stored user descriptions and existing payload/MIME are not translated. A regression verifies that legacy non-English MIME remains byte-identical after the template change.

Core forwarded means accepted by Notifications. Notifications sent means accepted by SMTP, not necessarily delivered to a person's inbox. No network I/O holds an open SQL transaction.

## Sender loop and states

One active sequential sender selects due pending jobs by persisted schedule. PostgreSQL session advisory ownership spans a whole iteration; a second process does not prepare/send that job concurrently. Ownership uses an AUTOCOMMIT connection/watchdog, not a long row transaction or per-job lease. [Operational limits](OPERATIONS.md).

- HTTP acceptance inserts pending, mime=NULL, attempts0 in the independent Notifications DB.
- Prepare validates the stored contract. If MIME is absent, render/save it and the persisted attempt/backoff before network.
- SMTP uses async I/O, phase/total timeouts and no external SMTPUTF8 requirement. Canonical payload recipient must equal the frozen ASCII envelope recipient on **every attempt**.
- SMTP acceptance commits sent. Retryable connection/timeout/transient SMTP errors retain immutable data and schedule exponential backoff. Permanent/invalid contracts or MIME remain failed with a safe category.
- Attempts are bounded and persisted, so restart does not reset the budget. No application token, recipient address, body or raw SMTP exception is logged.

Defaults: SENDER_TIMEOUT5s, SENDER_POLL_INTERVAL5s, SENDER_MAX_ATTEMPTS8, SENDER_BACKOFF_BASE1s, SENDER_BACKOFF_CAP60s. Test overlays use shorter polling/backoff only within their explicit isolated environment. Backoff is `min(cap,base*2^(attempts-1))`; ready work survives restart in PostgreSQL.

## Cancellation, generations and versions

Before **Core preparation**, cancellation/stale participation can suppress work and rescheduling can update unprepared context/deadlines. Once Core freezes and transfers a command, Notifications cannot consult Core or retract it. It sends a historical snapshot, even if cancellation occurs before MIME preparation. A later business change does not overwrite an already accepted job.

Before MIME preparation, a stored command is still logically immutable; only rendering is pending. After MIME preparation, bytes/envelope/Date/Message-ID also remain unchanged. Rescheduled messages describe their own old/new dates; they do not change earlier jobs. Repeated older HTTP acceptance never resets cancelled/failed/sent state, attempts or MIME. The email text states that current participation and ticket validity belong to Core.

The reminder has one logical identity across cancellation/rejoin/rescheduling. Core's pre-freeze time/version rules decide whether it is due, suppressed or updated. A frozen retry is not replaced with a new reminder, even after the event starts.

## Damaged MIME must not block later jobs

load_prepared validates headers lazily as well as the byte parser. Header defects, ValueError/TypeError/IndexError/AttributeError/HeaderParseError become a safe ValueError. From/To must each be one safe ASCII mailbox, identity and Date must be valid, and the canonical recipient must match the payload.

A damaged pending job becomes failed, preserving payload and original MIME. SMTP is not invoked for it; the sender continues with the next due job. Tests include `From: "`, `From: a@[`, damaged To, unsafe legacy IDNA recipients and a following successful job. No global except Exception hides arbitrary sender defects and no frozen message is repaired/regenerated silently.

## Ambiguous acceptance and duplicates

A sender may crash after the server accepts DATA but before local sent commit, or lose the SMTP response. Recovery cannot know whether the external system accepted the message. It repeats the same bytes/Message-ID and can duplicate mail on arbitrary SMTP servers. Session ownership/leases cannot retract an already accepted DATA transaction or provide SMTP fencing after DB failover.

Mailpit is an **emulator**. MP_IGNORE_DUPLICATE_IDS suppresses duplicates only while the ID remains in its current store and the option is enabled; deletion/reset/eviction removes that evidence. MP_MAX_MESSAGES0 avoids local test eviction. This is not general exactly-once SMTP or production inbox delivery.

## Diagnosis and safe manual retry

After resolving a cause, stop the sender and use:

```sh
docker compose stop notifications-sender
docker compose run --rm --no-deps notifications-sender python -m notifications_app.retry UUID --acknowledge-duplicate-risk
docker compose up -d notifications-sender
```

The CLI accepts failed only, validates contract/frozen MIME, retains ID/payload/MIME and resets attempts/deadline for an explicit attempt. A pending/sent job is not reset. Unsafe legacy MIME remains failed and cannot be retried by changing its recipient. Do not manually rewrite evidence in SQL. Duplicate risk is intentional operator acknowledgement, not a guarantee that the prior send failed.

Queue and heartbeat commands are in [OPERATIONS.md](OPERATIONS.md). SMTP failure does not make Core readiness fail. Failed jobs and overdue age require monitoring/operator action; Compose does not restart a process merely because its healthcheck is unhealthy.

## Actual verification coverage

Unit/integration tests use real PostgreSQL and Mailpit for persisted state, SMTP RCPT/encoding, retry, timeout, restart, accepted DATA with lost response, frozen byte identity, cancellation/rescheduling before/after freeze and a damaged job followed by a valid one. Infrastructure tests cover Core -> HTTP -> Notifications -> SMTP -> Mailpit and two DB roles.

The CI SMTP probe pauses Mailpit, kills/restarts the sender, and uses a proxy that forwards real DATA then loses the response. Recovery repeats the frozen message and checks one copy within the current Mailpit store. All failure injection is guarded to isolated test projects. Executed commands/results are in DEVELOPMENT_LOG; remote CI is not asserted without an actual run.
