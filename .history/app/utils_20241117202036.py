import time
from datetime import datetime
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    playercareerstats,
    commonteamroster,
    leaguedashplayerstats,
    commonplayerinfo,
)

from app.models import Player, Statistics, Team, LeagueDashPlayerStats
from db_config import get_connection
# Establish connection to PostgreSQL database
conn = get_connection(schema="public")
# Create a cursor for executing SQL commands
cur = conn.cursor()


# def fetch_and_store_players():
#     """Fetch all NBA players and store them in ChromaDB."""
#     #returns all players
#     all_players = players.get_players()
#     #active_players_moreinfo= playerindex.PlayerIndex(active_nullable=True)
# .get_data_frames()[0]
#     for player in all_players:
#         player_id = player["id"]
#         time.sleep(5)
#         cplayerinfoObj = commonplayerinfo.CommonPlayerInfo(player_id=
# player_id, timeout=300).get_data_frames[0]
#         availableSeasons = cplayerinfoObj["AvailableSeasons"]
#         cPlayerInfo = cplayerinfoObj['CommonPlayerInfo']
#         from_year = cPlayerInfo['FROM_YEAR']
#         to_year = cPlayerInfo['TO_YEAR']
#         available_seasons = availableSeasons # Calculate Available Seasons
# from from_year and to_year to 2017-18 2018-19 ...
#         name = player["full_name"]
#         position = cPlayerInfo['POSITION']  # nba_api doesn't provide
# position in the static API
#         weight= cPlayerInfo['WEIGHT']
#         born_date=cPlayerInfo['BIRTHDATE']
#         age= age #Calculate Age from Birthdate: Output Example "1998-03-
# 03T00:00:00"
#         exp=cPlayerInfo['SEASON_EXP']
#         school=cPlayerInfo['SCHOOL']

#         # Add player to ChromaDB
#         Player.add_player(player_id, name, position, weight,born_date, age,
# exp,school, available_seasons= available_seasons)
#     print("All active players have been successfully stored.")


def fetch_and_store_players():
    """Fetch all NBA players and store them in the players table."""
    # Define the range of seasons we are storing
    valid_seasons = [
        f"{year}-{(year + 1) % 100:02}"
        for year in range(2015, 2025)
    ]
# Fetch all players

    all_players = players.get_players()

    for player in all_players:
        player_id = player["id"]
        time.sleep(5)  # Avoid rate-limiting issues

        try:
            # Fetch player info using the API
            cplayerinfo_obj = commonplayerinfo.CommonPlayerInfo(
                player_id=player_id, timeout=300)
            available_seasons_df = cplayerinfo_obj.get_data_frames()[1]  
            # Second DataFrame is AvailableSeasons
            cplayerinfo_data = cplayerinfo_obj.get_data_frames()[0].iloc[0]
            # First DataFrame is CommonPlayerInfo
            # Extract and calculate data
            from_year = int(cplayerinfo_data["FROM_YEAR"])
            to_year = int(cplayerinfo_data["TO_YEAR"])
            name = player["full_name"]
            position = cplayerinfo_data.get("POSITION", "Unknown")
            weight = (
                int(cplayerinfo_data.get("WEIGHT", 0))
                if cplayerinfo_data.get("WEIGHT")
                else None
            )
            born_date = cplayerinfo_data.get("BIRTHDATE", None)
            exp = (
                int(cplayerinfo_data.get("SEASON_EXP", 0))
                if cplayerinfo_data.get("SEASON_EXP")
                else None
            )
            school = cplayerinfo_data.get("SCHOOL", None)
            # Calculate age
            age = None
            if born_date:
                born_date_obj = datetime.strptime(
                    born_date.split("T")[0], "%Y-%m-%d"
                    )
                age = datetime.now().year - born_date_obj.year
            # Calculate available seasons within the valid range
            available_seasons = [
                season for season in valid_seasons if int(season[:4]) >=
                from_year and int(season[:4]) <= to_year
            ]
            if available_seasons:
                # Add player to the database
                Player.add_player(
                    player_id=int(player_id),  # Ensure player_id is Python int
                    name=name,
                    position=position,
                    weight=weight,
                    born_date=born_date,
                    age=age,
                    exp=exp,
                    school=school,
                    available_seasons=",".join(available_seasons)
                    # Store as comma-separated string
                )
                print(f"Player {name} (ID: {player_id}) added with seasons: {
                    available_seasons}.")
            else:
                print(
                    f"Player {name} (ID: {player_id}) "
                    "has no valid seasons in the range."
                    )
        except Exception as e:
            print(f"Error processing player {player['full_name']} (ID: {
                player_id}): {e}")

    print("All players have been successfully stored.")
# def fetch_and_store_player_stats(player_id):
#     """Fetch career stats for a player and store them in ChromaDB."""
#     career = playercareerstats.PlayerCareerStats(player_id=player_id)
#     stats_df = career.get_data_frames()[0]
# # Get the main DataFrame from the response

