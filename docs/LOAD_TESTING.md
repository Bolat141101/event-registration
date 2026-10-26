# Load verification

Run from a **fresh isolated project**:

```sh
BROWSER_TEST_PROJECT=event-registration-relay-check-ui-UNIQUE LOAD_LABEL=after scripts/measure-load.sh
# Additional connection-count check:
BROWSER_TEST_PROJECT=event-registration-relay-check-ui-OTHER LOAD_LABEL=multi API_WORKERS=2 LOAD_VISITORS=1000 scripts/measure-load.sh
```

The script rejects the main project name/existing DB container, uses .env.example and tmpfs, and removes only its own containers/network through a trap, without --volumes. Docker Compose, host Python3 and available localhost ports are needed. Probe source is in infrastructure/checks; output is JSON. Stored raw results and SQL plans are retained, not deleted by cleanup.

## Method and what is measured

A burst of200 concurrent POSTs with distinct emails targets one capacity10 event. Record p50/p95/p99, status counts, completed burst throughput and sampled PostgreSQL lock waiters every50ms. Then reschedule that accepted population, check duplicates/capacity and outbox, and establish100 SSE clients by default. After initial snapshots/warm-up, hold streams for an8s measurement window and observe pg_stat_database xact_commit/deadlocks. The commit delta includes observer/readiness activity; it is not an exact SELECT count.

Relay/sender stop only for the DB phase. They restart afterward and the delivery probe checks real Core forwarding/Mailpit messages; drain time starts **before worker startup**, not after health-wait. A separate fresh HTTP pool is used for long-lived SSE after the POST phase. Errors do not trigger hidden client retries.

Visitors, requests/second and open connections differ:1000 SSE streams are not1000 registrations/second or1000 Chrome rendering sessions. A burst is not sustained arrival-rate traffic. API_WORKERS2/1000streams is an extra correctness/resource check, not a controlled comparison of process counts on identical connection populations.

EXPLAIN ANALYZE/BUFFERS/JSON covers bounded page IDs, page aggregates, outbox registration lookup and all three actual bulk reschedule statements. Fixtures10000events and explained mutations use isolated transactions/savepoints/rollback. Seq Scan on a small table is not a failure; plans depend on cardinality/statistics. Each probe confirmed24Core columns.

Controlled before: git archive e64a564 into a temporary directory, copying only the current probe/script, with separate baseline image tags. Two runs per version used fresh DBs, sequentially, without concurrent E2E/build activity during measurement. The earlier exploratory run under other Docker activity is not the controlled baseline.

## Historical measured results:2026-10-24

[Original JSON and plans](load-results/2026-10-24.json) are preserved. These runs used the **older, weaker acceptance criteria**: recorded values do show200×202 and expected counts, but exit0 alone did not prove all registration/outbox/SSE invariants. They are descriptive historical measurements, not standalone automated acceptance of the corrected probe.

| Run | API processes / SSE | Registration p50/p95/p99,ms | Completed burst req/s | Max lock waiters | Reschedule,ms | DB commits/8s SSE | Drain400emails,s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Before A | 1 /100 | 663.87/991.74/1021.67 | 188.11 | 14 | 405.54 | 791 | 6.495 |
| Before B | 1 /100 | 773.14/1167.20/1211.54 | 155.87 | 14 | 361.95 | 824 | 6.538 |
| After A | 1 /100 | 1162.17/1838.41/1900.58 | 102.01 | 14 | 65.56 | 26 | 48.606 |
| After B | 1 /100 | 693.63/1036.31/1069.43 | 180.36 | 14 | 32.99 | 12 | 8.443 |
| After, two processes | 2 /1000 | 793.18/1224.39/1266.01 | 153.01 | 29 | 77.27 | 34 | 9.129 |

All recorded runs had10confirmed/190waiting,0duplicate emails/queue numbers and0new deadlocks;400forwarded/400Mailpit copies/failed0. The other200outbox rows were future reminders. All requested streams remained active at observation end with no recorded transport error.

Shared event/process snapshots reduced observed SQL commit activity; rescheduling fell from362–406ms to33–66ms in the one-process samples. **Faster registration was not established**: after p95 was1036–1838ms versus992–1167ms before. The queue also is not claimed faster: after-A took48.606s, with maximum ready-job age93.297s. Its saved log tail had no ERROR/WARNING, but the cause is unresolved and requires profiling/longer repeated target-hardware tests. The singleton adds DB calls, but these measurements do not prove it explains that whole outlier. A60s overdue alert is intended to reveal such lag.

On10000events, bounded page plans used ix_events_start / Index Only Scan instead of Sort+Seq Scan and limited to21IDs. Full plans retain buffers/timing, including small-table sequential scans. A separate populated migration regression hashes all three tables across0005 downgrade0004/upgradehead and checks indexes,24columns and alembic check; rows/tickets/check-in/prepared payload remain unchanged.

Preliminary failed runs reused POST keep-alive sockets and saw RemoteProtocolError before the first snapshot on both versions. A separate fresh SSE pool fixed that probe setup issue. No reconnect retries or relaxed all-clients requirement were added; failed preliminary runs were not silently used as successful results.

## Corrected strict criteria and actual control run

The audit found that the old conditions allowed200×500 with0registrations and partial success, and did not validate SSE state/deadlocks/outbox. Corrected criteria require:

- All200 HTTP202, exactly10confirmed/190waiting,600pending jobs **for that event**, with worker/sender stopped for the DB phase.
- No duplicate emails/queue positions or new deadlocks.
- All requested/established streams still active, no transport/parser/task errors, at least two valid snapshots per client and latest message age<=3s.
- SSE fields/types/id/counts/schedule agree with the acknowledged HTTP reschedule; aware server_time is required. Z and+00:00 denote the same instant.
- Invalid JSON, EOF, child-task failure or incomplete results produce a nonzero exit. Engine/client/task cleanup remains explicit.

This is a fixed correctness scenario, not a generic benchmark allowing an unspecified error percentage. Test barriers, not sleep, synchronize regressions; timed8s measurement/poll periods are part of the benchmark itself.

At2026-10-24T19:52:13+05:00, the corrected probe ran with2API/1000SSE and exited0:200×202,10/190,600pending,1000established/active,9000valid messages,stale0/errors0/deadlocks0/duplicates0,29commits/8s. Registration p951770.01ms;400forwarded/Mailpit400,failed0,drain10.308s,maxdue23.458s. [Strict JSON/EXPLAIN](load-results/2026-10-24-audit.json). Its fresh project was cleaned automatically. This is not another controlled before/after comparison.

Eight seconds is not a soak test. Long overload, many distinct active events, distributed sources/NAT patterns, production SMTP and target hardware remain to be measured against agreed latency/error/backlog budgets. Hot-event writes remain serialized by PostgreSQL; adding API processes does not remove that business lock.
