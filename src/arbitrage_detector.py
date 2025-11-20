"""Arbitrage betting opportunity detector."""
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from itertools import combinations

import pandas as pd
from sqlalchemy import Column, String, Float, DateTime, JSON, Boolean

from src.db import Base, handle_db_errors
from src.logging_config import get_logger
from src.config import settings
from src.utils import utc_now

logger = get_logger(__name__)


class ArbitrageSignal(Base):
    """Store detected arbitrage opportunities."""
    
    __tablename__ = "arbitrage_signals"
    
    id = Column(String, primary_key=True)
    market_id = Column(String, index=True, nullable=False)
    arbitrage_type = Column(String, nullable=False)  # classic/middle/dual
    profit_margin = Column(Float, nullable=False)
    total_stake = Column(Float, nullable=False)
    legs = Column(JSON, nullable=False)  # List of bet legs
    optimal_stakes = Column(JSON, nullable=False)  # Stake distribution
    is_active = Column(Boolean, default=True)
    detected_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<ArbitrageSignal(market={self.market_id}, profit={self.profit_margin:.2%})>"


class ArbitrageDetector:
    """Detect arbitrage opportunities across multiple bookmakers."""
    
    def __init__(self):
        self.enabled = settings.ARBITRAGE_ENABLED
        self.min_profit_margin = settings.ARBITRAGE_MIN_PROFIT_MARGIN
        self.max_stake = settings.ARBITRAGE_MAX_STAKE
        
        logger.info(
            f"ArbitrageDetector initialized (enabled={self.enabled}, "
            f"min_profit={self.min_profit_margin:.2%})"
        )
    
    def detect_opportunities(self, odds_data: pd.DataFrame) -> List[Dict]:
        """Detect arbitrage opportunities from odds data.
        
        Args:
            odds_data: DataFrame with columns:
                - market_id
                - bookmaker
                - home_odds
                - away_odds
                - draw_odds (optional)
        
        Returns:
            List of arbitrage opportunities
        """
        if not self.enabled:
            logger.debug("Arbitrage detection disabled")
            return []
        
        opportunities = []
        
        try:
            # Group by market
            for market_id, market_odds in odds_data.groupby('market_id'):
                # Classic arbitrage (3-way markets)
                if 'draw_odds' in market_odds.columns:
                    arb = self._detect_classic_arbitrage(market_id, market_odds)
                    if arb:
                        opportunities.append(arb)
                
                # Two-way arbitrage
                two_way_arb = self._detect_two_way_arbitrage(market_id, market_odds)
                if two_way_arb:
                    opportunities.append(two_way_arb)
            
            logger.info(f"Detected {len(opportunities)} arbitrage opportunities")
            
            # Save to database
            if opportunities:
                self._save_opportunities(opportunities)
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error detecting arbitrage: {e}", exc_info=True)
            return []
    
    def _detect_classic_arbitrage(self, market_id: str, odds: pd.DataFrame) -> Optional[Dict]:
        """Detect classic 3-way arbitrage (home/draw/away)."""
        try:
            # Get best odds for each outcome
            best_home = odds['home_odds'].max()
            best_away = odds['away_odds'].max()
            best_draw = odds['draw_odds'].max() if 'draw_odds' in odds.columns else None
            
            if best_draw is None:
                return None
            
            # Get bookmakers offering best odds
            home_bookmaker = odds[odds['home_odds'] == best_home].iloc[0]['bookmaker']
            away_bookmaker = odds[odds['away_odds'] == best_away].iloc[0]['bookmaker']
            draw_bookmaker = odds[odds['draw_odds'] == best_draw].iloc[0]['bookmaker']
            
            # Calculate implied probabilities
            home_prob = 1 / best_home
            away_prob = 1 / best_away
            draw_prob = 1 / best_draw
            
            total_prob = home_prob + away_prob + draw_prob
            
            # Check if arbitrage exists
            if total_prob < 1.0:
                profit_margin = (1 - total_prob)
                
                if profit_margin >= self.min_profit_margin:
                    # Calculate optimal stakes
                    total_stake = min(1000.0, self.max_stake)  # Example stake
                    
                    home_stake = (home_prob / total_prob) * total_stake
                    away_stake = (away_prob / total_prob) * total_stake
                    draw_stake = (draw_prob / total_prob) * total_stake
                    
                    return {
                        'id': str(uuid.uuid4()),
                        'market_id': market_id,
                        'arbitrage_type': 'classic',
                        'arbitrage_opportunity': True,
                        'profit_margin': profit_margin,
                        'total_stake': total_stake,
                        'guaranteed_profit': total_stake * profit_margin,
                        'legs': [
                            {
                                'bookmaker': home_bookmaker,
                                'selection': 'home',
                                'odds': best_home,
                                'stake': home_stake,
                            },
                            {
                                'bookmaker': away_bookmaker,
                                'selection': 'away',
                                'odds': best_away,
                                'stake': away_stake,
                            },
                            {
                                'bookmaker': draw_bookmaker,
                                'selection': 'draw',
                                'odds': best_draw,
                                'stake': draw_stake,
                            },
                        ],
                        'optimal_stakes': {
                            'home': home_stake,
                            'away': away_stake,
                            'draw': draw_stake,
                        },
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in classic arbitrage detection: {e}")
            return None
    
    def _detect_two_way_arbitrage(self, market_id: str, odds: pd.DataFrame) -> Optional[Dict]:
        """Detect two-way arbitrage (home/away only)."""
        try:
            # Get best odds
            best_home = odds['home_odds'].max()
            best_away = odds['away_odds'].max()
            
            home_bookmaker = odds[odds['home_odds'] == best_home].iloc[0]['bookmaker']
            away_bookmaker = odds[odds['away_odds'] == best_away].iloc[0]['bookmaker']
            
            # Calculate implied probabilities
            home_prob = 1 / best_home
            away_prob = 1 / best_away
            
            total_prob = home_prob + away_prob
            
            # Check if arbitrage exists
            if total_prob < 1.0:
                profit_margin = (1 - total_prob)
                
                if profit_margin >= self.min_profit_margin:
                    total_stake = min(1000.0, self.max_stake)
                    
                    home_stake = (home_prob / total_prob) * total_stake
                    away_stake = (away_prob / total_prob) * total_stake
                    
                    return {
                        'id': str(uuid.uuid4()),
                        'market_id': market_id,
                        'arbitrage_type': 'two_way',
                        'arbitrage_opportunity': True,
                        'profit_margin': profit_margin,
                        'total_stake': total_stake,
                        'guaranteed_profit': total_stake * profit_margin,
                        'legs': [
                            {
                                'bookmaker': home_bookmaker,
                                'selection': 'home',
                                'odds': best_home,
                                'stake': home_stake,
                            },
                            {
                                'bookmaker': away_bookmaker,
                                'selection': 'away',
                                'odds': best_away,
                                'stake': away_stake,
                            },
                        ],
                        'optimal_stakes': {
                            'home': home_stake,
                            'away': away_stake,
                        },
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in two-way arbitrage detection: {e}")
            return None
    
    def _save_opportunities(self, opportunities: List[Dict]):
        """Save arbitrage opportunities to database."""
        try:
            with handle_db_errors() as session:
                for opp in opportunities:
                    signal = ArbitrageSignal(
                        id=opp['id'],
                        market_id=opp['market_id'],
                        arbitrage_type=opp['arbitrage_type'],
                        profit_margin=opp['profit_margin'],
                        total_stake=opp['total_stake'],
                        legs=opp['legs'],
                        optimal_stakes=opp['optimal_stakes'],
                    )
                    session.add(signal)
                
                logger.info(f"Saved {len(opportunities)} arbitrage signals to database")
                
        except Exception as e:
            logger.error(f"Error saving arbitrage opportunities: {e}", exc_info=True)
    
    def get_active_opportunities(self, market_id: Optional[str] = None) -> List[Dict]:
        """Get active arbitrage opportunities."""
        try:
            with handle_db_errors() as session:
                query = session.query(ArbitrageSignal).filter(
                    ArbitrageSignal.is_active == True
                )
                
                if market_id:
                    query = query.filter(ArbitrageSignal.market_id == market_id)
                
                signals = query.order_by(
                    ArbitrageSignal.profit_margin.desc()
                ).limit(50).all()
                
                return [
                    {
                        'id': s.id,
                        'market_id': s.market_id,
                        'arbitrage_type': s.arbitrage_type,
                        'profit_margin': s.profit_margin,
                        'total_stake': s.total_stake,
                        'legs': s.legs,
                        'optimal_stakes': s.optimal_stakes,
                        'detected_at': s.detected_at.isoformat(),
                    }
                    for s in signals
                ]
                
        except Exception as e:
            logger.error(f"Error getting arbitrage opportunities: {e}")
            return []