#     for _, row in stats_df.iterrows():
#         # Extract relevant data for statistics
#         stat_id = f"{player_id}_{row['SEASON_ID']}"
#         game_date = row["SEASON_ID"]
#         points = row["PTS"]
#         rebounds = row["REB"]
#         assists = row["AST"]
#         steals = row["STL"]
#         blocks = row["BLK"]

#         # Add stats entry to ChromaDB
#         Statistics.add_stat(player_id, game_date, points, rebounds, assists,
# steals, blocks)
#     print(
    # f"Career stats for player {player_id} have been stored successfully."
    # )


def fetch_and_store_player_stats(player_id):

    """Fetch and store career stats for a player if not already in the
    database."""
    # Skip API call if player stats already exist
    Statistics.create_table()
    if Statistics.stats_exist_for_player(player_id):
        print(
            f"Stats for player {player_id} already exist. Skipping API call.")
        return

    retries = 3  # Number of retries
    delay = 2  # Initial delay between retries

    for attempt in range(retries):
        try:
            # Fetch player stats from NBA API
            time.sleep(10)
            career_stats = playercareerstats.PlayerCareerStats(
                player_id=player_id, timeout=300)
            stats_df = career_stats.get_data_frames()[0]

            # Store stats in database
            for _, row in stats_df.iterrows():
                game_date = row['SEASON_ID']
                points = row['PTS']
                rebounds = row['REB']
                assists = row['AST']
                steals = row['STL']
                blocks = row['BLK']

                Statistics.add_stat(player_id, game_date, points, rebounds,
                                    assists, steals, blocks)

            print(f"Stats for player {player_id} stored successfully.")
            break  # Exit loop if successful

        except Exception as e:
            print(f"Error fetching stats for player {player_id}: {e}")
            if attempt < retries - 1:  # Only retry if attempts are left
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print(
                    f"Failed to fetch stats for player {player_id} after "
                    "{retries} attempts.")


def fetch_and_store_current_rosters():
    """Fetch and store roster information for current NBA teams."""
    teams_list = teams.get_teams()

    for team in teams_list:
        # Add the team to the database
        team_id = team['id']
        team_name = team['full_name']
        team_abbreviation = team['abbreviation']

        # Create or retrieve the team in the database
        team_obj = Team.add_team(name=team_name,
                                 abbreviation=team_abbreviation)
        print(f"Added {team_name} with {team_id} \n Sleeping for 15 Seconds")
        time.sleep(15)
        # Fetch the roster for this team
        team_roster_data = commonteamroster.CommonTeamRoster(
            team_id=team_id, timeout=600).get_normalized_dict()
        team_roster = team_roster_data['CommonTeamRoster']

        # Add each player in the roster to the team
        for player in team_roster:
            time.sleep(1)
            player_id = player['PLAYER_ID']
            player_name = player['PLAYER']
            player_number = player['NUM']  # Jersey number
            position = player['POSITION']
            how_acquired = player['HOW_ACQUIRED']
            season = player["SEASON"]

            # Player Data
            weight = player["WEIGHT"]
            born_date = player["BIRTH_DATE"]
            age = player["AGE"]
            exp = player["EXP"]
            if exp == "R":
                exp = 0

            school = player["SCHOOL"]

            # Check if player exists in the players table
            if Player.player_exists(player_id):
                # Add the player if they don't exist
                # Add position and how_aquired into roster, and position, age,
                # height, weight, draft into player

                # position = player.get('POSITION', 'Unknown')
                team_name = player['TeamID']

                # Player.update_player(player_id,player_name,player_number,
                # position,weight, born_date,age,exp,school)

                # print(f"Added new player: {player_name} (ID: {player_id})(
                # team_name(ID): {team_name})(position: {position})")
            else:
                print(f"PlayerID: {player_id} Name: {player_name} exists. Not "
                      "Updating For now \n ")
                Player.add_player(player_id, player_name, position, weight, born_date, age, exp,school, "Unknown")
                Player.add_player(
                    player_name,
                position,
                weight,
    born_date,
    player_id,
    age,
    exp,
    school,
    "Unknown",
)


            # Add player to the team's roster in the database
            team_obj.add_to_roster(player_id=player_id, player_name=player_name, player_number=player_number,position=position, how_acquired=how_acquired, season = season)

    # update_player_teams()
    print("All current NBA teams and their rosters have been successfully "
          "stored.")


def fetch_and_store_all_players_stats():
    """Fetch stats for all active players."""
    all_players = players.get_active_players()
    for player in all_players:
        fetch_and_store_player_stats(player["id"])
    print("All active player statistics have been successfully stored.")


