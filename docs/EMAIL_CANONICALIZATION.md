# Canonical email across Core, Notifications and existing data

The agreed policy uses the locked email-validator dependency, `ascii_email`, `check_deliverability=False`, `test_environment=True` and `allow_smtputf8=False`. There are no DNS/API lookups; local `.test` domains are allowed. Strip outer whitespace, retain the accepted case-insensitive local-part policy with lower(), validate and return lowercase ASCII. Do not casefold: it could turn ß into ss. Preserve dots and plus suffixes; reject Unicode local-parts, display names, multiple recipients and CR/LF/U+0000.

| Input | Canonical identity |
| --- | --- |
| `USER@faß.de` | `user@xn--fa-hia.de` |
| `user@xn--fa-hia.de` | `user@xn--fa-hia.de` |
| `user@fass.de` | `user@fass.de`, a different domain |
| `Some.One+Tag@EXAMPLE.test` | `some.one+tag@example.test` |

Deliberate Unicode fixtures remain in tests, including non-Latin IDN and rejected EAI local-parts. Translating the application must not remove that coverage.

The original defect had two causes: Core validated but ignored the returned ASCII address, while Notifications used Python's IDNA2003 codec. Each independent service now has a small canonical_email helper, with cross-service reference tests instead of a shared business runtime package. [email-validator normalization](https://github.com/JoshData/python-email-validator#normalization).

## New registrations and messages

Core normalizes before existing-registration lookup and at ORM assignment. READ COMMITTED, event FOR UPDATE and UNIQUE(event_id,email) remain. Unicode/Punycode identity is the same even across two API processes; another event may use the same address. Repeating email changes no participation, secret, ticket or outbox.

New registrations/payload recipients contain ASCII. Notifications does not rewrite its accepted DTO/JSON: changing legacyv1 content could turn an identical lost-ACK retry into409. Rendering and every SMTP retry compare canonical recipient identity. New To/RCPT TO contain one ASCII address and do not require SMTPUTF8.

## Existing payload and MIME

Migration0004 changes only registrations.email, not outbox/prepared_at or Notifications payload/MIME/status. Normal business operations can refresh unprepared Core context as before; frozen payload remains immutable.

Every send loads existing MIME and compares its canonical To with the canonical payload recipient. A legacy `user@faß.de` JSON can remain unchanged: new MIME renders the correct ASCII To; already correct frozen MIME repeats unchanged. ASCII casing is accepted while retaining original bytes/headers, including Message-ID casing.

Frozen `To: user@fass.de` with payload `user@faß.de` is unsafe because fass.de and xn--fa-hia.de differ. Mark failed with a safe category, invoke no SMTP and continue to the next job. Preserve payload/MIME/attempts/schedule rather than silently repairing evidence. Non-ASCII frozen From/To are also rejected instead of enabling SMTPUTF8 or rewriting the envelope. Manual retry validates and rejects unsafe data; repeated HTTP cannot reactivate it. A message already sent cannot be retracted by this fix.

## Read-only audit and migration0004

The original preflight found0 registrations/0 collisions in a read-only transaction and did not upgrade the main installation. That historical observation is not a statement about its current contents.

```sh
docker compose build api notifications
docker compose run --rm --no-deps api python -m app.email_audit
```

The CLI performs READ ONLY SELECT and outputs counts, invalid UUIDs and collision UUID groups, never addresses/tokens. Exit1 requires manual resolution. This is only a snapshot; migration repeats its audit under locks.

0004 takes ACCESS EXCLUSIVE on events then registrations, audits every registration including cancelled, and detects invalid legacy data or `(event_id,canonical_email)` collisions **before the first UPDATE**. Failure rolls back the whole revision and reports IDs only: it never merges, deletes or picks a winner. The revision freezes its normalization policy rather than importing a future changing app helper.

On success it updates email only and strengthens the ASCII CHECK (`octet_length=char_length` in UTF8), keeping IDs, status, queue, tokens, tickets, versions and outbox. Core remains3tables/24columns. A CHECK cannot itself perform IDNA normalization or replace the validator.

Downgrade to0003 removes only the ASCII CHECK component; it cannot reconstruct prior Unicode/casing from canonical strings. Exact restoration needs a backup, not guessed spelling. Old revision files are unchanged and Alembic hides bind parameters.

After a backup and successful read-only audit, an operator can stop old writers, apply migrations and start the new code:

```sh
docker compose stop api worker
docker compose run --rm migrate
docker compose up --no-build -d --wait api worker notifications notifications-sender frontend
```

These are operator instructions, not actions on the main database during readiness verification. Do not delete a volume or automatically merge participants to bypass an audit failure.

## Evidence

Tests cover ASCII/IDN/ß/Punycode, dots/suffixes, no SMTPUTF8, repeated/concurrent registration, audit atomicity, cancelled collisions, populated upgrade/downgrade/check and24columns. MIME regressions retain legacy JSON/correct frozen bytes, reject fass-versus-IDNA mismatch without SMTP, and allow the following valid job. Real SMTP captures canonical RCPT TO and the full Core -> inbox -> MIME -> Mailpit path. Both freeze boundaries and SMTP ambiguity remain as documented in [SMTP_DELIVERY.md](SMTP_DELIVERY.md).
