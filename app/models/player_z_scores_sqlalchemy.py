"""
SQLAlchemy ORM model for player_z_scores table.

This module defines the PlayerZScoresORM model which stores Z-score statistics
for NBA players across various performance metrics.

Z-scores represent how many standard deviations a player's statistic is from
the league average, providing a normalized view of player performance.

Author: SQLAlchemy Migration Team
Date: 2025-11-20
"""

from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, Float, ForeignKey, Index, select
from sqlalchemy.orm import relationship, Session
from app.database import Base


class PlayerZScoresORM(Base):
    """
    SQLAlchemy ORM model for the player_z_scores table.
    
    Stores calculated Z-scores for various player statistics, showing
    how each player's performance compares to league averages.
    
    Attributes:
        player_id (int): Primary key, references players table
        pts_z_score (float): Points Z-score
        reb_z_score (float): Rebounds Z-score
        ast_z_score (float): Assists Z-score
        stl_z_score (float): Steals Z-score
        blk_z_score (float): Blocks Z-score
        tov_z_score (float): Turnovers Z-score (negative is better)
        fg3m_z_score (float): 3-Point Field Goals Made Z-score
        dd2_z_score (float): Double-Doubles Z-score
        fg_pct_z_score (float): Field Goal Percentage Z-score
        ft_pct_z_score (float): Free Throw Percentage Z-score
        fg3_pct_z_score (float): 3-Point Percentage Z-score
        
    Relationships:
        player: Reference to PlayerORM model
    """
    
    __tablename__ = 'player_z_scores'
    
    # Primary Key - references players table
    player_id = Column(Integer, ForeignKey('players.player_id', ondelete='CASCADE'), 
                      primary_key=True, nullable=False)
    
    # Z-Score columns (all FLOAT)
    pts_z_score = Column(Float, nullable=True)
    reb_z_score = Column(Float, nullable=True)
    ast_z_score = Column(Float, nullable=True)
    stl_z_score = Column(Float, nullable=True)
    blk_z_score = Column(Float, nullable=True)
    tov_z_score = Column(Float, nullable=True)
    fg3m_z_score = Column(Float, nullable=True)
    dd2_z_score = Column(Float, nullable=True)
    fg_pct_z_score = Column(Float, nullable=True)
    ft_pct_z_score = Column(Float, nullable=True)
    fg3_pct_z_score = Column(Float, nullable=True)
    
    # Relationship
    player = relationship("PlayerORM", backref="z_scores")
    
    # Table configuration
    __table_args__ = (
        Index('idx_player_z_scores_player_id', 'player_id'),
    )
    
    def __repr__(self) -> str:
        """String representation of PlayerZScoresORM."""
        return (
            f"<PlayerZScoresORM(player_id={self.player_id}, "
            f"pts_z={self.pts_z_score:.2f} if self.pts_z_score else 'N/A', "
            f"reb_z={self.reb_z_score:.2f} if self.reb_z_score else 'N/A', "
            f"ast_z={self.ast_z_score:.2f} if self.ast_z_score else 'N/A')>"
        )
    
    def to_dict(self, include_all: bool = True) -> Dict[str, Any]:
        """
        Convert the PlayerZScoresORM instance to a dictionary.
        
        Args:
            include_all: If True, includes all Z-score fields.
                        If False, only includes non-null Z-scores.
        
        Returns:
            Dictionary representation of the Z-scores
        """
        data = {
            'player_id': self.player_id,
            'pts_z_score': self.pts_z_score,
            'reb_z_score': self.reb_z_score,
            'ast_z_score': self.ast_z_score,
            'stl_z_score': self.stl_z_score,
            'blk_z_score': self.blk_z_score,
            'tov_z_score': self.tov_z_score,
            'fg3m_z_score': self.fg3m_z_score,
            'dd2_z_score': self.dd2_z_score,
            'fg_pct_z_score': self.fg_pct_z_score,
            'ft_pct_z_score': self.ft_pct_z_score,
            'fg3_pct_z_score': self.fg3_pct_z_score,
        }
        
        if not include_all:
            # Filter out None values
            data = {k: v for k, v in data.items() if v is not None or k == 'player_id'}
        
        return data
    
    def get_composite_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate a weighted composite Z-score for overall player value.
        
        Args:
            weights: Dictionary mapping stat names to weights.
                    Defaults to equal weights for positive stats.
                    
        Returns:
            Weighted composite Z-score
        """
        if weights is None:
            # Default weights - equal for positive stats, negative for turnovers
            weights = {
                'pts': 1.0,
                'reb': 1.0,
                'ast': 1.0,
                'stl': 1.0,
                'blk': 1.0,
                'tov': -1.0,  # Negative because turnovers are bad
                'fg3m': 0.5,
                'dd2': 0.5,
                'fg_pct': 0.75,
                'ft_pct': 0.5,
                'fg3_pct': 0.5,
            }
        
        z_scores = {
            'pts': self.pts_z_score,
            'reb': self.reb_z_score,
            'ast': self.ast_z_score,
            'stl': self.stl_z_score,
            'blk': self.blk_z_score,
            'tov': self.tov_z_score,
            'fg3m': self.fg3m_z_score,
            'dd2': self.dd2_z_score,
            'fg_pct': self.fg_pct_z_score,
            'ft_pct': self.ft_pct_z_score,
            'fg3_pct': self.fg3_pct_z_score,
        }
        
        total_weight = 0
        weighted_sum = 0
        
        for stat, weight in weights.items():
            z_score = z_scores.get(stat)
            if z_score is not None:
                weighted_sum += z_score * weight
                total_weight += abs(weight)
        
        if total_weight == 0:
            return 0.0
        
        return weighted_sum / total_weight
    
    # ==================== Class Methods for CRUD Operations ====================
    
    @classmethod
    def get_by_player(cls, session: Session, player_id: int) -> Optional['PlayerZScoresORM']:
        """
        Retrieve Z-scores for a specific player.
        
        Args:
            session: SQLAlchemy session
            player_id: Player ID to query
            
        Returns:
            PlayerZScoresORM instance or None if not found
        """
        return session.query(cls).filter(cls.player_id == player_id).first()
    
    @classmethod
    def get_all(cls, session: Session, limit: Optional[int] = None) -> List['PlayerZScoresORM']:
        """
        Retrieve all player Z-scores.
        
        Args:
            session: SQLAlchemy session
            limit: Optional limit on number of results
            
        Returns:
            List of PlayerZScoresORM instances
        """
        query = session.query(cls)
        if limit:
            query = query.limit(limit)
        return query.all()
    
    @classmethod
    def get_top_players(cls, session: Session, stat: str, limit: int = 10) -> List['PlayerZScoresORM']:
        """
        Get top players by a specific Z-score stat.
        
        Args:
            session: SQLAlchemy session
            stat: Stat name (e.g., 'pts', 'reb', 'ast')
            limit: Number of top players to return
            
        Returns:
            List of PlayerZScoresORM instances sorted by the stat
        """
        stat_column = f"{stat}_z_score"
        if not hasattr(cls, stat_column):
            raise ValueError(f"Invalid stat: {stat}")
        
        column = getattr(cls, stat_column)
        return (
            session.query(cls)
            .filter(column.isnot(None))
            .order_by(column.desc())
            .limit(limit)
            .all()
        )
    
    @classmethod
    def create(cls, session: Session, player_id: int, **z_scores) -> 'PlayerZScoresORM':
        """
        Create or update Z-scores for a player (upsert operation).
        
        Args:
            session: SQLAlchemy session
            player_id: Player ID
            **z_scores: Keyword arguments for Z-score values
            
        Returns:
            PlayerZScoresORM instance
        """
        # Check if record exists
        existing = cls.get_by_player(session, player_id)
        
        if existing:
            # Update existing record
            for key, value in z_scores.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            return existing
        else:
            # Create new record
            new_z_scores = cls(player_id=player_id, **z_scores)
            session.add(new_z_scores)
            return new_z_scores
    
    @classmethod
    def bulk_upsert(cls, session: Session, z_scores_list: List[Dict[str, Any]]) -> int:
        """
        Bulk insert or update Z-scores for multiple players.
        
        Args:
            session: SQLAlchemy session
            z_scores_list: List of dictionaries containing player_id and Z-scores
            
        Returns:
            Number of records processed
        """
        count = 0
        for z_scores_data in z_scores_list:
            player_id = z_scores_data.pop('player_id')
            cls.create(session, player_id, **z_scores_data)
            count += 1
        
        return count
    
    @classmethod
    def update(cls, session: Session, player_id: int, **updates) -> Optional['PlayerZScoresORM']:
        """
        Update Z-scores for a specific player.
        
        Args:
            session: SQLAlchemy session
            player_id: Player ID to update
            **updates: Keyword arguments for fields to update
            
        Returns:
            Updated PlayerZScoresORM instance or None if not found
        """
        z_scores = cls.get_by_player(session, player_id)
        if z_scores:
            for key, value in updates.items():
                if hasattr(z_scores, key):
                    setattr(z_scores, key, value)
        return z_scores
    
    @classmethod
    def delete(cls, session: Session, player_id: int) -> bool:
        """
        Delete Z-scores for a specific player.
        
        Args:
            session: SQLAlchemy session
            player_id: Player ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        z_scores = cls.get_by_player(session, player_id)
        if z_scores:
            session.delete(z_scores)
            return True
        return False