def update_player_teams():
    """Update the team field in the players table using data from the roster ""
    ""table."""
    cur.execute('''
        UPDATE players
        SET team = teams.name
        FROM roster
        INNER JOIN teams ON roster.team_id = teams.team_id
        WHERE players.player_id = roster.player_id;
    ''')
    conn.commit()
    print("All currently rostered players have been listed for their correct team.")

def fetch_and_store_leaguedashplayer_stats():
    """Fetch and store player statistics for the last 10 seasons."""
    for season in range(2015, 2025):  # Last 10 seasons
        season_string = f"{season}-{str(season + 1)[-2:]}"
        print(f"Fetching stats for season {season_string}...")

        time.sleep(10)  # Pause to avoid rate limits
        try:
            stats = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season_string,
                timeout=300
            ).get_normalized_dict()['LeagueDashPlayerStats']

            for player_stat in stats:
                if not Player.player_exists(player_stat['PLAYER_ID']):
                    print("Player Is not in database, adding ", player_stat['PLAYER_NAME'])
                    Player.add_player(
                        player_id=player_stat['PLAYER_ID'],
                        name=player_stat['PLAYER_NAME'],
                        team="Unknown",
                        position="Unknown",
                        weight=0,
                        born_date="Unknown",
                        age= player_stat['AGE'],
                        exp =0,
                        school="Unkown"
                    )

                LeagueDashPlayerStats.add_stat(
                    player_id=player_stat['PLAYER_ID'],
                    player_name=player_stat['PLAYER_NAME'],
                    season =season_string,
                    team_id=player_stat['TEAM_ID'],
                    age=player_stat['AGE'],
                    gp=player_stat['GP'],
                    w=player_stat['W'],
                    l=player_stat['L'],
                    w_pct=player_stat['W_PCT'],
                    min=player_stat['MIN'],
                    fgm=player_stat['FGM'],
                    fga=player_stat['FGA'],
                    fg_pct=player_stat['FG_PCT'],
                    fg3m=player_stat['FG3M'],
                    fg3a=player_stat['FG3A'],
                    fg3_pct=player_stat['FG3_PCT'],
                    fta=player_stat['FTA'],
                    ft_pct=player_stat['FT_PCT'],
                    oreb=player_stat['OREB'],
                    dreb=player_stat['DREB'],
                    reb=player_stat['REB'],
                    ast=player_stat['AST'],
                    tov=player_stat['TOV'],
                    stl=player_stat['STL'],
                    blk=player_stat['BLK'],
                    blka=player_stat['BLKA'],
                    pf=player_stat['PF'],
                    pfd=player_stat['PFD'],
                    pts=player_stat['PTS'],
                    plus_minus=player_stat['PLUS_MINUS'],
                    nba_fantasy_points=player_stat['NBA_FANTASY_PTS'],
                    dd=player_stat['DD2'],
                    td3=player_stat['TD3'],
                    gp_rank=player_stat['GP_RANK'],
                    w_rank=player_stat['W_RANK'],
                    l_rank=player_stat['L_RANK'],
                    w_pct_rank=player_stat['W_PCT_RANK'],
                    min_rank=player_stat['MIN_RANK'],
                    fgm_rank=player_stat['FGM_RANK'],
                    fg_pct_rank=player_stat['FG_PCT_RANK'],
                    fg3m_rank=player_stat['FG3M_RANK'],
                    fg3a_rank=player_stat['FG3A_RANK'],
                    fg3_pct_rank=player_stat['FG3_PCT_RANK'],
                    ftm_rank=player_stat['FTM_RANK'],
                    fta_rank=player_stat['FTA_RANK'],
                    ft_pct_rank=player_stat['FT_PCT_RANK'],
                    oreb_rank=player_stat['OREB_RANK'],
                    dreb_rank=player_stat['DREB_RANK'],
                    reb_rank=player_stat['REB_RANK'],
                    ast_rank=player_stat['AST_RANK'],
                    tov_rank=player_stat['TOV_RANK'],
                    stl_rank=player_stat['STL_RANK'],
                    blk_rank=player_stat['BLK_RANK'],
                    blka_rank=player_stat['BLKA_RANK'],
                    pf_rank=player_stat['PF_RANK'],
                    pfd_rank=player_stat['PFD_RANK'],
                    pts_rank=player_stat['PTS_RANK'],
                    plus_minus_rank=player_stat['PLUS_MINUS_RANK'],
                    nba_fantasy_points_rank=player_stat['NBA_FANTASY_PTS_RANK'],
                    dd2_rank=player_stat['DD2_RANK'],
                    td3_rank=player_stat['TD3_RANK']
                )
            print(f"Stats for season {season_string} stored successfully.")
        except Exception as e:
            print(f"Error fetching stats for season {season_string}: {e}")
#great work today, work tomorrow on enhancing the static past stats we collect, and then make more ways to interact with
#the stats API
#teamid needs to be made consistent with nba api
#boxscore traditionalv3 for all games last season + this season
