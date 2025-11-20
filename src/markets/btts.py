"""Both Teams To Score (BTTS) market analyzer."""
import numpy as np
from typing import Dict, List
from scipy.stats import poisson

from src.logging_config import get_logger

logger = get_logger(__name__)


class BTTSAnalyzer:
    """Analyze Both Teams To Score markets."""
    
    def __init__(self):
        """Initialize BTTS analyzer."""
        logger.info("BTTSAnalyzer initialized")
    
    def predict_btts(
        self,
        home_goals_avg: float,
        away_goals_avg: float,
        home_conceded_avg: float,
        away_conceded_avg: float,
        home_btts_rate: float = 0.5,
        away_btts_rate: float = 0.5
    ) -> Dict[str, float]:
        """Predict BTTS probability.
        
        Args:
            home_goals_avg: Home team average goals scored
            away_goals_avg: Away team average goals scored
            home_conceded_avg: Home team average goals conceded
            away_conceded_avg: Away team average goals conceded
            home_btts_rate: Historical BTTS rate for home team
            away_btts_rate: Historical BTTS rate for away team
            
        Returns:
            Dict with BTTS probabilities
        """
        # Method 1: Poisson-based
        # P(Home scores) = 1 - P(Home scores 0)
        home_expected = (home_goals_avg + away_conceded_avg) / 2
        away_expected = (away_goals_avg + home_conceded_avg) / 2
        
        prob_home_scores = 1 - poisson.pmf(0, home_expected)
        prob_away_scores = 1 - poisson.pmf(0, away_expected)
        
        # P(BTTS) = P(Home scores) * P(Away scores)
        prob_btts_poisson = prob_home_scores * prob_away_scores
        
        # Method 2: Historical BTTS rates
        prob_btts_historical = (home_btts_rate + away_btts_rate) / 2
        
        # Weighted average (70% Poisson, 30% historical)
        prob_btts = 0.7 * prob_btts_poisson + 0.3 * prob_btts_historical
        prob_no_btts = 1 - prob_btts
        
        return {
            'btts_yes': prob_btts,
            'btts_no': prob_no_btts,
            'prob_home_scores': prob_home_scores,
            'prob_away_scores': prob_away_scores
        }
    
    def find_value_btts(
        self,
        prediction: Dict,
        odds: Dict[str, float],
        min_edge: float = 0.05
    ) -> List[Dict]:
        """Find value bets in BTTS markets.
        
        Args:
            prediction: Predicted BTTS probabilities
            odds: Market odds {'btts_yes': 1.90, 'btts_no': 1.95}
            min_edge: Minimum edge required
            
        Returns:
            List of value opportunities
        """
        opportunities = []
        
        for selection in ['btts_yes', 'btts_no']:
            if selection not in odds or selection not in prediction:
                continue
            
            prob = prediction[selection]
            market_odds = odds[selection]
            implied_prob = 1 / market_odds
            edge = prob - implied_prob
            
            if edge >= min_edge:
                ev = (prob * market_odds) - 1
                
                opportunities.append({
                    'market': 'btts',
                    'selection': selection,
                    'odds': market_odds,
                    'probability': prob,
                    'edge': edge,
                    'ev': ev
                })
        
        return opportunities
    
    def analyze_match(
        self,
        home_team_stats: Dict,
        away_team_stats: Dict,
        odds: Dict[str, float]
    ) -> List[Dict]:
        """Analyze a match for BTTS value.
        
        Args:
            home_team_stats: Team statistics including btts_rate
            away_team_stats: Team statistics including btts_rate
            odds: BTTS market odds
            
        Returns:
            List of value opportunities
        """
        prediction = self.predict_btts(
            home_goals_avg=home_team_stats.get('goals_scored_avg', 1.5),
            away_goals_avg=away_team_stats.get('goals_scored_avg', 1.5),
            home_conceded_avg=home_team_stats.get('goals_conceded_avg', 1.2),
            away_conceded_avg=away_team_stats.get('goals_conceded_avg', 1.2),
            home_btts_rate=home_team_stats.get('btts_rate', 0.5),
            away_btts_rate=away_team_stats.get('btts_rate', 0.5)
        )
        
        return self.find_value_btts(prediction, odds)
