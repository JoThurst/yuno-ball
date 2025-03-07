from nba_api.stats.endpoints import leaguedashplayerstats, defensehub, cumestatsteam, cumestatsteamgames, leaguedashteamstats
from app.models.team import Team
from app.models.leaguedashteamstats import LeagueDashTeamStats
import pandas as pd
import json, time
import logging

def fetch_league_dash_player_stats(season='2023-24'):
    """
    Fetch and debug LeagueDashPlayerStats for a given season.
    """
    print(f"\nFetching LeagueDashPlayerStats for {season}...")
    response = leaguedashplayerstats.LeagueDashPlayerStats(season=season).get_normalized_dict()

    if 'LeagueDashPlayerStats' in response and len(response['LeagueDashPlayerStats']) > 0:
        headers = response['LeagueDashPlayerStats'][0].keys()
        first_record = response['LeagueDashPlayerStats'][0]

        print("\nHeaders:", headers)
        print("\nSample Record:", json.dumps(first_record, indent=4))
    else:
        print("\nNo data found for LeagueDashPlayerStats.")

def fetch_defense_hub_stats(season='2019-20'):
    """
    Fetch and debug DefenseHub stats for a given season, handling API failures.
    """
    print(f"\nFetching DefenseHub stats for {season}...")
    
    try:
        # Attempt API Call
        response = defensehub.DefenseHub(
            game_scope_detailed="Season",
            league_id="00",
            player_or_team="Team",
            player_scope="All Players",
            season=season,
            season_type_playoffs="Regular Season"
        )

        # ✅ Ensure the API returned valid JSON before parsing
        raw_response = response.get_json()
        if not raw_response or raw_response.strip() == "":
            logging.error(f"DefenseHub API returned an empty response for {season}.")
            print("\n❌ DefenseHub API returned an empty response.")
            return
        
        response_dict = response.get_dict()

        if "resultSets" not in response_dict:
            print("\nNo data found for DefenseHub.")
            return
        
        # Iterate through the different datasets available in DefenseHub
        for result_set in response_dict["resultSets"]:
            stat_name = result_set["name"]
            headers = result_set["headers"]
            rows = result_set["rowSet"]

            print(f"\n📊 {stat_name}: {len(rows)} records found.")

            if rows:
                print(f"Headers: {headers}")
                print(f"First Record: {json.dumps(rows[0], indent=4)}")
            else:
                print(f"No data available for {stat_name}.")

    except Exception as e:
        logging.error(f"Error fetching DefenseHub data for {season}: {e}")
        print(f"\n❌ Error fetching DefenseHub data: {e}")


def fetch_team_game_ids(season='2023-24'):
    """
    Fetch all game IDs for each team using `CumeStatsTeamGames`.

    Args:
        season (str): The season to fetch data for (e.g., "2023-24").

    Returns:
        dict: { team_id: [game_id1, game_id2, ...] }
    """
    print(f"\nFetching game IDs for all teams in {season}...")

    # ✅ Step 1: Fetch all team IDs from the database
    teams = Team.get_all_teams()
    if not teams:
        print("\n❌ No teams found in the database.")
        return {}

    team_game_ids = {}

    for team in teams:
        team_id = team["team_id"]
        print(f"\nFetching game IDs for Team ID: {team_id}...")

        try:
            # ✅ Step 2: Fetch game IDs for the specific team
            response = cumestatsteamgames.CumeStatsTeamGames(
                league_id="00",
                season=season[:4],  # Convert "2023-24" to "202324"
                season_type_all_star="Regular Season",
                team_id=team_id  # Correctly pass the `team_id`
            ).get_dict()

            # ✅ Step 3: Validate API response
            if "resultSets" not in response:
                print(f"\n❌ No data found for team {team_id}. Skipping.")
                continue

            game_data = response["resultSets"][0]  # The first result set contains game info
            headers = game_data["headers"]
            rows = game_data["rowSet"]

            for row in rows:
                game_info = dict(zip(headers, row))
                game_id = game_info["GAME_ID"]

                if team_id not in team_game_ids:
                    team_game_ids[team_id] = []
                team_game_ids[team_id].append(game_id)

            print(f"✅ Retrieved {len(team_game_ids[team_id])} game IDs for team {team_id}.")

        except Exception as e:
            logging.error(f"Error fetching CumeStatsTeamGames data for team {team_id}: {e}")
            print(f"\n❌ Error fetching game IDs for team {team_id}: {e}")

        time.sleep(1)  # 🔥 Avoid API rate limits

    print(f"\n📊 Retrieved game IDs for {len(team_game_ids)} teams.")
    return team_game_ids



