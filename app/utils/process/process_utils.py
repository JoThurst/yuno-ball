def normalize_row(row, headers):
    """Helper function to convert a row and headers into a dictionary."""
    return dict(zip(headers, row))

def calculate_averages(game_logs):
    """Calculate averages for points, rebounds, assists, etc."""
    total_games = len(game_logs)
    if total_games == 0:
        return {}

    return {
        "points_avg": sum(log["points"] for log in game_logs) / total_games,
        "rebounds_avg": sum(log["rebounds"] for log in game_logs) / total_games,
        "assists_avg": sum(log["assists"] for log in game_logs) / total_games,
        "steals_avg": sum(log["steals"] for log in game_logs) / total_games,
        "blocks_avg": sum(log["blocks"] for log in game_logs) / total_games,
        "turnovers_avg": sum(log["turnovers"] for log in game_logs) / total_games,
    }