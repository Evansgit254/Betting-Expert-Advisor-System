"""Correlation estimation for betting opportunities."""
import numpy as np
from typing import List, Dict

from src.logging_config import get_logger

logger = get_logger(__name__)


class CorrelationEstimator:
    """Estimate correlations between betting opportunities."""
    
    def __init__(self):
        """Initialize correlation estimator."""
        self.correlation_rules = {
            'same_match_different_outcome': -1.0,  # Mutually exclusive
            'same_league_same_day': 0.3,           # Moderate correlation
            'same_team_different_match': 0.5,      # High correlation
            'different_league': 0.1,               # Low correlation
            'default': 0.0                         # Independent
        }
        
        logger.info("CorrelationEstimator initialized with rule-based estimation")
    
    def estimate_correlation_matrix(self, opportunities: List[Dict]) -> np.ndarray:
        """Estimate correlation matrix for opportunities.
        
        Args:
            opportunities: List of betting opportunities with metadata
            
        Returns:
            Correlation matrix (n x n)
        """
        n = len(opportunities)
        
        if n == 0:
            return np.array([[]])
        
        if n == 1:
            return np.array([[1.0]])
        
        # Initialize correlation matrix
        corr_matrix = np.eye(n)
        
        # Fill off-diagonal elements
        for i in range(n):
            for j in range(i + 1, n):
                corr = self._estimate_pairwise_correlation(
                    opportunities[i],
                    opportunities[j]
                )
                corr_matrix[i, j] = corr
                corr_matrix[j, i] = corr  # Symmetric
        
        logger.debug(f"Estimated correlation matrix for {n} opportunities")
        return corr_matrix
    
    def _estimate_pairwise_correlation(self, opp1: Dict, opp2: Dict) -> float:
        """Estimate correlation between two opportunities.
        
        Args:
            opp1: First opportunity
            opp2: Second opportunity
            
        Returns:
            Correlation coefficient (-1 to 1)
        """
        # Check if same match
        market_id1 = opp1.get('market_id', '')
        market_id2 = opp2.get('market_id', '')
        
        if market_id1 and market_id2 and market_id1 == market_id2:
            # Same match, different outcomes
            selection1 = opp1.get('selection', '')
            selection2 = opp2.get('selection', '')
            
            if selection1 != selection2:
                return self.correlation_rules['same_match_different_outcome']
            else:
                # Same match, same selection (duplicate?)
                return 1.0
        
        # Check if same team involved
        home1 = opp1.get('home', '').lower()
        away1 = opp1.get('away', '').lower()
        home2 = opp2.get('home', '').lower()
        away2 = opp2.get('away', '').lower()
        
        teams1 = {home1, away1} if home1 and away1 else set()
        teams2 = {home2, away2} if home2 and away2 else set()
        
        if teams1 and teams2 and teams1 & teams2:
            # At least one team in common
            return self.correlation_rules['same_team_different_match']
        
        # Check if same league
        league1 = opp1.get('league', '').lower()
        league2 = opp2.get('league', '').lower()
        
        if league1 and league2:
            if league1 == league2:
                # Same league - check if same day
                # (Simplified: assume moderate correlation for same league)
                return self.correlation_rules['same_league_same_day']
            else:
                # Different leagues
                return self.correlation_rules['different_league']
        
        # Default: assume independent
        return self.correlation_rules['default']
    
    def get_diversification_score(self, opportunities: List[Dict]) -> float:
        """Calculate diversification score for a set of opportunities.
        
        Higher score = better diversification
        
        Args:
            opportunities: List of opportunities
            
        Returns:
            Diversification score (0 to 1)
        """
        if len(opportunities) <= 1:
            return 0.0
        
        corr_matrix = self.estimate_correlation_matrix(opportunities)
        
        # Average absolute correlation (excluding diagonal)
        n = len(opportunities)
        off_diagonal = corr_matrix[np.triu_indices(n, k=1)]
        avg_correlation = np.abs(off_diagonal).mean()
        
        # Diversification score: 1 - avg_correlation
        # (lower correlation = higher diversification)
        diversification = 1.0 - avg_correlation
        
        return diversification
