# Diagnosis and recovery

Core readiness checks its own DB/schema. Notifications and SMTP availability do not determine Core HTTP readiness. Use these commands on an explicitly selected environment; verification/failure injection must use the isolated test project from README.

## Safe observation

```sh
docker compose ps
docker compose exec -T worker python -m app.worker_health
docker compose exec -T notifications-sender python -m notifications_app.worker_health
docker compose exec -T worker python -m app.operations --check
docker compose exec -T notifications-sender python -m notifications_app.operations --check
```

Worker health reads the real loop heartbeat, PID, database-ready flag and monotonic age<180s. The bound allows limited network attempts/polling. It is not an SMTP success receipt. Repeated DB/iteration failures make health unhealthy; Compose does not restart a process merely because health is unhealthy, so production needs alerting/operator action. Exit/restart policy is separate.

Queue summaries expose status counts, at most20 failed UUIDs and oldest_due_seconds. `--check` exits1 for failed>0 or ready work overdue>60s. Future reminders are excluded. This is age from available_at, not total age since initial creation: backoff changes available_at. No recipient, token, payload, MIME or raw error body is printed. The delivery probe measures separate end-to-end drain time.

## Explicit failed retry

Resolve the cause and inspect safe last_error in its owning DB first. Do not rewrite payload/MIME or issue another ID.

```sh
docker compose stop worker
docker compose run --rm --no-deps worker python -m app.notifications.retry UUID --acknowledge-duplicate-risk
docker compose up -d worker

docker compose stop notifications-sender
docker compose run --rm --no-deps notifications-sender python -m notifications_app.retry UUID --acknowledge-duplicate-risk
docker compose up -d notifications-sender
```

Only failed can be reset to pending with attempts0/deadline-now; identity and freeze evidence remain. Pending/sent/forwarded are not reset. Notifications validates contract/MIME/envelope before requeue; Core prepare rechecks contract/state/time. An occupied mutex prevents the operation. Unsafe MIME remains failed, never repaired by regeneration. A retry can duplicate an externally accepted action with a lost result.

## Ownership and failover limits

Each service's whole iteration acquires session advisory key794632801 in its independent PostgreSQL database. Another process cannot prepare or send concurrently. One reserved AUTOCOMMIT connection retains ownership across HTTP/SMTP; SQL business transactions are closed. Cleanup unlocks before pooling or invalidates a damaged connection. A0.5s watchdog cancels the attempt if the ownership connection is lost; SIGKILL releases ownership when PostgreSQL closes the session.

This is singleton enforcement, not distributed leases or external SMTP fencing. A DB session failure/failover can overlap DATA already accepted before detection. Stable MIME/Message-ID cannot guarantee exactly-once SMTP. Mailpit suppression is limited to its current configured store. Stop senders before planned failover/rolling maintenance.

## SSE, lists and admission

One event/process producer reads a current snapshot each second and broadcasts through queue1 per subscriber. The last disconnect cancels/deletes the producer; shutdown closes tasks before the engine. A SQL-failed producer retires its registry entry before old HTTP cleanup, so reconnect creates a fresh producer; late old cleanup cannot delete the replacement. No SQL transaction stays open while waiting for subscribers.

SSE_MAX_CONNECTIONS2000 bounds each API process; SSE_LIMIT2000 bounds the current Nginx. REGISTER_RATE30r/s with burst1000 uses actual remote_addr. A large burst accommodates shared NAT, and SSE has no small per-IP cap. Incoming X-Forwarded-For/X-Real-IP are overwritten; Core is not publicly published.429 includes safe JSON and Retry-After; health remains independent. A future external ingress needs explicit trusted-proxy ranges and IP tests. Separate ingress instances do not share rate zones; this is not full distributed bot protection.

API_WORKERS defaults1. More processes have separate pools/producers; account for all PostgreSQL connections, including one reserved ownership connection per active relay/sender. Business locking/UNIQUE/FIFO remain in PostgreSQL.

`GET /api/events?limit=20&offset=0` returns items,next_offset,server_time; limit1..100, offset0..1000000. IDs are bounded before aggregates. Concurrent rescheduling can shift offset pages; refresh the list rather than assuming a historical snapshot. Large offsets may later justify cursors.

UI uses server_time plus performance.now. Before synchronization or after SSE/network loss, availability is neutral and time-dependent actions are disabled. List time comes from its page response; detail time comes from SSE. Private state refreshes on snapshot changes/reconnect and10s fallback for private-only changes; final server/generation checks remain authoritative. No private GET is issued every second merely for a heartbeat.

Server/DB clocks must be synchronized. Device-clock protection does not replace server NTP. New emails/UI use English; user data and already prepared payload/MIME remain unchanged.

## Production and measurement

See [LOAD_TESTING.md](LOAD_TESTING.md), including a historically slow queue run and the corrected strict probe. Production still needs TLS, actual SMTP/TLS credentials and domain reputation/SPF/DKIM/DMARC, trusted ingress, backup/restore drills, metrics/alerts, clock synchronization and target-hardware budgets. Local Mailpit and short load runs are not an SLA. External SMTP/CD are not deployed by this project task.
