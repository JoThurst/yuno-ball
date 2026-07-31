# Yuno Ball Data Licensing Register

Status: required governance template  
Prepared: 2026-07-15

## Purpose

Track whether each source may be collected, stored, transformed, displayed, used for models, redistributed, sponsored, or sold.

Access to data does not establish commercial permission.

## Register fields

| Field | Description |
|---|---|
| Source | Provider or dataset |
| Source URL | Canonical terms or data page |
| Data categories | Injury, odds, box score, etc. |
| Access method | API, PDF, CSV, manual |
| License/terms version | Exact version/date |
| Internal storage | permitted/unknown/prohibited |
| Internal analysis | permitted/unknown/prohibited |
| Model training | permitted/unknown/prohibited |
| Derived public analysis | permitted/unknown/prohibited |
| Raw public display | permitted/unknown/prohibited |
| Raw redistribution | permitted/unknown/prohibited |
| Paid product use | permitted/unknown/prohibited |
| Betting product use | permitted/unknown/prohibited |
| Attribution | required text/link |
| Retention limits | duration or deletion obligation |
| Rate limits | contractual/technical |
| Commercial contact | provider contact |
| Legal review | not started/in progress/approved/rejected |
| Notes | ambiguity and action |

## Current entries

### Official NBA injury PDFs

Status: terms review required.

Intended use:

- internal source preservation;
- normalized availability analysis;
- public derived explanations.

Do not assume raw PDF redistribution or paid database resale.

### Stat Surge injury archive

Status: project-owner permission confirmed; no standalone formal license file.

Recorded classification: `permission-confirmed-no-formal-license`, public use
approved, commercial use permitted. Internal storage, analysis, model training,
derived public analysis, and paid/commercial product use are permitted by the
confirmed grant. Raw redistribution is permitted by the confirmation but is not
part of the implemented product or staging contract.

Intended use:

- historical internal staging;
- availability research;
- derived historical features if permitted.

### Kaggle historical betting dataset

Status: project-owner permission confirmed; no standalone Kaggle license file
accompanies the preserved pack.

Recorded classification: `permission-confirmed-no-formal-license`, public use
approved, commercial use permitted. The permission resolves the use gate but
does not resolve source timing semantics, bookmaker provenance, anomaly review,
or whether any market represents an opening/closing line.

Intended use:

- historical staging;
- model research;
- derived market baselines.

Unknown:

- commercial display;
- raw redistribution;
- original bookmaker/source rights.

### Future odds provider

Status: vendor-specific contract required.

Evaluate:

- public line display;
- derived probabilities;
- archives;
- redistribution;
- API/package use;
- affiliate conditions.

## Release gates

A source cannot power:

- a public raw-data page;
- a paid API;
- a downloadable dataset;
- a sponsored betting product

until the relevant fields are explicitly approved.

## Repository policy

Commit:

- terms references;
- permission records;
- attribution templates;
- source manifests;
- small test fixtures.

Do not commit:

- purchased datasets;
- credentials;
- licensed bulk raw data;
- private contracts.
