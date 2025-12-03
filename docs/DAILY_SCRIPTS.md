# Daily Scripts Guide

This guide covers the daily data ingestion and calculation scripts for the NBA Sports Analytics platform.

## Overview

The daily pipeline is split into three scripts:

| Script | Purpose | Log File |
|--------|---------|----------|
| `daily_ingest.py` | Orchestrator - runs both fetch and calculate | `daily_ingest.log` |
| `daily_fetch.py` | Fetches data from NBA APIs | `daily_fetch.log` |
| `daily_calculate.py` | Runs analysis on fetched data | `daily_calculate.log` |

## Quick Start

```bash
# Activate virtual environment first
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run the full pipeline
python daily_ingest.py

# Or run phases separately
python daily_fetch.py      # Fetch all data
python daily_calculate.py  # Run all calculations
```

---

## daily_ingest.py (Orchestrator)

The main entry point that runs both fetch and calculate phases.

### Basic Usage

```bash
# Run everything (default)
python daily_ingest.py

# Only fetch data (skip calculations)
python daily_ingest.py --fetch-only

# Only run calculations (skip fetching)
python daily_ingest.py --calc-only

# List all available tasks
python daily_ingest.py --list
```

### Selective Tasks

```bash
# Run specific fetch tasks, all calculations
python daily_ingest.py --fetch-tasks players rosters gamelogs

# Run all fetch, specific calculations
python daily_ingest.py --calc-tasks streaks heat consistency

# Combine both
python daily_ingest.py --fetch-tasks players gamelogs --calc-tasks streaks heat

# Exclude specific tasks
python daily_ingest.py --exclude-fetch injury odds --exclude-calc flags
```

### API Options

```bash
# Force proxy usage (rotates through configured proxies)
python daily_ingest.py --proxy

# Force local/direct connection (bypass proxies)
python daily_ingest.py --local

# Override season
python daily_ingest.py --season 2023-24
```

---

## daily_fetch.py (Data Fetching)

Fetches data from NBA APIs with rate limiting and error handling.

### Available Tasks

| Task | Description | API Calls |
|------|-------------|-----------|
| `players` | Sync active players and available_seasons | ~1 |
| `rosters` | Update current team rosters | ~30 |
| `gamelogs` | Fetch player game logs (current season) | ~500+ |
| `schedule` | Update game schedule with results | ~1 |
| `future` | Fetch upcoming game schedule | ~1 |
| `teamstats` | Fetch team game stats for season | ~30 |
| `leagueteam` | Fetch league-wide team statistics | ~10 |
| `leagueplayer` | Fetch league-wide player statistics | ~10 |
| `injury` | Fetch player injury/status from boxscores | ~50-100 (batch) |
| `odds` | Fetch today's game betting odds | 1 |

### Usage Examples

```bash
# Run all fetch tasks
python daily_fetch.py

# List available tasks with descriptions
python daily_fetch.py --list

# Run specific tasks only
python daily_fetch.py --tasks players rosters gamelogs

# Run all except specified
python daily_fetch.py --exclude injury odds

# Use proxy for API calls
python daily_fetch.py --proxy

# Force local (no proxy)
python daily_fetch.py --local
```

### Recommended Order

The default order is optimized for data dependencies:

1. `players` - Base player data
2. `rosters` - Current team assignments
3. `gamelogs` - Player game-by-game stats
4. `schedule` - Game results
5. `future` - Upcoming games
6. `teamstats` - Team game logs
7. `leagueteam` - League team stats
8. `leagueplayer` - League player stats
9. `injury` - Injury/status data (slower, batch)
10. `odds` - Today's odds only

---

## daily_calculate.py (Calculations)

Runs analysis and calculations on data already in the database.

### Available Tasks

| Task | Description | Depends On |
|------|-------------|------------|
| `streaks` | Consecutive streaks and recent form windows | gamelogs |
| `heat` | Hot/cold player identification (recent vs season) | gamelogs |
| `consistency` | Player volatility/CV for each stat | gamelogs |
| `schedule` | B2B, rest days, rest advantage analysis | schedule |
| `metrics` | Team performance + Strength of Schedule | teamstats, schedule |
| `flags` | Qualitative team performance tags | metrics |
| `environment` | Today's game context analysis | metrics, schedule |

### Usage Examples

