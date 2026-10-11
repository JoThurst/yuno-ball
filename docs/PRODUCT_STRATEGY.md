# Yuno Ball Product and Revenue Strategy

Status: product direction and prioritization contract
Reviewed: 2026-10-10; current cross-program delivery status is consolidated in [`PROJECT_STATUS.md`](PROJECT_STATUS.md)

## Product position

Yuno Ball should be the place an NBA fan visits to understand what matters today, not another database of box scores and not an opaque picks feed. Its advantage should combine trustworthy data, fast daily context, explainable analytics, a recognizable “you know ball” voice, and outputs designed for both the site and social distribution.

## Core user promise

Within a few minutes, a user should be able to answer:

- Which games and players matter today?
- What matchup, rest, form, or availability factors create the edge?
- How fresh and complete is the information?
- What does the model expect, how confident is it, and what could make it wrong?
- Which insight is worth sharing or revisiting after the game?

## Current launch position

The first public product slice is Daily Intelligence V1: a descriptive,
source-backed slate with permanent historical date and matchup destinations.
Completed historical matchups also show what actually happened—a durable final
result and bounded canonical box-score context—separate from the pregame read.
It shows freshness, completeness, and uncertainty as product content. It does
not publish predictions, betting edges, or unsupported rotation claims. The
legacy `/home` path now redirects to Daily. `/daily/betting` remains visible as
a clearly labeled experimental observation surface for the sports-betting and
fantasy audience, but it is not the semantic source of truth for Daily V1.

## Product pillars

### 1. Daily NBA intelligence

Build a fast daily hub with games, standings context, official availability
when complete, rest and schedule pressure, team form, matchup edges, and model
forecasts. Every card should expose source freshness, completeness, and
confidence.

### 2. Explainable matchup analysis

Replace raw table overload with curated offense-versus-defense comparisons, likely pace, shooting profile conflicts, rebounding and turnover edges, recent rotation context, and concise explanations generated from deterministic metrics.

### 3. Auditable predictions

Start with home win probability, expected margin, and expected total. Publish model/version/as-of metadata, retain prediction history, measure calibration, and show misses as well as wins. Add market comparison only after timestamped odds ingestion exists.

### 4. Shareable media system

Every major analytical payload should be reusable as:

- a vertical social card;
- a short-form video script and hook;
- a daily carousel/thread;
- an email or push summary;
- an embeddable chart or linkable team/player page.

The site should be the canonical destination behind the content, not a disconnected side project.

### 5. Trust and performance

Use clear empty, stale, and partial-data states. Avoid fake precision. Pages should remain useful when live NBA endpoints fail by relying on validated stored data and showing the last successful refresh.

## Suggested roadmap

### Foundation

- Fix known ingestion defects, current-season derivation, roster history, corrected box-score upserts, team plus/minus, dynamic SQL validation, and job locking.
- Add migrations, test coverage, structured job runs, data-quality checks, and cache namespace/versioning.
- Establish product analytics for acquisition, activation, retention, page latency, data freshness, and conversion.

### Differentiated V1

- Treat `/daily/` as the canonical daily intelligence page; `/home` is a
  compatibility redirect and `/games` is the durable lookup/archive surface.
- Keep the old dashboard as an internal research/data-quality console and fold
  useful player/team context into dated Daily and Matchup stories.
- Precompute typed matchup payloads.
- Add team form and schedule-pressure features.
- Launch transparent baseline game predictions with immutable history.
- Add indexable team, player, matchup, and daily insight pages with strong internal linking.

### Distribution

- Generate daily branded cards and short-form scripts from the same data contracts.
- Create recurring formats such as “You Know Ball Today,” “Bench Brilliance,” “Matchup That Matters,” and prediction review posts.
- Capture email subscribers with a useful daily digest rather than a generic newsletter form.

### Monetization

Use a ladder rather than gating the entire product immediately:

1. Free site supported by traffic, sponsorship inventory, and selective affiliates.
2. Paid daily/weekly premium report with deeper matchup and model context.
3. Membership with alerts, saved teams, historical model tracking, and advanced filters.
4. Creator/media packages: branded data cards, embeds, newsletters, or licensed feeds.
5. Developer/data packages: documented API or scheduled exports only after data licensing, reliability, rate limits, and support obligations are understood.
6. Sponsorships around recurring content series rather than intrusive generic ads.

Do not market guaranteed outcomes or hide model limitations. Confirm data-provider and league trademark/licensing constraints before selling redistributed raw data or using official marks commercially.

## KPI framework

Track a small product funnel:

- Acquisition: organic search entrances, social referral sessions, returning direct users.
- Activation: user reaches a matchup, prediction, or daily insight interaction.
- Retention: 7-day and 30-day returning users, notification/email retention, favorite-team return rate.
- Trust: data freshness SLA, ingestion success, correction rate, prediction calibration, broken/empty payload rate.
- Revenue: sponsor yield, free-to-email conversion, free-to-paid conversion, churn, revenue per active user.

Do not optimize page views at the expense of trust, latency, or useful task completion.