def fetch_team_stats_by_game(season='2023-24'):
    """
    Fetch total team stats for each team using `CumeStatsTeamGames` and `CumeStatsTeam`,
    then calculate rankings for key statistics.

    Args:
        season (str): The season to fetch data for (e.g., "2023-24").
    """
    print(f"\nFetching total team stats for {season}...")

    # ✅ Fetch game IDs for all teams
    team_game_ids = fetch_team_game_ids(season)

    if not team_game_ids:
        print("\n❌ No game IDs retrieved. Skipping stats fetch.")
        return

    total_team_stats = []

    for team_id, game_ids in team_game_ids.items():
        print(f"\nFetching team stats for team {team_id} with {len(game_ids)} games...")

        try:
            # ✅ Fetch stats for all games of this team
            response = cumestatsteam.CumeStatsTeam(
                league_id="00",
                season=season[:4],
                season_type_all_star="Regular Season",
                team_id=team_id,
                game_ids="|".join(game_ids),  # Provide all game IDs at once
            ).get_dict()

            if "resultSets" not in response:
                print(f"\n❌ No data found for team {team_id}.")
                continue

            # ✅ Extract `TotalTeamStats`
            total_team_stats_set = None
            for result_set in response["resultSets"]:
                if result_set["name"] == "TotalTeamStats":
                    total_team_stats_set = result_set
                    break

            if total_team_stats_set is None or not total_team_stats_set["rowSet"]:
                print(f"\n❌ No TotalTeamStats data found for team {team_id}. Skipping.")
                continue

            headers = total_team_stats_set["headers"]
            rows = total_team_stats_set["rowSet"]

            for row in rows:
                stats_data = dict(zip(headers, row))
                stats_data["team_id"] = team_id  # Ensure we have the correct team ID
                total_team_stats.append(stats_data)

            print(f"✅ Successfully fetched total stats for team {team_id}.")

        except Exception as e:
            logging.error(f"Error fetching CumeStatsTeam data for team {team_id}: {e}")
            print(f"\n❌ Error fetching team stats for team {team_id}: {e}")

        time.sleep(1)  # 🔥 Avoid API rate limits

    print(f"\n📊 Retrieved total team stats for {len(total_team_stats)} games.")

    # ✅ Convert data to a DataFrame for ranking calculations
    df = pd.DataFrame(total_team_stats)

    # ✅ Select key stats for ranking
    ranking_stats = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "FG_PCT", "FG3_PCT", "FT_PCT"]
    rank_columns = {}

    for stat in ranking_stats:
        if stat in df.columns:
            df[f"{stat}_Rank"] = df[stat].rank(ascending=False, method="min")
            rank_columns[f"{stat}_Rank"] = df[f"{stat}_Rank"]

    # ✅ Display Rankings
    print("\n📊 Team Rankings for Key Stats:")
    print(df[["team_id"] + list(rank_columns.keys())].sort_values(by="PTS_Rank"))

    return df

def fetch_league_dash_team_stats(season="2023-24"):
    """
    Fetch and debug LeagueDashTeamStats for a given season.
    Logs output to a markdown file for later use.
    """
    print(f"\nFetching LeagueDashTeamStats for {season}...")

    measure_types = ["Base", "Advanced", "Misc", "Four Factors", "Scoring", "Opponent", "Usage", "Defense"]
    per_modes = ["Totals", "Per48", "Per100Possessions"]
    season_types = ["Regular Season", "Playoffs"]

    all_team_stats = []
    output_filename = "league_dash_team_stats_output.md"

    # ✅ Start logging to a markdown file
    with open(output_filename, "w", encoding="utf-8") as md_file:
        md_file.write(f"# LeagueDashTeamStats API Output ({season})\n")
        md_file.write(f"_This file contains all measure types, per modes, and season types retrieved from the API._\n\n")

        for measure_type in measure_types:
            for per_mode in per_modes:
                for season_type in season_types:
                    log_message = f"\n## 📊 MeasureType: {measure_type}, PerMode: {per_mode}, SeasonType: {season_type}\n"
                    print(log_message)
                    md_file.write(log_message)

                    try:
                        # ✅ API Call
                        response = leaguedashteamstats.LeagueDashTeamStats(
                            league_id_nullable="00",
                            season=season,
                            season_type_all_star=season_type,
                            measure_type_detailed_defense=measure_type,
                            per_mode_detailed=per_mode,
                            rank="Y"  # Ensure rankings are included
                        ).get_dict()

                        # ✅ Validate response
                        if "resultSets" not in response:
                            log_message = f"\n❌ No data found for {measure_type}, {per_mode}, {season_type}.\n"
                            print(log_message)
                            md_file.write(log_message)
                            continue

                        data_set = response["resultSets"][0]  # The first result set contains team stats
                        headers = data_set["headers"]
                        rows = data_set["rowSet"]

                        if rows:
                            log_message = f"\n- **Total Records:** {len(rows)}\n"
                            print(log_message)
                            md_file.write(log_message)

                            md_file.write("\n**Headers:**\n")
                            md_file.write("```\n" + ", ".join(headers) + "\n```\n")

                            md_file.write("\n**Sample Record:**\n")
                            md_file.write("```json\n" + json.dumps(rows[0], indent=4) + "\n```\n")

                            for row in rows:
                                stats_data = dict(zip(headers, row))
                                stats_data["MeasureType"] = measure_type
                                stats_data["PerMode"] = per_mode
                                stats_data["SeasonType"] = season_type
                                all_team_stats.append(stats_data)
                        else:
                            log_message = f"\n❌ No data available for {measure_type}, {per_mode}, {season_type}.\n"
                            print(log_message)
                            md_file.write(log_message)

                    except Exception as e:
                        log_message = f"\n❌ Error fetching data for {measure_type}, {per_mode}, {season_type}: {e}\n"
                        logging.error(log_message)
                        print(log_message)
                        md_file.write(log_message)

                    time.sleep(1)  # 🔥 Avoid API rate limits

        md_file.write(f"\n## 📊 Total Records Collected: {len(all_team_stats)}\n")

    print(f"\n✅ All output has been logged to `{output_filename}`.")
    return all_team_stats

