"""
Fetcher for game odds data from NBA Live Odds endpoint.

Uses BaseFetcher patterns for retry/rate limiting.
Simpler than injury fetcher since there's only one endpoint call per day.

Created: December 2, 2025
Part of: Phase 1.6 - Game Odds Ingestion
"""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional, Tuple, Any

from requests.exceptions import Timeout, RequestException

from app.models.game_odds_sqlalchemy import GameOddsORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.database import get_db_context

from .base_fetcher import BaseFetcher, rate_limiter
from .api_utils import create_api_endpoint, get_live_headers

# NBA API imports
try:
    from nba_api.live.nba.endpoints import odds
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False

logger = logging.getLogger(__name__)


class OddsFetcher(BaseFetcher):
    """
    Fetches game odds from NBA's live odds endpoint.
    
    The odds endpoint returns all games for today in a single call,
    so this is much simpler than the injury fetcher.
    """
    
    def __init__(self):
        """Initialize the fetcher."""
        super().__init__()
        if not NBA_API_AVAILABLE:
            logger.warning("nba_api.live not available - odds fetching disabled")

    @staticmethod
    def _current_slate_games(target_date, season: str) -> Dict[str, Tuple[int, int]]:
        """Return exact home/away IDs for canonical games on the Eastern slate."""
        with get_db_context() as db:
            rows = [row for row in GameScheduleORM.get_by_date(target_date, db=db)
                    if row['season'] == season]
        by_game: Dict[str, List[Dict]] = {}
        for row in rows:
            by_game.setdefault(row['game_id'], []).append(row)
        games = {}
        for game_id, pair in by_game.items():
            home = [row for row in pair if row['home_or_away'] == 'H']
            away = [row for row in pair if row['home_or_away'] == 'A']
            if (len(pair) != 2 or len(home) != 1 or len(away) != 1
                    or home[0]['opponent_team_id'] != away[0]['team_id']
                    or away[0]['opponent_team_id'] != home[0]['team_id']):
                raise RuntimeError(f"Incomplete canonical odds slate pair for {game_id}")
            games[game_id] = (home[0]['team_id'], away[0]['team_id'])
        return games
    
    def _fetch_raw_odds(self) -> Optional[List[Dict]]:
        """
        Fetch raw odds data from NBA API.
        
        Returns:
            List of game odds data or None on failure
        """
        if not NBA_API_AVAILABLE:
            return None
        
        def _api_call():
            rate_limiter.wait_if_needed()
            odds_data = create_api_endpoint(
                odds.Odds,
                proxy=self.api_config.get("proxy"),
                headers=get_live_headers(self.api_config.get("headers")),
                timeout=self.api_config.get("timeout", self.default_timeout),
            )
            return odds_data.games.get_dict()
        
        try:
            return self._handle_api_call(_api_call)
        except (Timeout, RequestException) as exc:
            logger.error(f"Error fetching odds: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Unexpected error fetching odds: {exc}")
            return None
    
    def _parse_odds_data(
        self,
        games_data: List[Dict],
        season: str,
        target_date: date
    ) -> List[Dict]:
        """
        Parse raw odds data into structured records.
        
        Args:
            games_data: Raw games data from NBA API
            season: Season string
            target_date: Date for these odds
            
        Returns:
            List of structured odds records
        """
        records = []
        
        for game in games_data:
            game_id = game.get('gameId')
            home_team_id = int(game.get('homeTeamId', 0))
            away_team_id = int(game.get('awayTeamId', 0))
            
            if not game_id or not home_team_id or not away_team_id:
                continue
            
            markets = game.get('markets', [])
            books_data: Dict[str, Dict[str, Any]] = {}
            
            for market in markets:
                market_name = market.get('name')
                books = market.get('books', [])
                
                for book in books:
                    book_id = book.get('id')
                    book_name = book.get('name')
                    country_code = book.get('countryCode')
                    book_url = book.get('url')
                    
                    if not book_id:
                        continue
                    
                    if book_id not in books_data:
                        books_data[book_id] = {
                            'game_id': game_id,
                            'game_date': target_date,
                            'season': season,
                            'home_team_id': home_team_id,
                            'away_team_id': away_team_id,
                            'sportsbook_id': book_id,
                            'sportsbook_name': book_name,
                            'country_code': country_code,
                            'sportsbook_url': book_url,
                            'raw_data': game
                        }
                    
                    outcomes = book.get('outcomes', [])
                    
                    if market_name == '2way':
                        # Moneyline odds
                        for outcome in outcomes:
                            outcome_type = outcome.get('type')
                            curr = float(outcome.get('odds', 0)) if outcome.get('odds') else None
                            opening = float(outcome.get('opening_odds', 0)) if outcome.get('opening_odds') else None
                            trend = outcome.get('odds_trend')
                            
                            if outcome_type == 'home':
                                books_data[book_id]['home_ml_odds'] = curr
                                books_data[book_id]['home_ml_opening'] = opening
                                books_data[book_id]['home_ml_trend'] = trend
                            elif outcome_type == 'away':
                                books_data[book_id]['away_ml_odds'] = curr
                                books_data[book_id]['away_ml_opening'] = opening
                                books_data[book_id]['away_ml_trend'] = trend
                    
                    elif market_name == 'spread':
                        # Spread odds
                        for outcome in outcomes:
                            outcome_type = outcome.get('type')
                            spread = float(outcome['spread']) if outcome.get('spread') is not None else None
                            opening_spread = float(outcome['opening_spread']) if outcome.get('opening_spread') is not None else None
                            spread_odds = float(outcome.get('odds', 0)) if outcome.get('odds') else None
                            
                            if outcome_type == 'home':
                                books_data[book_id]['home_spread'] = spread
                                books_data[book_id]['home_spread_opening'] = opening_spread
                                books_data[book_id]['spread_home_odds'] = spread_odds
                            elif outcome_type == 'away':
                                books_data[book_id]['away_spread'] = spread
                                books_data[book_id]['away_spread_opening'] = opening_spread
                                books_data[book_id]['spread_away_odds'] = spread_odds
            
            records.extend(books_data.values())
        
        return records
    
    def fetch_todays_odds(
        self,
        season: str,
        country_filter: str = 'US'
    ) -> Tuple[int, int]:
        """
        Fetch and store odds for today's games.
        
        Args:
            season: Season string
            country_filter: Country code to filter sportsbooks (default: 'US')
            
        Returns:
            Tuple of (games_with_odds, records_stored)
        """
        if not NBA_API_AVAILABLE:
            raise RuntimeError("nba_api.live not available - cannot fetch odds")
        
        today = datetime.now(ZoneInfo('America/New_York')).date()
        logger.info(f"Fetching odds for {today}")
        slate_games = self._current_slate_games(today, season)
        if not slate_games:
            logger.info("No canonical games on today's Eastern slate")
            return 0, 0
        
        # Fetch raw odds
        games_data = self._fetch_raw_odds()
        
        if games_data is None:
            raise RuntimeError("Live odds source fetch failed")
        
        if not games_data:
            raise RuntimeError("Live odds source returned no games for a scheduled slate")

        current_games = []
        seen_ids = set()
        for game in games_data:
            game_id = str(game.get('gameId', ''))
            if game_id not in slate_games:
                continue
            if game_id in seen_ids:
                raise RuntimeError(f"Duplicate Live odds game {game_id}")
            seen_ids.add(game_id)
            home_id, away_id = slate_games[game_id]
            if (str(game.get('homeTeamId')) != str(home_id)
                    or str(game.get('awayTeamId')) != str(away_id)):
                raise RuntimeError(f"Live odds team identity differs from canonical slate for {game_id}")
            current_games.append(game)
        if not current_games:
            raise RuntimeError("Live odds source has no games from today's canonical slate")
        
        logger.info(f"Found {len(current_games)}/{len(slate_games)} current-slate games in Live odds feed")
        
        # Parse into structured records
        records = self._parse_odds_data(current_games, season, today)
        
        if not records:
            raise RuntimeError("No current-slate Live odds records parsed")
        
        # Filter by country
        if country_filter:
            records = [r for r in records if r.get('country_code') == country_filter]
            logger.info(f"Filtered to {len(records)} {country_filter} sportsbook records")
        records = [r for r in records if (
            r.get('home_ml_odds') is not None and r.get('away_ml_odds') is not None
        ) or (
            r.get('home_spread') is not None and r.get('away_spread') is not None
            and r.get('spread_home_odds') is not None and r.get('spread_away_odds') is not None
        )]
        if not records:
            raise RuntimeError("No complete current-slate sportsbook pairs for requested country")
        
        # Store using bulk upsert
        try:
            with get_db_context() as db:
                count = GameOddsORM.bulk_create(records, db=db)
                db.commit()
            
            unique_games = len(set(r['game_id'] for r in records))
            logger.info(f"Stored {count} odds records for {unique_games} games")
            return unique_games, count
            
        except Exception as e:
            raise RuntimeError(f"Could not persist current-slate Live odds: {e}") from e
    
    def get_game_odds_summary(
        self,
        game_id: str
    ) -> Dict[str, Any]:
        """
        Get odds summary for a specific game.
        
        Args:
            game_id: Game ID
            
        Returns:
            Dictionary with odds summary
        """
        with get_db_context() as db:
            odds_list = GameOddsORM.get_by_game(game_id, db=db)
            
            if not odds_list:
                return {'game_id': game_id, 'has_odds': False}
            
            consensus = GameOddsORM.get_consensus_odds(game_id, db=db)
            
            by_book = []
            for o in odds_list:
                by_book.append({
                    'book': o.sportsbook_name,
                    'home_ml': o.get_home_ml_american(),
                    'away_ml': o.get_away_ml_american(),
                    'spread': o.home_spread,
                    'home_ml_trend': o.home_ml_trend,
                    'away_ml_trend': o.away_ml_trend
                })
            
            return {
                'game_id': game_id,
                'has_odds': True,
                'game_date': odds_list[0].game_date.isoformat() if odds_list else None,
                'home_team_id': odds_list[0].home_team_id if odds_list else None,
                'away_team_id': odds_list[0].away_team_id if odds_list else None,
                'consensus': consensus,
                'by_book': by_book
            }

