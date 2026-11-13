---
name: yuno-release-evidence
description: Audit Yuno Ball PR, staging, ingestion, or public beta readiness and prepare an evidence-based release recommendation.
---

# Yuno release evidence

Read `docs/DEPLOYMENT_RUNBOOK.md`; identify exact commit, environment, and proposed action. Check status, relevant tests, and actual CI runs separately. A configured workflow, fixture, push, or localhost readiness response establishes only its own layer.

For private staging, inspect managed PostgreSQL/Redis probes, bounded migration/reconciliation, backup plus separate restore, ingestion disablement or scheduling with replay proof, freshness states, and rollback rehearsal. Verify the current readiness contract: PostgreSQL healthy/Redis down is 200 `degraded_ready`; PostgreSQL down is 503. Mark every gate observed pass, observed fail, or unverified with dated evidence. Keep public traffic and ingestion changes outside staging verification unless authorized.

Give a GO/NO-GO tied to unresolved gates. Billable provisioning requires exact candidate, cloud account, region, spending ceiling, and authorization. A review does not authorize merge or deploy. Update the runbook only when the process changes.
