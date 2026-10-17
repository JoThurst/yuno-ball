# Program Progress Session — 2026-09-13

Status: completed reviewable slices; no production writes; one bounded live odds probe; full-suite readiness cleanup

## Completed in this session

### Odds pilot

- Added a fail-closed SportsGameOdds client and provider-shape normalizer.
- Authentication is header-only through `SPORTSGAMEODDS_API_KEY`; the key is
  never placed in a URL or repository file.
- Default probe mode is plan-only and reports zero network requests.
- Explicit live mode is capped at one request and 25 events, with no Yuno Ball
  database writer or scheduler path.
- Game-level moneyline, spread, and total shapes are normalized; player props
  and non-game periods are excluded.
- Provider team IDs remain unresolved strings until identity mapping and pair
  completeness are reviewed.
- Explicitly authorized live probe completed with exactly one read-only request:
  HTTP 200, one event received and normalized, both provider teams and start
  time present, ten game-market rows, 48 bookmaker rows, and 48 provider
  timestamps. A next cursor was present and intentionally not followed.

### Daily launch hardening

- Replaced the navbar's implicit live `fetch_todays_games()` call with a
  persisted schedule read. Rendering `/design/status` no longer causes an
  external source fetch and measured about 90 ms after restart.
- Added an accessible page-loader label and a 2.5-second client fallback so a
  missing optional JavaScript bundle cannot leave a user on an endless spinner.
- Updated the visual status map to seven gates: 57% complete, 29% active, and
  14% waiting on season evidence.

### Program G evidence

- Reran both chronological held-out directions across 1,075 source/held-out
  games per season.
- Both runs completed with `writes_performed=false`.
- Results remain research evidence only; direction-dependent calibration does
  not clear the public prediction gate.

### Checklist completion pass

- Added the Daily accessibility baseline: keyboard skip link, focusable main
  landmark, labeled loader, dropdown/menu ARIA state, and historical tipoff
  fallback that does not invent midnight from date-only schedules.
- Completed the frozen G feature-family comparison over 1,075 eligible games
  per season. The strength/form/schedule and matchup variants pass coverage and
  subgroup eligibility in both approved seasons; the matchup log-loss range is
  0.0109. No model or route publication occurred.
- Reran H1 source-timing and role-band preparation audits. Historical timing is
  still not production-safe; the role rehearsal remains explicitly
  `production_ready=false`.
- Added fixture-only SportsGameOdds pair review. It canonicalizes spread-side
  lines by absolute value, reports complete/incomplete/duplicate groups, and
  leaves provider identity unresolved. No second live request was made.
- Resolved legacy route/ORM/empty-state failures and made Alembic ignore the
  intentionally retained but unmodeled legacy `users` table during drift
  checks.

## Verification

- Focused provider, status, Daily launch, market adapter, and navbar tests:
  15 passed after the loader contract test was corrected.
- `python -m compileall -q app scripts`: passed.
- `scripts/probe_sportsgameodds.py --env-file C:\Code\sports_analytics\.env`:
  plan-only, `network_request_count=0`, `writes_performed=false`.
- Full suite with the local env loaded: **436 passed, 2 skipped**, warnings only.
- `alembic check`: **No new upgrade operations detected.**
- Focused odds adapter tests: **6 passed**.
- Focused slate snapshot tests: **3 passed**.

## Next gates

1. Resolve the observed provider team IDs to canonical NBA IDs and verify
   complete game-market pairs across a separately bounded review.
2. Review SportsGameOdds plan/quota semantics, licensing, coverage, and
   timestamp precision before any durable apply or Daily market context.
3. Keep forward H1 timing and G monitoring moving without publishing claims.
4. Run the 2026-27 completed-game bridge smoke after the first completed game.
