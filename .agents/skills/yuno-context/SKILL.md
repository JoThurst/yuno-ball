---
name: yuno-context
description: Establish current Yuno Ball architecture, implementation status, and task scope before cross-cutting work or project-status answers. Skip for a small localized fix.
---

# Yuno context

Start with `AGENTS.md`, exact branch/HEAD, `git status --short`, and relevant implementation found with `rg`. Preserve unrelated edits. Planning documents and dated research are claims until checked against code, migrations, tests, and any live system explicitly in scope.

For material changes, follow the source-of-truth reading requirement in `AGENTS.md`; then focus deeper inspection on the relevant documents. `docs/YUNOBALL_ARCHITECTURE.md` maps boundaries; `docs/DATA_DICTIONARY.md` and `docs/DATABASE_PROFILE.md` cover schema and dated snapshot evidence; `docs/SOURCE_CATALOG.md` covers providers; `docs/METRIC_CATALOG.md` covers formulas; `docs/ROUTE_CATALOG.md` and `docs/PRODUCT_STRATEGY.md` cover product surfaces; `docs/DEPLOYMENT_RUNBOOK.md` covers release gates. Use `docs/PROJECT_STATUS.md` to locate prior checkpoints, then verify the specific claim. The database profile is not live proof.

In a status answer, identify checkout and evidence level: implemented in code, verified locally, verified in staging, or public deployment. Distinguish roadmap intent from current behavior. For a change, identify its owner and affected contract before editing; update the canonical document when the contract changes.
