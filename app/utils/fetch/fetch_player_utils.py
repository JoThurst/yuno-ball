from nba_api.stats.endpoints import playergamelogs
from nba_api.stats.static import players, teams
from app.models.player import Player
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from app.utils.config_utils import logger, API_RATE_LIMIT, RateLimiter, MAX_WORKERS
from app.utils.fetch.api_utils import get_api_config, create_api_endpoint
from app.models.player_streaks import PlayerStreaks

import time

# Define a rate limiter to avoid hitting API rate limits
rate_limiter = RateLimiter(max_requests=15, interval=30)

def fetch_player_streaks(season='2024-25'):
    """
    Fetch and store player streaks for the last 10 games in the 2024-25 season.

    Tracks streaks for:
    - Points: 10, 15, 20, 25
    - Rebounds: 4, 6, 8, 10
    - Assists: 2, 4, 6, 8, 10
    - 3-Pointers Made: 1, 2, 3, 4
    """
    print(f"\nFetching player game logs for season {season}...\n")
    PlayerStreaks.create_table()
    PlayerStreaks.clear_streaks()

    # Define thresholds for streaks
    streak_thresholds = {
        "PTS": [10, 15, 20, 25],
        "REB": [4, 6, 8, 10],
        "AST": [2, 4, 6, 8, 10],
        "FG3M": [1, 2, 3, 4],
    }

    active_players = players.get_active_players()
    player_ids = [p['id'] for p in active_players]

    streak_data = []

    def fetch_batch(player_id_batch):
        """Fetch game logs for a batch of players with retries on timeouts."""
        try:
            rate_limiter.wait_if_needed()
            time.sleep(1.8)

            streak_results = []

            for player_id in player_id_batch:
                retries = 3
                for attempt in range(retries):
                    try:
                        time.sleep(API_RATE_LIMIT)  # Avoid rate-limiting issues
                        rate_limiter.wait_if_needed()

                        # Use the create_api_endpoint function to handle proxy configuration
                        logs = create_api_endpoint(
                            playergamelogs.PlayerGameLogs,
                            player_id_nullable=player_id,
                            season_nullable=season,
                            last_n_games_nullable=10,
                            timeout=40
                        ).get_data_frames()[0]

                        if logs.empty:
                            logger.warning(f" No data returned for player {player_id} (Attempt {attempt+1}/{retries})")
                            continue  # Try again

                        player_name = Player.get_player_name(player_id)

                        # Track streaks
                        for stat, thresholds in streak_thresholds.items():
                            for threshold in thresholds:
                                streak = (logs[stat] >= threshold).sum()

                                if streak >= 7:
                                    logger.info(f" Found streak for {player_name}: {stat} >= {threshold} in {streak}/10 games")

                                    streak_results.append({
                                        "player_id": player_id,
                                        "player_name": player_name,
                                        "stat": stat,
                                        "threshold": threshold,
                                        "streak_games": streak,
                                        "season": season
                                    })

                        break  # Exit retry loop if successful

                    except TimeoutError:
                        logger.warning(f" Timeout for player {player_id}, retrying ({attempt+1}/{retries})...")
                        time.sleep(5)  # Short delay before retry
                    except Exception as e:
                        logger.error(f" Error fetching logs for player {player_id}: {e}")
                        break  # Do not retry on non-timeout errors

            return streak_results

        except Exception as e:
            logger.error(f" Error fetching batch {player_id_batch}: {e}")
            return []

    # Batch players to avoid API overload
    batch_size = 3  # Keep batch size small to ensure API reliability
    player_batches = [player_ids[i:i + batch_size] for i in range(0, len(player_ids), batch_size)]

    # ✅ Use a dictionary to track futures
    futures_dict = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for batch in player_batches:
            future = executor.submit(fetch_batch, batch)
            futures_dict[future] = batch  # Store batch info for debugging

        for future in tqdm(as_completed(futures_dict), total=len(futures_dict), desc="Fetching player logs"):
            try:
                result = future.result()
                if result:
                    streak_data.extend(result)
                else:
                    logger.warning(f" No streaks found in batch {futures_dict[future]}")
            except Exception as e:
                logger.error(f" Error processing batch {futures_dict[future]}: {e}")

    # ✅ Store streaks in the database instead of CSV
    if streak_data:
        PlayerStreaks.store_streaks(streak_data)  # Call the new class to store streaks
        logger.info(f" Stored {len(streak_data)} player streaks in the database.")
    else:
        logger.info(" No qualifying streaks found")
