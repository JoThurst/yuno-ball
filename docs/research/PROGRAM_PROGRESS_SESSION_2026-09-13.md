# Program Progress Session — 2026-09-13

Status: completed reviewable slices; no production writes; one bounded live odds probe

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

## Verification

- Focused provider, status, Daily launch, market adapter, and navbar tests:
  15 passed after the loader contract test was corrected.
- `python -m compileall -q app scripts`: passed.
- `scripts/probe_sportsgameodds.py --env-file C:\Code\sports_analytics\.env`:
  plan-only, `network_request_count=0`, `writes_performed=false`.
- Preliminary full suite with the local env loaded: 407 passed, 5 skipped, 22
  failures. The failing areas are legacy route aliases, ORM compatibility
  expectations, an unrelated availability mock, an encoding fixture, and the
  first version of the new loader assertion. The final focused run is green;
  the full suite still needs a later baseline-cleanup pass.

## Next gates

1. Resolve the observed provider team IDs to canonical NBA IDs and verify
   complete game-market pairs across a separately bounded review.
2. Review SportsGameOdds plan/quota semantics, licensing, coverage, and
   timestamp precision before any durable apply or Daily market context.
3. Keep forward H1 timing and G monitoring moving without publishing claims.
4. Run the 2026-27 completed-game bridge smoke after the first completed game.
