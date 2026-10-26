# Reflection

*AI-assisted reflection based on the recorded development history*

The project was developed as a small event registration service with an AI coding assistant in Codex.
The main challenge was protecting the last available place when requests arrived together.
PostgreSQL transactions and an event row lock keep registration and FIFO promotion consistent.
The transactional outbox separates business commits from unreliable network delivery.
A second service owns notification acceptance, MIME preparation and SMTP submission.
Immutable payloads and stored MIME make retries explainable, although SMTP acceptance can still be followed by a duplicate.
Tests with real PostgreSQL and Mailpit exposed failures that simpler substitutes would have missed.
Browser tests also revealed how loading races and device clocks can mislead an interface.
Generated changes were inspected and tested rather than treated as evidence of correctness.
The next priorities are production monitoring, restore drills and longer load tests on the target environment.
