---
name: yuno-security-boundary
description: Review or change Yuno Ball route exposure, authentication, input validation, secrets, CORS, rate limiting, or data-access boundaries. Use for security-sensitive behavior, not every ordinary route edit.
---

# Yuno security boundary

Read `AGENTS.md`, affected routes and middleware, `app/utils/security_config.py`, and the release-surface tests. Identify the environment, actor, sensitive data or operation, and the actual enforcement layer. `secure_endpoint` and a hidden navigation link do not establish authentication; production 404 controls currently keep research, design, and betting pages outside the public beta.

Trace every new or changed route for public reachability, method semantics, validation, SQL identifier allowlists, external fetch behavior, and secret/log exposure. Public GET must be read-only. Keep credentials and database/proxy URLs in environment configuration, never in source, output, or fixtures. Check that a Redis outage does not quietly remove the protection intended for readiness or rate-limited paths.

Verify allowed and denied behavior using production-configured tests, including malformed input and unauthenticated access where applicable. State what was checked and what remains unverified; do not call a read-only research surface private without an access boundary. Update `docs/ROUTE_CATALOG.md` or `docs/DEPLOYMENT_RUNBOOK.md` when exposure or operational controls change.
