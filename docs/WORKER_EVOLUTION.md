# Current workers and a future concurrency boundary

Core implements transactional outbox creation/refresh, event-locked JSONv1 preparation and an async HTTP relay with persisted attempts/backoff. Notifications accepts idempotently before202 and its separate sender stores MIME before asynchronous SMTP. Forwarded is not sent. [Protocol](NOTIFICATION_PROTOCOL.md).

## Current boundary

- Registration/cancellation/rescheduling mutate business state and add outbox in one AsyncSession/transaction. They do not start a worker or call SMTP.
- Core notification functions own dedup/context/preparation; Notifications independently owns MIME and SMTP. No generic queue interface or cross-service ORM package is required.
- There is one active relay and one active sender. Whole iterations/manual retry use a PostgreSQL session advisory mutex with ownership watchdog; network runs outside SQL transactions. prepared_at freezes payload and nullable MIME marks the independent second freeze boundary, not task ownership.
- FIFO promotion stays inside the event-locked business transaction regardless of SMTP availability.
- Accidental second processes do not increase throughput: mutex serializes them. Do not treat `--scale worker=2` or `--scale notifications-sender=2` as horizontal job processing. Stop old senders before maintenance/failover, since ownership cannot fence an SMTP action already accepted remotely.

Each concurrent asyncio task would need its own AsyncSession. Async I/O alone does not create distributed claiming. The current loop/health/diagnostics and explicit retry are described in [OPERATIONS.md](OPERATIONS.md).

## Future plan, not implemented

1. After actual throughput measurements justify it, add a new Core outbox migration with lease_token/locked_until and an index. Claim ready work in a short FOR UPDATE SKIP LOCKED transaction, then commit ownership before HTTP. Preserve event -> outbox lock ordering and freeze checks; do not hold an outbox row lock while waiting for an event.
2. Independently add claiming/leases to Notifications for multiple senders. Expiry allows recovery; completion must compare-and-set the current owner token. Core does not manage Notifications leases.
3. SKIP LOCKED is for independent jobs, **not participant FIFO**. Registration/cancel/promotion remain one Core transaction under the event lock.
4. An expired lease does not stop an old process from completing an external HTTP/SMTP action. Preserve idempotent HTTP acceptance, immutable IDs/payload/MIME and remote duplicate handling. Leases do not make SMTP exactly-once.
5. Replace the global mutex only with proven per-job ownership, expiry/renewal/stale-owner tests, crash-before/after-ACK tests and preserved within-event ordering. Keep a separate AsyncSession per task.

A future Celery relay still needs transactional outbox-to-broker publication and idempotent consumers. Redis/Celery/Kafka and distributed leases are deliberately absent now. The business allocation/FIFO algorithms need not be rewritten when the job selection/completion implementation changes.
