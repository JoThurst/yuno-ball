-- Enable pg_trgm extension for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Players table indexes
CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);
CREATE INDEX IF NOT EXISTS idx_players_seasons ON players USING gin(available_seasons gin_trgm_ops);

-- Statistics table indexes
CREATE INDEX IF NOT EXISTS idx_statistics_season ON statistics(season_year);
CREATE INDEX IF NOT EXISTS idx_statistics_player_season ON statistics(player_id, season_year);
CREATE INDEX IF NOT EXISTS idx_statistics_points ON statistics(points DESC);
CREATE INDEX IF NOT EXISTS idx_statistics_rebounds ON statistics(rebounds DESC);
CREATE INDEX IF NOT EXISTS idx_statistics_assists ON statistics(assists DESC);

-- Game Schedule table indexes
CREATE INDEX IF NOT EXISTS idx_game_schedule_date ON game_schedule(game_date);
CREATE INDEX IF NOT EXISTS idx_game_schedule_season ON game_schedule(season);
CREATE INDEX IF NOT EXISTS idx_game_schedule_team_result ON game_schedule(team_id, result);

-- Team Game Stats table indexes
CREATE INDEX IF NOT EXISTS idx_team_game_stats_date ON team_game_stats(game_date);
CREATE INDEX IF NOT EXISTS idx_team_game_stats_season ON team_game_stats(season);
CREATE INDEX IF NOT EXISTS idx_team_game_stats_points ON team_game_stats(pts DESC);

-- Player Game Logs table indexes
CREATE INDEX IF NOT EXISTS idx_gamelogs_player_season ON gamelogs(player_id, season);
CREATE INDEX IF NOT EXISTS idx_gamelogs_points ON gamelogs(points DESC);
CREATE INDEX IF NOT EXISTS idx_gamelogs_minutes ON gamelogs(minutes_played);

-- League Dash Player Stats table indexes
CREATE INDEX IF NOT EXISTS idx_leaguedash_season ON leaguedashplayerstats(season);
CREATE INDEX IF NOT EXISTS idx_leaguedash_points ON leaguedashplayerstats(pts DESC);
CREATE INDEX IF NOT EXISTS idx_leaguedash_fantasy ON leaguedashplayerstats(nba_fantasy_pts DESC);

-- Analyze tables to update statistics
ANALYZE players;
ANALYZE statistics;
ANALYZE game_schedule;
ANALYZE team_game_stats;
ANALYZE gamelogs;
ANALYZE leaguedashplayerstats;

-- Optimize tables after cleanup
ANALYZE players;
ANALYZE statistics;
ANALYZE game_schedule;
ANALYZE team_game_stats;
ANALYZE player_game_log;
ANALYZE league_dash_player_stats;

-- Create or update indexes for better query performance
-- Players table
CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);

-- Statistics table
CREATE INDEX IF NOT EXISTS idx_statistics_player_game ON statistics(player_id, game_id);
CREATE INDEX IF NOT EXISTS idx_statistics_game_date ON statistics(game_date);
CREATE INDEX IF NOT EXISTS idx_statistics_team ON statistics(team_id);

-- Game schedule
CREATE INDEX IF NOT EXISTS idx_game_schedule_date ON game_schedule(game_date);
CREATE INDEX IF NOT EXISTS idx_game_schedule_teams ON game_schedule(home_team_id, away_team_id);

-- Team game stats
CREATE INDEX IF NOT EXISTS idx_team_game_stats_game ON team_game_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_team_game_stats_team_game ON team_game_stats(team_id, game_id);
CREATE INDEX IF NOT EXISTS idx_team_game_stats_date ON team_game_stats(game_date);

-- Player game log
CREATE INDEX IF NOT EXISTS idx_player_game_log_player ON player_game_log(player_id);
CREATE INDEX IF NOT EXISTS idx_player_game_log_game ON player_game_log(game_id);
CREATE INDEX IF NOT EXISTS idx_player_game_log_date ON player_game_log(game_date);

-- League dash player stats
CREATE INDEX IF NOT EXISTS idx_league_dash_player_stats_player ON league_dash_player_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_league_dash_player_stats_season ON league_dash_player_stats(season);

-- Add constraints to ensure data integrity
ALTER TABLE players
    ADD CONSTRAINT IF NOT EXISTS players_team_id_fk
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL;

ALTER TABLE statistics
    ADD CONSTRAINT IF NOT EXISTS statistics_player_id_fk
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    ADD CONSTRAINT IF NOT EXISTS statistics_game_id_fk
    FOREIGN KEY (game_id) REFERENCES game_schedule(id) ON DELETE CASCADE;

ALTER TABLE team_game_stats
    ADD CONSTRAINT IF NOT EXISTS team_game_stats_team_id_fk
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    ADD CONSTRAINT IF NOT EXISTS team_game_stats_game_id_fk
    FOREIGN KEY (game_id) REFERENCES game_schedule(id) ON DELETE CASCADE;

ALTER TABLE player_game_log
    ADD CONSTRAINT IF NOT EXISTS player_game_log_player_id_fk
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    ADD CONSTRAINT IF NOT EXISTS player_game_log_game_id_fk
    FOREIGN KEY (game_id) REFERENCES game_schedule(id) ON DELETE CASCADE;

-- Add check constraints for data validation
ALTER TABLE statistics
    ADD CONSTRAINT IF NOT EXISTS check_statistics_positive
    CHECK (
        minutes >= 0 AND
        points >= 0 AND
        rebounds >= 0 AND
        assists >= 0
    );

ALTER TABLE team_game_stats
    ADD CONSTRAINT IF NOT EXISTS check_team_game_stats_positive
    CHECK (
        team_score >= 0 AND
        opponent_score >= 0
    );

-- Vacuum analyze to optimize storage and update statistics
VACUUM ANALYZE; 