# Run the function to test
#fetch_league_dash_team_stats()



def ingest_league_dash_team_stats(season="2023-24"):
    """
    Fetch and insert LeagueDashTeamStats for all measure types and per modes.
    Optimized to process all measure types before inserting into the database.
    """
    print(f"\n🚀 Ingesting LeagueDashTeamStats for {season}...")

    # ✅ Ensure Table Exists Before Insert
    LeagueDashTeamStats.create_table()

    measure_types = ["Base", "Advanced", "Misc", "Four Factors", "Scoring", "Opponent", "Defense"]
    per_modes = ["Totals", "Per48", "Per100Possessions"]
    season_types = ["Regular Season", "Playoffs"]

    all_team_stats = []

    for measure_type in measure_types:
        measure_stats = {}  # Store data by team_id to fill all columns together

        for per_mode in per_modes:
            for season_type in season_types:
                print(f"\n📊 Fetching: MeasureType={measure_type}, PerMode={per_mode}, SeasonType={season_type}")

                try:
                    # ✅ API Call
                    response = leaguedashteamstats.LeagueDashTeamStats(
                        league_id_nullable="00",
                        season=season,
                        season_type_all_star=season_type,
                        measure_type_detailed_defense=measure_type,
                        per_mode_detailed=per_mode,
                        rank="Y"
                    ).get_dict()

                    # ✅ Validate response
                    if "resultSets" not in response:
                        print(f"\n❌ No data found for {measure_type}, {per_mode}, {season_type}.")
                        continue

                    data_set = response["resultSets"][0]  # The first result set contains team stats
                    headers = data_set["headers"]
                    rows = data_set["rowSet"]

                    if rows:
                        for row in rows:
                            team_id = row[headers.index("TEAM_ID")]
                            team_name = row[headers.index("TEAM_NAME")]

                            # Initialize team entry if not present
                            if team_id not in measure_stats:
                                measure_stats[team_id] = {
                                    "team_id": team_id,
                                    "team_name": team_name,
                                    "season": season,
                                    "season_type": season_type
                                }

                            # Add prefixed stats
                            for i, stat in enumerate(headers):
                                if stat not in ["TEAM_ID", "TEAM_NAME"]:
                                    col_name = f"{measure_type}_{per_mode}_{stat}"
                                    measure_stats[team_id][col_name] = row[i]

                        print(f"✅ Fetched {len(rows)} records for {measure_type} {per_mode}.")

                except Exception as e:
                    logging.error(f" Error fetching data for {measure_type}, {per_mode}, {season_type}: {e}")
                    print(f"\n❌ Error fetching data: {e}")

                time.sleep(1)  # 🔥 Avoid API rate limits

        # ✅ Insert into DB with Correct Function Call
        for team_id, team_data in measure_stats.items():
            try:
                LeagueDashTeamStats.add_team_season_stat(team_data)  # ✅ Corrected argument passing
                print(f"✅ Inserted stats for Team ID {team_id}")

            except Exception as e:
                logging.error(f" Error inserting data for Team ID {team_id}: {e}")

    print(f"\n✅ Ingestion completed for {season}.")

# Run the function to ingest data
ingest_league_dash_team_stats()


#fetch_league_dash_player_stats()
#fetch_defense_hub_stats()
