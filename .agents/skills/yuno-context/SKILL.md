---
name: yuno-context
description: Establish current Yuno Ball architecture, implementation status, and task scope before cross-cutting work or project-status answers. Skip for a small localized fix.
---

# Yuno context

Start with `AGENTS.md`, exact branch/HEAD, `git status --short`, and relevant implementation found with `rg`. Preserve unrelated edits. Planning documents and dated research are claims until checked against code, migrations, tests, and any live system explicitly in scope.

Use the task-to-document map in `AGENTS.md` to locate only relevant sections; do not preload its document list. Expand to callers or consumers when a concrete dependency requires it. Use `docs/PROJECT_STATUS.md` or a dated handoff only to locate a needed checkpoint, then verify the specific claim. The database profile is a dated snapshot, not live proof. A status request does not authorize resuming unfinished implementation.

In a status answer, identify checkout and evidence level: implemented in code, verified locally, verified in staging, or public deployment. Distinguish roadmap intent from current behavior. For a change, identify its owner and affected contract before editing; update the canonical document when the contract changes.
