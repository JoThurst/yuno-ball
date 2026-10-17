# Daily Intelligence V1 package

Status: implemented as the public descriptive launch-slice contract
Reviewed: 2026-10-10; cross-program status is consolidated in [`docs/PROJECT_STATUS.md`](../PROJECT_STATUS.md)

## Purpose

Daily Intelligence V1 is the first reusable package for turning the existing
cutoff-safe slate data into explainable daily editorial context. It is intended
to give the product and design work a concrete payload to react to before we
commit to a final page, social card, newsletter, or alert layout.

The package is descriptive. It contains no prediction, odds, market comparison,
or new durable metric. Prior rolling SoS remains research-only and is explicitly
excluded from the default payload.

## Contract

The versioned endpoint is:

```text
GET /daily/api/v1?date=YYYY-MM-DD&season=YYYY-YY
```

The local inspection command is:

```text
python scripts/daily_intelligence_v1_report.py --date 2025-03-03 --season 2024-25
```

The visual design lab is available at:

```text
GET /design/daily-v1
```

It opens on the rich historical demo and links to the current/blocked state.
It is a prototype surface, not a second data contract.

The outer contract is defined by the frozen dataclasses in
`app/services/daily_intelligence_service.py` and serializes to JSON with:

| Field | Purpose |
| --- | --- |
| `contract_version` | Stable consumer version: `daily-intelligence-v1`. |
| `status` | `available`, `partial`, or `empty`; this is not a model confidence. |
| `freshness` | Source, as-of, validated-run state, stale state, and explanation. |
| `summary` | Slate count, deterministic ranked game IDs, snapshot metadata, and package counts. |
| `games` | Ranked matchups with editorial priority, team identity, environment, schedule pressure, form, availability uncertainty, players to watch, optional postgame outcome/box-score context, and provenance. |
| `insights` | Deterministic, metric-traceable explanations with stable IDs and source/as-of context. |
| `disclaimers` | Product-safe boundaries that travel with the payload. |

## Current insight families

- Slate summary.
- Editorial matchup priority (context ranking only, not a prediction).
- Pace context.
- Scoring-environment context, not a projected total.
- Schedule-pressure flags.
- Team form from the stored recent-versus-season net-rating delta.
- Official availability uncertainty.
- Player watch from stored heat-index context.

Each insight retains a stable ID, metric context, completeness, and source/as-of
fields where the upstream data provides them. Missing or stale evidence remains
explicit and is never changed to zero.

Schedule display preserves the source precision boundary. Exact schedule rows
may show a formatted tipoff; `date_only` rows show `tipoff unavailable` rather
than formatting midnight as if it were a real start time. The date remains
usable for historical context even when a precise tipoff is unavailable.

## Source and design boundary

The package adapts `build_slate_context`, so it inherits the existing historical
cutoff behavior for versioned snapshots and game-scoped official availability.
It does not make external NBA calls at request time and does not write to the
database or Redis. `/daily/`, `/daily/archive`, the canonical date and matchup
pages, and `/daily/betting` compatibility behavior are documented in the route
catalog; all consume their declared boundaries rather than creating a second
semantic contract.

### Observed postgame context

For a completed game, `games[].actual` carries the observed final result and
score from the durable schedule record. When complete canonical
`player_game_facts` are available, it also carries a bounded set of top scoring
player lines with points, rebounds, assists, minutes, and source metadata. This
is a postgame explanation layer: it never changes the historical pregame
signals, is absent from scheduled-game presentation, and honestly reports
missing player facts rather than treating them as zero.

The next design conversation can use this payload to decide which parts deserve
visual priority: ranked slate, one-line explanations, availability blocks,
schedule context, environment tags, and player-watch modules. Figma work should
not add a second semantic contract; it should consume the same package fields.

## Deferred gates

- 2026-27 current-season smoke remains blocked until a completed Regular Season
  bridge run produces current-season evidence. Preseason is externally underway,
  but the current C7 contract is Regular Season-only; schedule/roster
  onboarding alone is not enough.
- Prior rolling SoS examples are approved as wording/examples only; no SoS
  route, cache, durable field, or production insight is added here.
- Predictions wait for Program G model, walk-forward, calibration, and
  immutable-prediction gates.
- Role-change and lineup-stint insights remain limited until Program C/H lineup
  and expected-minutes evidence is complete.
