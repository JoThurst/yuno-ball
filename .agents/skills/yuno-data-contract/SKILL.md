---
name: yuno-data-contract
description: Design or change Yuno Ball PostgreSQL tables, Alembic migrations, canonical grains, or reconciliation. Use yuno-cache-performance for Redis behavior.
---

# Yuno data contract

Read `docs/DATA_DICTIONARY.md`, relevant models/migrations, and `docs/YUNOBALL_ARCHITECTURE.md`. `docs/DATABASE_PROFILE.md` is a dated snapshot; inspect a target database only when authorized.

Define row grain and uniqueness before a migration. Specify source lineage, as-of/availability time, nullable meaning, season type, and replay behavior. Use explicit transactions for related durable rows. Plan additive migration and rollback/reconciliation; preserve historical data. Strictly allowlist dynamic SQL identifiers.

For a migration, identify readers and writers that must coexist during rollout. Verify duplicate handling, nulls, pairs, and reruns as relevant. Update `docs/DATA_DICTIONARY.md` for implemented grain/schema changes; update the architecture document if ownership or a boundary changes.