```bash
# Run all calculations
python daily_calculate.py

# List available tasks with descriptions
python daily_calculate.py --list

# Run specific tasks only
python daily_calculate.py --tasks streaks heat consistency

# Run all except specified
python daily_calculate.py --exclude flags environment

# Override season
python daily_calculate.py --season 2023-24
```

### Recommended Order

Tasks are ordered based on dependencies:

1. `streaks` - Needs gamelogs
2. `heat` - Needs gamelogs
3. `consistency` - Needs gamelogs
4. `schedule` - Needs game schedule
5. `metrics` - Needs team stats + schedule
6. `flags` - Needs metrics (calculated first)
7. `environment` - Needs metrics + schedule

---

## Common Workflows

### Daily Production Run

```bash
# Full pipeline - run overnight or morning
python daily_ingest.py
```

### Quick Update (Skip Heavy Tasks)

```bash
# Fetch essentials only
python daily_fetch.py --tasks schedule future odds

# Calculate game-day relevant only
python daily_calculate.py --tasks metrics flags environment
```

### Backfill Historical Data

```bash
# Fetch old season data
python daily_fetch.py --tasks gamelogs schedule teamstats --season 2023-24

# Calculate for old season
python daily_calculate.py --season 2023-24
```

### Debug Specific Tasks

```bash
# Test just one fetch task
python daily_fetch.py --tasks odds

# Test just one calculation
python daily_calculate.py --tasks consistency
```

### Skip Slow Tasks for Development

```bash
# Skip injury (batch boxscore calls) and odds
python daily_ingest.py --exclude-fetch injury odds

# Skip slow calculations
python daily_ingest.py --exclude-calc streaks heat
```

---

## Error Handling

### Fetch Errors

If a fetch task fails:
- The error is logged to `daily_fetch.log`
- Other tasks continue running
- Summary shows which tasks failed

```bash
# Check logs for errors
Get-Content daily_fetch.log -Tail 50  # Windows PowerShell
tail -50 daily_fetch.log              # Linux/Mac
```

### Rate Limiting

The fetchers implement:
- **Rate Limiter**: 30 requests per 25 seconds
- **Batch Processing**: Games processed in batches with delays
- **Adaptive Throttling**: Backs off after consecutive failures
- **Retry Logic**: 3 retries with exponential backoff

If you're getting rate limited:
```bash
# Use proxy rotation
python daily_fetch.py --proxy

# Or increase delays in code (base_fetcher.py)
```

### Calculation Errors

If a calculation fails:
- Check `daily_calculate.log` for stack traces
- Ensure required data exists (run fetch first)
- Check for data quality issues

---

## Scheduling

### Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task → "NBA Daily Ingest"
3. Trigger: Daily at 6:00 AM (or preferred time)
4. Action: Start a program
   - Program: `C:\Code\sports_analytics\venv\Scripts\python.exe`
   - Arguments: `daily_ingest.py`
   - Start in: `C:\Code\sports_analytics`

### Linux Cron

```bash
# Edit crontab
crontab -e

# Add line (runs at 6 AM daily)
0 6 * * * cd /path/to/sports_analytics && source venv/bin/activate && python daily_ingest.py >> /var/log/nba_ingest.log 2>&1
```

### AWS (EC2)

The scripts detect AWS environment automatically and:
- Reduce MAX_WORKERS to 1 (single-threaded)
- Log to CloudWatch if configured

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `FORCE_PROXY` | Always use proxy | `false` |
| `FORCE_LOCAL` | Never use proxy | `false` |
| `MAX_WORKERS` | Thread pool size | `3` |

### Proxy Configuration

See `docs/proxy_setup.md` for proxy configuration details.

---

## Troubleshooting

### "DATABASE_URL environment variable is not set"

```bash
# Create .env file with:
DATABASE_URL=postgresql://user:pass@host:5432/database
```

### "Import error - Python path issue"

```bash
# Ensure you're in the project root
cd C:\Code\sports_analytics

# Activate venv
venv\Scripts\activate

# Try running
python daily_ingest.py
```

### "No games found" or "0 records"

This is normal if:
- It's off-season
- No games scheduled today
- Data was already fetched (incremental)

### Fetch task takes very long

The `injury` task fetches boxscores in batches. For a full season backfill:
- ~1,230 games × 1 API call each
- Rate limited to avoid bans
- Can take 30-60 minutes

Use `--exclude injury` for faster runs during development.

