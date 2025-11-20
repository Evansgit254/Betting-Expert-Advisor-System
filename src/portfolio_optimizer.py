"""Portfolio optimization using Modern Portfolio Theory."""
import numpy as np
from scipy.optimize import minimize
from typing import List, Dict, Optional, Tuple

from src.logging_config import get_logger

logger = get_logger(__name__)


class PortfolioOptimizer:
    """Optimize bet allocation across multiple opportunities using MPT."""
    
    def __init__(
        self,
        max_position_size: float = 0.15,
        min_diversification: int = 1,
        risk_free_rate: float = 0.0
    ):
        """Initialize portfolio optimizer.
        
        Args:
            max_position_size: Max fraction of bankroll per bet (e.g., 0.15 = 15%)
            min_diversification: Minimum number of bets if possible
            risk_free_rate: Risk-free rate for Sharpe calculation
        """
        self.max_position_size = max_position_size
        self.min_diversification = min_diversification
        self.risk_free_rate = risk_free_rate
        
        logger.info(
            f"PortfolioOptimizer initialized (max_position={max_position_size:.1%}, "
            f"min_diversification={min_diversification})"
        )
    
    def optimize_portfolio(
        self,
        opportunities: List[Dict],
        bankroll: float,
        correlation_matrix: Optional[np.ndarray] = None
    ) -> Dict:
        """Optimize stake allocation across opportunities.
        
        Args:
            opportunities: List of value bets with 'ev' and 'p' (probability)
            bankroll: Available bankroll
            correlation_matrix: Correlation matrix (n x n) or None for independent
            
        Returns:
            Dict with optimized allocations and portfolio metrics
        """
        n_opps = len(opportunities)
        
        if n_opps == 0:
            return {'allocations': [], 'metrics': {}}
        
        # Single opportunity - simple Kelly
        if n_opps == 1:
            return self._single_opportunity(opportunities[0], bankroll)
        
        # Extract expected values and probabilities
        evs = np.array([opp['ev'] for opp in opportunities])
        probs = np.array([opp['p'] for opp in opportunities])
        odds = np.array([opp.get('odds', 2.0) for opp in opportunities])
        
        # Default to independent if no correlation matrix
        if correlation_matrix is None:
            correlation_matrix = np.eye(n_opps)
        
        # Estimate variances (simplified: variance ~= p * (1-p) * (odds-1)^2)
        variances = probs * (1 - probs) * ((odds - 1) ** 2)
        
        # Covariance matrix
        std_devs = np.sqrt(variances)
        cov_matrix = np.outer(std_devs, std_devs) * correlation_matrix
        
        # Optimize
        result = self._optimize_sharpe(evs, cov_matrix, bankroll, n_opps)
        
        # Build result
        allocations = []
        for i, opp in enumerate(opportunities):
            stake = result['weights'][i] * bankroll
            if stake > 0.01:  # Filter out tiny allocations
                allocations.append({
                    **opp,
                    'stake': stake,
                    'weight': result['weights'][i]
                })
        
        return {
            'allocations': allocations,
            'metrics': {
                'expected_return': result['expected_return'],
                'volatility': result['volatility'],
                'sharpe_ratio': result['sharpe_ratio'],
                'diversification': len(allocations)
            }
        }
    
    def _single_opportunity(self, opportunity: Dict, bankroll: float) -> Dict:
        """Handle single opportunity case (simple Kelly)."""
        ev = opportunity['ev']
        p = opportunity['p']
        odds = opportunity.get('odds', 2.0)
        
        # Kelly fraction: f = (p * odds - 1) / (odds - 1)
        kelly_fraction = (p * odds - 1) / (odds - 1) if odds > 1 else 0
        kelly_fraction = max(0, min(kelly_fraction, self.max_position_size))
        
        stake = kelly_fraction * bankroll
        
        return {
            'allocations': [{**opportunity, 'stake': stake, 'weight': kelly_fraction}],
            'metrics': {
                'expected_return': kelly_fraction * ev,
                'volatility': kelly_fraction * np.sqrt(p * (1-p) * (odds-1)**2),
                'sharpe_ratio': ev / np.sqrt(p * (1-p) * (odds-1)**2) if p * (1-p) > 0 else 0,
                'diversification': 1
            }
        }
    
    def _optimize_sharpe(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        bankroll: float,
        n_assets: int
    ) -> Dict:
        """Optimize portfolio to maximize Sharpe ratio.
        
        Args:
            expected_returns: Expected value for each bet
            cov_matrix: Covariance matrix
            bankroll: Total bankroll
            n_assets: Number of assets
            
        Returns:
            Optimal weights and metrics
        """
        # Objective: Minimize negative Sharpe ratio
        def neg_sharpe(weights):
            portfolio_return = np.dot(weights, expected_returns)
            portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            if portfolio_vol == 0:
                return 0
            
            sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol
            return -sharpe  # Minimize negative = maximize positive
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Weights sum to 1
        ]
        
        # Bounds: each weight between 0 and max_position_size
        bounds = tuple((0, self.max_position_size) for _ in range(n_assets))
        
        # Initial guess: equal weight
        initial_weights = np.ones(n_assets) / n_assets
        
        # Optimize
        result = minimize(
            neg_sharpe,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )
        
        if not result.success:
            logger.warning(f"Optimization did not converge: {result.message}")
        
        # Calculate final metrics
        optimal_weights = result.x
        portfolio_return = np.dot(optimal_weights, expected_returns)
        portfolio_vol = np.sqrt(np.dot(optimal_weights.T, np.dot(cov_matrix, optimal_weights)))
        sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0
        
        return {
            'weights': optimal_weights,
            'expected_return': portfolio_return,
            'volatility': portfolio_vol,
            'sharpe_ratio': sharpe
        }
    
    def calculate_portfolio_metrics(
        self,
        allocations: List[Dict],
        correlation_matrix: Optional[np.ndarray] = None
    ) -> Dict:
        """Calculate metrics for a given portfolio allocation.
        
        Args:
            allocations: List of bets with stakes
            correlation_matrix: Optional correlation matrix
            
        Returns:
            Portfolio metrics
        """
        if not allocations:
            return {}
        
        n = len(allocations)
        stakes = np.array([a['stake'] for a in allocations])
        evs = np.array([a['ev'] for a in allocations])
        probs = np.array([a['p'] for a in allocations])
        odds = np.array([a.get('odds', 2.0) for a in allocations])
        
        total_stake = stakes.sum()
        weights = stakes / total_stake if total_stake > 0 else np.zeros(n)
        
        # Expected return
        expected_return = np.dot(weights, evs)
        
        # Variance
        if correlation_matrix is None:
            correlation_matrix = np.eye(n)
        
        variances = probs * (1 - probs) * ((odds - 1) ** 2)
        std_devs = np.sqrt(variances)
        cov_matrix = np.outer(std_devs, std_devs) * correlation_matrix
        
        portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
        portfolio_vol = np.sqrt(portfolio_variance)
        
        # Sharpe ratio
        sharpe = (expected_return - self.risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0
        
        return {
            'expected_return': expected_return,
            'volatility': portfolio_vol,
            'sharpe_ratio': sharpe,
            'total_stake': total_stake,
            'diversification': n
        }
