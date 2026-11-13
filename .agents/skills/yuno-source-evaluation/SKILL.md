---
name: yuno-source-evaluation
description: Evaluate a candidate NBA, injury, odds, or external dataset provider before integration or paid collection. Use for source feasibility, license, timing, identity, coverage, and cost decisions.
---

# Yuno source evaluation

Read `docs/research/SOURCE_EVALUATION_MATRIX.md`, the relevant `docs/SOURCE_CATALOG.md` entry, and any program-specific research gate. Start with a credential-free, zero-network assessment using public docs, local fixtures, and existing evidence. A trial should have a bounded sample, request/cost ceiling, explicit network approval if needed, and a stop condition; never expose credentials.

Evaluate source grain, provider and retrieval timestamps, timestamp precision, data-availability semantics, identity mapping, historical range, completeness, corrections, schema stability, raw retention, commercial/redistribution/model-training rights, and expected spend. Distinguish a 403, transport failure, empty slate, missing market, and unsupported endpoint. For markets, require complete reciprocal selections and preserve unknown historical timing.

Deliver a scored recommendation and unresolved gates: reject, research-only, staging-only, or candidate for an explicit integration decision. No provider evaluation authorizes a scheduled writer, canonical promotion, public claim, or billable recurring plan. Update the source catalog only after a source's accepted contract changes; keep exploratory evidence in research documentation.
