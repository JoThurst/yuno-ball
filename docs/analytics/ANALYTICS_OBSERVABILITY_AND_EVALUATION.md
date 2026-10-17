# Yuno Ball Analytics Observability and Evaluation

Status: proposed operating contract  
Prepared: 2026-07-15

## Purpose

Make analytics failures, stale inputs, missing coverage, corrections, model degradation, and product-quality issues visible.

## Ingestion metrics

Per source/task:

- last successful run;
- last attempted run;
- duration;
- rows read/inserted/updated/skipped/rejected;
- source freshness;
- duplicate rate;
- parser failure rate;
- unresolved identity rate;
- retries;
- source HTTP status distribution.

## Data-quality metrics

- maximum source date by table;
- season coverage;
- paired games;
- missing dates;
- duplicate natural keys;
- orphan rows;
- unexpected null rates;
- malformed seasons;
- game-ID type conflicts;
- snapshot dates per metric;
- completeness distribution.

## Availability metrics

- reports discovered;
- reports downloaded;
- duplicate-content reports;
- parse success;
- teams not submitted;
- unresolved players;
- material transitions;
- latest report age.

## Odds metrics

- books per game;
- markets per game;
- observation age;
- line/price anomalies;
- unmatched events;
- pregame versus live;
- provider cost;
- polling gaps;
- consensus coverage.

## Feature metrics

- rows produced;
- insufficient-history rate;
- missing-input flags;
- correction revisions;
- feature build latency;
- old snapshot reproducibility;
- feature version distribution.

## Model metrics

- prediction coverage;
- fallback rate;
- calibration;
- log loss/Brier;
- MAE/RMSE;
- performance by season/team/month;
- incomplete-input performance;
- drift;
- revision frequency.

## Product metrics

- Daily load time;
- payload age;
- empty-card rate;
- matchup opens;
- explanation engagement;
- repeat visits;
- postgame return;
- email conversion;
- share-to-site sessions.

## Alerts

Alert on:

- required source stale beyond SLA;
- destructive row-count drop;
- current-season maximum date regression;
- zero games when schedule expects games;
- high parser failure;
- identity resolution degradation;
- no complete Daily payload;
- calibration degradation;
- cache payload version mismatch.

## Runbook requirement

Every alert links to:

- source/task;
- last good run;
- affected seasons/dates;
- retry command;
- validation query;
- rollback or containment action.
