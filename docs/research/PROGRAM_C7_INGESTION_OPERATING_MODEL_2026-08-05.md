# Program C7 ingestion operating model

## Incident resolved

Batch 2 of the 2025-26 C7 backfill reached the NBA endpoints successfully but
failed at publication because player ID `1642955` was missing from `players`.
The ID is Kadary Richmond. NBA CommonPlayerInfo identifies him as a 2025-26
NBA player with NBA and G League flags; the NBA G League profile lists him with
Capital City Go-Go. His February 11, 2026 Wizards appearance was a historical
call-up/short-term-contract case, not an invalid box-score row.

The failure exposed a sequencing defect: current-player/static discovery is not
a complete historical player dimension. It can miss G League, two-way, Exhibit
10, 10-day, or otherwise short-lived NBA call-ups after they leave the current
roster. The C7 fact foreign key correctly prevented an orphan fact.

## Required operating modes

### Daily ingestion

Daily ingestion remains independent of the C7 coverage gate and should use the
daily advisory lock. Its order is:

1. Discover active players and reconcile current rosters.
2. Update schedule and team-game results.
3. Resolve any player IDs observed in the day’s box scores through
   CommonPlayerInfo before publishing player facts.
4. Publish current facts and legacy compatibility projections according to
   their own contracts.
5. Calculate downstream snapshots only after the required source tasks pass.

An unresolved identity is a quarantined retry item, not a fabricated player
row and not permission to bypass the foreign key.

### Historical or mass backfill

Historical work uses a separate C7 backfill lock and never holds the daily lock.
It selects an exact manifest, fetches bounded batches of at most 25 games,
resolves missing player parents before publication, and records the manifest,
identity-resolution result, C5 reconciliation, and database-only replay proof.
Network calls occur outside database transactions. A provider failure or
unresolved identity fails the batch before fact publication; the batch can be
retried without deleting or rewriting legacy tables.

### Replay and recovery

Database-only replay is the default idempotency proof and does not consume
proxy requests. Provider re-fetch is explicit via `--network-replay`. A failed
batch remains pending in the coverage inventory; successful earlier batches
are not repeated.

## Current implementation boundary

The shared identity service is now used by the C7 runner and the reusable
`scripts/resolve_player_identity.py` repair command. The next hardening slice
is to add a durable unresolved-identity/quarantine ledger for daily and mass
jobs so one unusual call-up does not stop unrelated games, while retaining a
clear completeness gate for Program D.
