"""Over/Under (Totals) market analyzer."""
import numpy as np
from typing import Dict, List, Optional
from scipy.stats import poisson

from src.logging_config import get_logger

logger = get_logger(__name__)


class TotalsAnalyzer:
    """Analyze Over/Under goals markets."""
    
    def __init__(self):
        """Initialize totals analyzer."""
        self.common_lines = [0.5, 1.5, 2.5, 3.5, 4.5]
        logger.info("TotalsAnalyzer initialized")
    
    def predict_total_goals(
        self,
        home_goals_avg: float,
        away_goals_avg: float,
        home_conceded_avg: float,
        away_conceded_avg: float
    ) -> Dict[str, float]:
        """Predict expected goals for a match.
        
        Args:
            home_goals_avg: Home team average goals scored
            away_goals_avg: Away team average goals scored
            home_conceded_avg: Home team average goals conceded
            away_conceded_avg: Away team average goals conceded
            
        Returns:
            Dict with expected goals and probabilities
        """
        # Expected goals using attack/defense strength
        home_expected = (home_goals_avg + away_conceded_avg) / 2
        away_expected = (away_goals_avg + home_conceded_avg) / 2
        total_expected = home_expected + away_expected
        
        # Calculate probabilities for each line using Poisson
        probabilities = {}
        for line in self.common_lines:
            # Probability of total goals > line
            prob_over = self._prob_over_line(total_expected, line)
            probabilities[f'over_{line}'] = prob_over
            probabilities[f'under_{line}'] = 1 - prob_over
        
        return {
            'expected_total': total_expected,
            'expected_home': home_expected,
            'expected_away': away_expected,
            'probabilities': probabilities
        }
    
    def _prob_over_line(self, expected_goals: float, line: float) -> float:
        """Calculate probability of total goals over a line.
        
        Uses Poisson distribution for goal modeling.
        """
        # P(X > line) = 1 - P(X <= line)
        # For 2.5: P(X > 2.5) = 1 - P(X <= 2)
        threshold = int(np.floor(line))
        prob_under = poisson.cdf(threshold, expected_goals)
        return 1 - prob_under
    
    def find_value_totals(
        self,
        prediction: Dict,
        odds: Dict[str, float],
        min_edge: float = 0.05
    ) -> List[Dict]:
        """Find value bets in Over/Under markets.
        
        Args:
            prediction: Predicted probabilities
            odds: Market odds {'over_2.5': 2.10, 'under_2.5': 1.80}
            min_edge: Minimum edge required (default 5%)
            
        Returns:
            List of value bet opportunities
        """
        opportunities = []
        probabilities = prediction.get('probabilities', {})
        
        for market, prob in probabilities.items():
            if market not in odds:
                continue
            
            market_odds = odds[market]
            implied_prob = 1 / market_odds
            edge = prob - implied_prob
            
            if edge >= min_edge:
                # Calculate expected value
                ev = (prob * market_odds) - 1
                
                opportunities.append({
                    'market': 'totals',
                    'selection': market,
                    'odds': market_odds,
                    'probability': prob,
                    'edge': edge,
                    'ev': ev,
                    'expected_total': prediction['expected_total']
                })
        
        return opportunities
    
    def analyze_match(
        self,
        home_team_stats: Dict,
        away_team_stats: Dict,
        odds: Dict[str, float]
    ) -> List[Dict]:
        """Analyze a match for Over/Under value.
        
        Args:
            home_team_stats: {'goals_scored_avg': 1.5, 'goals_conceded_avg': 1.2}
            away_team_stats: {'goals_scored_avg': 1.3, 'goals_conceded_avg': 1.1}
            odds: Market odds
            
        Returns:
            List of value opportunities
        """
        prediction = self.predict_total_goals(
            home_goals_avg=home_team_stats.get('goals_scored_avg', 1.5),
            away_goals_avg=away_team_stats.get('goals_scored_avg', 1.5),
            home_conceded_avg=home_team_stats.get('goals_conceded_avg', 1.2),
            away_conceded_avg=away_team_stats.get('goals_conceded_avg', 1.2)
        )
        
        return self.find_value_totals(prediction, odds)
