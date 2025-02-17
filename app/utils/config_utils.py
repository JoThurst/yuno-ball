"""
Module: config_utils
This module provides configuration utilities for the NBA Sports Analytics application.
Sets up global logging configurations by reading environment-specific variables for the log level and log file.
Logging configuration includes a stream handler and a file handler to enable real-time and file-based logging.
Defines a global constant for API rate limiting to manage the interval between API calls.
"""

import os
import logging

# Global Logging Configuration
LOG_LEVEL: str = os.getenv(key="LOG_LEVEL", default="INFO").upper()
LOG_FILE: str = os.getenv(key="LOG_FILE", default="nba_data_module.log")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(filename=LOG_FILE)],
)

LOGGER: logging.Logger = logging.getLogger(name=__name__)

# Global Rate-Limiting for API Calls
API_RATE_LIMIT = 0.6  # Seconds to sleep between API calls
