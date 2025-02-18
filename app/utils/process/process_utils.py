"""
Module for processing NBA game logs and computing statistical averages.
This module provides utility functions for transforming rows of data into dictionaries and
for calculating average statistics from a list of game logs.
The two primary functions included are:
        normalize_row(row, headers):
            Converts a list of values (row) and its corresponding list of headers into a dictionary,
            effectively mapping each header to its corresponding value in the row.
        calculate_averages(game_logs):
            Calculates the average statistics (points, rebounds, assists, steals, blocks, turnovers)
            from a collection of game logs. If no game logs are provided, it returns an empty dictionary.
"""


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
