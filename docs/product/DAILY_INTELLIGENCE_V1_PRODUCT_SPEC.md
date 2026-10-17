# Yuno Ball Daily Intelligence V1 Product Specification

Status: implemented launch contract
Prepared: 2026-07-15
Current review: 2026-09-13; cross-program status is consolidated in [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md)

## Product statement

Yuno Ball Daily tells an NBA fan what matters today, why it matters, what may change, and how fresh the information is.

## Primary user jobs

- identify the most important games;
- understand matchup edges quickly;
- see schedule and availability context;
- find players whose roles may change;
- inspect transparent predictions when available;
- return after games to compare expectation with result.

## Page hierarchy

### Daily header

- date and slate state;
- data last refreshed;
- scheduled game count;
- incomplete matchup count;
- most important slate note;
- latest material availability update.

### Ranked slate

Each card contains:

- exact start time and teams when schedule precision supports it; otherwise an
  explicit unavailable-time state;
- Slate Score;
- projected competitiveness;
- team form;
- schedule edge;
- availability uncertainty;
- two or three Style Collision edges;
- players to watch;
- deterministic “why it matters” text;
- data freshness;
- missing-input state;
- link to permanent matchup page.

### Matchup detail

1. Overview
2. Team strength and form
3. Schedule pressure
4. Style Collision
5. Availability and rotation
6. Player role changes
7. Prediction and uncertainty
8. Market context when approved
9. Source and freshness details
10. Postgame review after completion

## Typed payload

Suggested shape:

```json
{
  "payload_version": "daily_matchup.v1",
  "game": {},
  "as_of": {},
  "completeness": {},
  "slate_score": {},
  "team_form": {},
  "schedule": {},
  "style_edges": [],
  "availability": {},
  "players_to_watch": [],
  "prediction": null,
  "market": null,
  "explanations": [],
  "source_status": []
}
```

Every nested contract must be named and versioned.

## Explanation system

Explanations should be deterministic templates based on metric thresholds.

Requirements:

- trace to the underlying metric;
- state direction and context;
- avoid causal certainty;
- avoid fake precision;
- mention missing or stale inputs;
- never generate from a null treated as zero.

Example:

> New York's clearest edge is second-chance creation. Its recent offensive-rebound rate is strong, while the opponent has struggled to complete defensive possessions.

## Empty and stale states

Examples:

- availability report not yet submitted;
- insufficient team history;
- source update delayed;
- market unavailable;
- game postponed;
- prediction withheld due to incomplete inputs.

A missing section should explain why it is missing.

## Historical archive

Permanent routes should support:

- `/daily/YYYY-MM-DD`
- `/matchup/YYYY-MM-DD/away-home`
- team-season form archives;
- prediction history;
- postgame reviews.

Historical pages must select snapshots at or before the historical cutoff.

The launch slice implements these destinations as read-only public
pages:

- `/daily/archive` provides a bounded index of durable Regular Season dates;
- `/daily/YYYY-MM-DD` is the canonical date page;
- `/matchup/YYYY-MM-DD/AWAY-HOME` is the canonical date-scoped matchup page.

The existing `/daily/?date=YYYY-MM-DD` query form remains compatible, but the
canonical links and navigation point to the permanent routes. Team-season form
archives, prediction history, and postgame reviews remain later distribution
and modeling slices.

## Performance

- Daily payload precomputed after validated ingestion;
- Redis contains only versioned disposable payloads;
- DB-only fallback available;
- no per-player external calls in request path;
- source metadata compactly serialized.

## Product analytics

Track:

- daily page visit;
- matchup open;
- explanation expand;
- freshness detail open;
- player watch click;
- prediction detail open;
- email signup;
- share action;
- postgame return.

## V1 exclusions

- player props;
- guaranteed betting edge;
- untimestamped market comparison;
- market edge or recommendation claims during the forward observation pilot;
- generative narrative without deterministic grounding;
- unsupported injury-impact certainty;
- live possession feed.

## Acceptance criteria

- useful without prediction;
- every card has freshness state;
- no historical future snapshot;
- typed contract;
- cache version;
- deterministic explanation tests;
- useful partial-state UI;
- permanent indexable URLs;
- one payload reused by site and distribution tooling.

## Launch implementation note

`GET /daily/` and `GET /daily/YYYY-MM-DD` render this contract as the public
Daily Intelligence V1 surface; `/daily/archive` and
`/matchup/YYYY-MM-DD/AWAY-HOME` provide the historical launch destinations.
Canonical forward market observations may appear as an optional,
timestamped context block when complete sportsbook pairs have been collected;
missing coverage remains explicit. The legacy `/daily/betting` surface remains
available as a compatibility view while the pilot source is evaluated.
