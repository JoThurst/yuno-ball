---
name: yuno-web-feature
description: Build or revise Yuno Ball Flask routes, services, templates, and Daily or matchup journeys. Use for user-facing web features and route contracts.
---

# Yuno web feature

Read `docs/ROUTE_CATALOG.md`, relevant route/service/template, and `docs/PRODUCT_STRATEGY.md`. For Daily and matchup work, also inspect `docs/product/DAILY_INTELLIGENCE_V1_PRODUCT_SPEC.md`. V1 reading order is selected day's games, then permanent matchup, with archive access. Keep date and game identity stable. A fixture preview does not verify a public release.

Assemble analytical data in services and pass named fields to templates. Expose source, `as_of`, completeness, and useful empty, stale, partial, or unavailable states. Keep observations, predictions, and postgame results distinct. Public GET routes remain read-only; external calls belong behind provider/fetch interfaces.

Verify a real date/game path and an empty or stale path. Check keyboard access, skip link, loading status, semantic main landmark, and stateful menus on affected pages. Measure render latency when changing an expensive path. Check production surface controls before exposing research routes. Update `docs/ROUTE_CATALOG.md` for route changes and `docs/PRODUCT_STRATEGY.md` for product-scope changes.
