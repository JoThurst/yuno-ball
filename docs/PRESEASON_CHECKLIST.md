# Preseason / Season-Open Checklist

Short dry-run sequence before automating daily ingest for 2026-27.

1. **Connectivity** — activate venv, confirm `DATABASE_URL`, run `python scripts/verify_proxy_setup.py` (or `--local` if not using proxy).
2. **Season string** — `python -c "from app.utils.season_utils import get_current_season; print(get_current_season())"` (October+ → new season).
3. **Light fetch** — `python daily_fetch.py --tasks players rosters schedule future --local` (add `--season 2026-27` once CDN has it).
4. **Validate historical day** — `python scripts/validate_daily_data.py --season 2025-26 --date 2026-03-03` (known completed slate).
5. **Full quiet-day run** — `python daily_ingest.py --local` then confirm `data/last_ingest_success.json` and validation report.
6. **Schedule Task Scheduler** — `scripts/run_daily_ingest.ps1` per [DAILY_SCRIPTS.md](DAILY_SCRIPTS.md).

Out of scope: MLB (`mlb_temp/`), schema redesign.
