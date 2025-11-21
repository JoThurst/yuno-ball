"""SQLAlchemy ORM model for PlayerGameLog.

This module provides the GameLogORM class which represents individual game
performance records for players in the database using SQLAlchemy ORM.

Created: November 20, 2025
Part of: SQLAlchemy migration (Day 2 continued)
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, VARCHAR, DateTime, ForeignKey, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Session, relationship

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class GameLogORM(Base):
    """SQLAlchemy ORM model for player game logs.
    
    This model represents a player's performance in a single game.
    It maps to the 'gamelogs' table in the public schema.
    
    Attributes:
        player_id: Reference to the player
        game_id: Unique game identifier
        team_id: Reference to the team
        points: Points scored in the game
        assists: Assists in the game
        rebounds: Rebounds in the game
        steals: Steals in the game
        blocks: Blocks in the game
        turnovers: Turnovers in the game
        minutes_played: Minutes played (format: MM:SS)
        season: Season identifier (e.g., "2024-25")
        created_at: Record creation timestamp
        updated_at: Record update timestamp
        
    Relationships:
        player: The player this game log belongs to
        team: The team the player played for
    """
    
    __tablename__ = 'gamelogs'
    __table_args__ = (
        PrimaryKeyConstraint('player_id', 'game_id'),
        Index('idx_gamelogs_player_id', 'player_id'),
        Index('idx_gamelogs_game_id', 'game_id'),
        Index('idx_gamelogs_team_id', 'team_id'),
        Index('idx_gamelogs_season', 'season'),
        Index('idx_gamelogs_player_season', 'player_id', 'season'),
        Index('idx_gamelogs_points', 'points'),
        Index('idx_gamelogs_minutes', 'minutes_played'),
        Index('gamelogs_player_game_idx', 'player_id', 'game_id'),
        Index('gamelogs_season_idx', 'season'),
        Index('gamelogs_game_idx', 'game_id'),
    )
    
    # Composite Primary Key
    player_id = Column(BigInteger, nullable=False)
    game_id = Column(VARCHAR, nullable=False)
    
    # Foreign Keys
    team_id = Column(BigInteger, ForeignKey('teams.team_id'), nullable=False)
    
    # Game Statistics
    points = Column(Integer, nullable=True, default=0)
    assists = Column(Integer, nullable=True, default=0)
    rebounds = Column(Integer, nullable=True, default=0)
    steals = Column(Integer, nullable=True, default=0)
    blocks = Column(Integer, nullable=True, default=0)
    turnovers = Column(Integer, nullable=True, default=0)
    minutes_played = Column(VARCHAR, nullable=True, default='00:00')
    season = Column(VARCHAR, nullable=False)
    
    # Note: created_at and updated_at columns exist in table definition
    # but not in actual database table, so commenting out for now
    # created_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    # updated_at = Column(DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships (when models have relationships defined)
    # player = relationship("PlayerORM", back_populates="gamelogs")
    # team = relationship("TeamORM")
    
    def __repr__(self) -> str:
        """String representation of the game log."""
        return f"<GameLogORM(player_id={self.player_id}, game_id='{self.game_id}', pts={self.points})>"
    
    def to_dict(self) -> dict:
        """Convert game log object to dictionary.
        
        Returns:
            dict: Dictionary representation of the game log
        """
        return {
            'player_id': self.player_id,
            'game_id': self.game_id,
            'team_id': self.team_id,
            'points': self.points,
            'assists': self.assists,
            'rebounds': self.rebounds,
            'steals': self.steals,
            'blocks': self.blocks,
            'turnovers': self.turnovers,
            'minutes_played': self.minutes_played,
            'season': self.season
        }
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_player(cls, player_id: int, db: Optional[Session] = None) -> List['GameLogORM']:
        """Get all game logs for a player, ordered by game_id desc.
        
        Args:
            player_id: The player's unique identifier
            db: Optional database session
            
        Returns:
            List of GameLogORM objects
        """
        if db:
            return db.query(cls).filter(
                cls.player_id == player_id
            ).order_by(cls.game_id.desc()).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.player_id == player_id
            ).order_by(cls.game_id.desc()).all()
    
    @classmethod
    def get_by_player_and_season(cls, player_id: int, season: str, db: Optional[Session] = None) -> List['GameLogORM']:
        """Get game logs for a player in a specific season.
        
        Args:
            player_id: The player's unique identifier
            season: Season identifier (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            List of GameLogORM objects
        """
        if db:
            return db.query(cls).filter(
                cls.player_id == player_id,
                cls.season == season
            ).order_by(cls.game_id.desc()).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.player_id == player_id,
                cls.season == season
            ).order_by(cls.game_id.desc()).all()
    
    @classmethod
    def get_by_team(cls, team_id: int, db: Optional[Session] = None) -> List['GameLogORM']:
        """Get all game logs for a team.
        
        Args:
            team_id: The team's unique identifier
            db: Optional database session
            
        Returns:
            List of GameLogORM objects
        """
        if db:
            return db.query(cls).filter(
                cls.team_id == team_id
            ).order_by(cls.game_id.desc()).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.team_id == team_id
            ).order_by(cls.game_id.desc()).all()
    
    @classmethod
    def get_by_game(cls, game_id: str, db: Optional[Session] = None) -> List['GameLogORM']:
        """Get all game logs for a specific game.
        
        Args:
            game_id: The game's unique identifier
            db: Optional database session
            
        Returns:
            List of GameLogORM objects
        """
        if db:
            return db.query(cls).filter(cls.game_id == game_id).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.game_id == game_id).all()
    
    @classmethod
    def get_single_log(cls, player_id: int, game_id: str, db: Optional[Session] = None) -> Optional['GameLogORM']:
        """Get a specific game log by player and game.
        
        Args:
            player_id: The player's unique identifier
            game_id: The game's unique identifier
            db: Optional database session
            
        Returns:
            GameLogORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(
                cls.player_id == player_id,
                cls.game_id == game_id
            ).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.player_id == player_id,
                cls.game_id == game_id
            ).first()
    
    @classmethod
    def get_last_n_games(cls, player_id: int, n: int = 10, db: Optional[Session] = None) -> List['GameLogORM']:
        """Get the last N games for a player.
        
        Args:
            player_id: The player's unique identifier
            n: Number of games to return
            db: Optional database session
            
        Returns:
            List of GameLogORM objects
        """
        if db:
            return db.query(cls).filter(
                cls.player_id == player_id
            ).order_by(cls.game_id.desc()).limit(n).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.player_id == player_id
            ).order_by(cls.game_id.desc()).limit(n).all()
    
    @classmethod
    def get_best_game(cls, player_id: int, stat: str = 'points', db: Optional[Session] = None) -> Optional['GameLogORM']:
        """Get the best game for a player by a specific stat.
        
        Args:
            player_id: The player's unique identifier
            stat: Stat to sort by (points, assists, rebounds, etc.)
            db: Optional database session
            
        Returns:
            GameLogORM object if found, None otherwise
        """
        stat_column = getattr(cls, stat, cls.points)
        
        if db:
            return db.query(cls).filter(
                cls.player_id == player_id
            ).order_by(stat_column.desc()).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.player_id == player_id
            ).order_by(stat_column.desc()).first()
    
    @classmethod
    def has_logs_for_season(cls, player_id: int, season: str, db: Optional[Session] = None) -> bool:
        """Check if game logs exist for a player in a specific season.
        
        Args:
            player_id: The player's unique identifier
            season: Season identifier
            db: Optional database session
            
        Returns:
            True if logs exist, False otherwise
        """
        if db:
            return db.query(cls).filter(
                cls.player_id == player_id,
                cls.season == season
            ).count() > 0
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.player_id == player_id,
                cls.season == season
            ).count() > 0
    
    # ==================== CRUD Operations ====================
    
    @classmethod
    def create(cls,
               player_id: int,
               game_id: str,
               team_id: int,
               season: str,
               points: int = 0,
               assists: int = 0,
               rebounds: int = 0,
               steals: int = 0,
               blocks: int = 0,
               turnovers: int = 0,
               minutes_played: str = '00:00',
               db: Optional[Session] = None) -> 'GameLogORM':
        """Create new game log or update if exists (upsert).
        
        Args:
            player_id: Player's unique identifier
            game_id: Game's unique identifier
            team_id: Team's unique identifier
            season: Season identifier
            points: Points scored
            assists: Assists
            rebounds: Rebounds
            steals: Steals
            blocks: Blocks
            turnovers: Turnovers
            minutes_played: Minutes played
            db: Optional database session
            
        Returns:
            GameLogORM: The created or updated game log object
        """
        def _create(session: Session) -> 'GameLogORM':
            # Check if game log exists
            game_log = session.query(cls).filter(
                cls.player_id == player_id,
                cls.game_id == game_id
            ).first()
            
            if game_log:
                # Update existing game log
                game_log.team_id = team_id
                game_log.season = season
                game_log.points = points
                game_log.assists = assists
                game_log.rebounds = rebounds
                game_log.steals = steals
                game_log.blocks = blocks
                game_log.turnovers = turnovers
                game_log.minutes_played = minutes_played
                logger.info(f"Updated game log for player {player_id}, game {game_id}")
            else:
                # Create new game log
                game_log = cls(
                    player_id=player_id,
                    game_id=game_id,
                    team_id=team_id,
                    season=season,
                    points=points,
                    assists=assists,
                    rebounds=rebounds,
                    steals=steals,
                    blocks=blocks,
                    turnovers=turnovers,
                    minutes_played=minutes_played
                )
                session.add(game_log)
                logger.info(f"Created game log for player {player_id}, game {game_id}")
            
            session.flush()
            return game_log
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            game_log = _create(session)
            session.commit()
            return game_log
    
    @classmethod
    def bulk_create(cls, game_logs: List[dict], db: Optional[Session] = None) -> int:
        """Bulk insert game logs (upsert).
        
        Args:
            game_logs: List of dictionaries with game log data
            db: Optional database session
            
        Returns:
            Number of game logs created/updated
        """
        def _bulk_create(session: Session) -> int:
            from sqlalchemy.exc import IntegrityError
            count = 0
            skipped = 0
            
            # Process each log individually to handle errors gracefully
            for log_data in game_logs:
                try:
                    # Create or update the game log
                    # Note: create() does its own flush, so we need to handle errors per item
                    cls.create(
                        player_id=log_data['player_id'],
                        game_id=log_data['game_id'],
                        team_id=log_data['team_id'],
                        season=log_data['season'],
                        points=log_data.get('points', 0),
                        assists=log_data.get('assists', 0),
                        rebounds=log_data.get('rebounds', 0),
                        steals=log_data.get('steals', 0),
                        blocks=log_data.get('blocks', 0),
                        turnovers=log_data.get('turnovers', 0),
                        minutes_played=log_data.get('minutes_played', '00:00'),
                        db=session
                    )
                    count += 1
                except IntegrityError as e:
                    # Handle foreign key violations or duplicate key errors gracefully
                    session.rollback()  # Rollback this specific item's transaction
                    if 'foreign key' in str(e).lower() or 'gamelogs_team_id_fkey' in str(e):
                        skipped += 1
                        logger.debug(f"Skipping gamelog with invalid team_id {log_data.get('team_id')} "
                                   f"(player {log_data.get('player_id')}, game {log_data.get('game_id')})")
                    else:
                        skipped += 1
                        logger.warning(f"Skipping gamelog due to integrity error "
                                     f"(player {log_data.get('player_id')}, game {log_data.get('game_id')}): {e}")
                except Exception as e:
                    # Log other errors but continue with remaining logs
                    session.rollback()  # Rollback this specific item's transaction
                    skipped += 1
                    logger.error(f"Error creating gamelog (player {log_data.get('player_id')}, "
                               f"game {log_data.get('game_id')}): {e}")
            
            # Final flush for any remaining pending changes
            try:
                session.flush()
                if skipped > 0:
                    logger.info(f"Bulk created/updated {count} game logs, skipped {skipped} due to errors")
                else:
                    logger.info(f"Bulk created/updated {count} game logs")
            except Exception as e:
                logger.error(f"Error flushing game logs: {e}")
                session.rollback()
                raise
            
            return count
        
        if db:
            return _bulk_create(db)
        
        with get_db_context() as session:
            count = _bulk_create(session)
            session.commit()
            return count
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this game log from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.info(f"Deleted game log: player {self.player_id}, game {self.game_id}")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()


# Backward compatibility function
def get_gamelog_model():
    """Get the appropriate game log model (SQLAlchemy version).
    
    Returns:
        GameLogORM class
    """
    return GameLogORM

