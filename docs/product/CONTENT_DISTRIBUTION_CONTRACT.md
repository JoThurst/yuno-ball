# Yuno Ball Content Distribution Contract

Status: proposed product/distribution contract  
Prepared: 2026-07-15

## Purpose

Ensure analytical work creates repeatable site, social, email, and media outputs from one canonical payload.

## Source payloads

Approved payload families:

- daily slate;
- matchup intelligence;
- player role watch;
- availability transition;
- prediction;
- postgame review.

Distribution tooling must not independently recalculate metrics.

## Required metadata

Every distributed item carries internally:

- payload version;
- metric versions;
- as-of timestamp;
- source freshness;
- completeness;
- canonical site URL;
- generated timestamp;
- editorial status.

## Formats

### Daily site card

Full analytical context.

### Social card

- one claim;
- one supporting comparison;
- as-of;
- Yuno branding;
- canonical URL.

### Short-form script

1. Hook
2. Basketball reason
3. Uncertainty
4. What to watch
5. Site call-to-action

### Newsletter block

- matchup title;
- why it matters;
- two edges;
- availability note;
- prediction when approved;
- link.

### Alert

Only for material events:

- important status transition;
- large role change;
- meaningful prediction revision;
- notable line movement after a timestamped observation;
- model disagreement threshold.

## Editorial rules

- no unsupported causation;
- no guaranteed outcome;
- no hidden missing data;
- no market claim from unknown-time historical odds;
- no “injury” label for all G League assignments;
- no fake precision;
- no generated player quote.

## Repeatable series

- You Know Ball Today
- Matchup That Matters
- Rotation Shock
- Style Collision
- Bench Brilliance
- Yuno Called It / Yuno Missed It
- What Changed Before Tip

## Archive

Every distributed item links to a permanent site object.

Do not publish disposable social claims without a canonical record.

## Measurement

Track:

- impressions;
- click-through;
- site engagement;
- subscriber conversion;
- returning visits;
- format completion;
- topic/team performance;
- correction rate.

Do not optimize only for impressions.
