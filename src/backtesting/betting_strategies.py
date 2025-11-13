"""Betting-specific strategy implementations for backtesting."""
from typing import Any, Dict, Optional


class ValueBettingStrategy:
    """Value betting strategy based on edge over bookmaker odds."""

    def __init__(self, min_edge: float = 0.05, min_odds: float = 1.5, max_odds: float = 10.0):
        """Initialize value betting strategy.

        Args:
            min_edge: Minimum edge required (e.g., 0.05 = 5%)
            min_odds: Minimum acceptable odds
            max_odds: Maximum acceptable odds
        """
        self.min_edge = min_edge
        self.min_odds = min_odds
        self.max_odds = max_odds

    def evaluate(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Evaluate if a bet should be placed.

        Args:
            market_data: Dictionary with market information including:
                - odds: Decimal odds offered
                - p_win: Estimated win probability
                - market_id: Market identifier
                - selection: Selection name

        Returns:
            Bet recommendation dict or None
        """
        odds = market_data.get("odds", 0)
        p_win = market_data.get("p_win", 0)

        # Calculate expected value and edge
        implied_prob = 1.0 / odds if odds > 1 else 0
        edge = p_win - implied_prob

        # Check if bet meets criteria
        if edge >= self.min_edge and self.min_odds <= odds <= self.max_odds:
            return {
                "market_id": market_data.get("market_id"),
                "selection": market_data.get("selection"),
                "odds": odds,
                "stake": 0,  # Will be determined by staking strategy
                "edge": edge,
                "p_win": p_win,
            }

        return None


class KellyCriterionStrategy:
    """Kelly criterion-based staking strategy."""

    def __init__(self, bankroll: float, kelly_fraction: float = 0.25, min_edge: float = 0.02):
        """Initialize Kelly strategy.

        Args:
            bankroll: Current bankroll
            kelly_fraction: Fraction of full Kelly to bet (0.25 = quarter Kelly)
            min_edge: Minimum edge required to bet
        """
        self.bankroll = bankroll
        self.kelly_fraction = kelly_fraction
        self.min_edge = min_edge

    def evaluate(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Evaluate bet sizing using Kelly criterion.

        Args:
            market_data: Market data with odds and win probability

        Returns:
            Bet recommendation with Kelly stake or None
        """
        odds = market_data.get("odds", 0)
        p_win = market_data.get("p_win", 0)

        if odds <= 1.0 or p_win <= 0:
            return None

        # Calculate edge
        implied_prob = 1.0 / odds
        edge = p_win - implied_prob

        if edge < self.min_edge:
            return None

        # Kelly formula: f = (bp - q) / b
        # where b = odds - 1, p = p_win, q = 1 - p_win
        b = odds - 1
        q = 1 - p_win
        kelly_fraction_full = (b * p_win - q) / b

        # Apply fractional Kelly
        kelly_stake = self.bankroll * kelly_fraction_full * self.kelly_fraction

        # Ensure positive stake
        if kelly_stake <= 0:
            return None

        # Cap at 10% of bankroll
        kelly_stake = min(kelly_stake, self.bankroll * 0.1)

        return {
            "market_id": market_data.get("market_id"),
            "selection": market_data.get("selection"),
            "odds": odds,
            "stake": kelly_stake,
            "edge": edge,
            "p_win": p_win,
            "kelly_fraction": kelly_fraction_full,
        }


class ArbitrageStrategy:
    """Arbitrage betting strategy."""

    def __init__(self, min_profit_margin: float = 0.01):
        """Initialize arbitrage strategy.

        Args:
            min_profit_margin: Minimum profit margin required (e.g., 0.01 = 1%)
        """
        self.min_profit_margin = min_profit_margin

    def detect_opportunity(self, odds_data: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Detect arbitrage opportunities across multiple bookmakers.

        Args:
            odds_data: Dictionary mapping outcomes to best odds
                e.g., {'home': 2.1, 'draw': 3.5, 'away': 4.0}

        Returns:
            Arbitrage opportunity details or None
        """
        if not odds_data or len(odds_data) < 2:
            return None

        # Calculate total inverse odds (implied probability sum)
        total_inv_odds = sum(1.0 / odds for odds in odds_data.values())

        # If less than 1, there's an arbitrage opportunity
        if total_inv_odds < 1.0:
            profit_margin = (1.0 / total_inv_odds) - 1.0

            if profit_margin >= self.min_profit_margin:
                return {
                    "opportunity": True,
                    "profit_margin": profit_margin,
                    "total_inv_odds": total_inv_odds,
                    "odds": odds_data,
                    "stakes": self._calculate_stakes(odds_data, total_inv_odds),
                }

        return None

    def _calculate_stakes(
        self, odds_data: Dict[str, float], total_inv_odds: float, total_stake: float = 100.0
    ) -> Dict[str, float]:
        """Calculate optimal stakes for arbitrage.

        Args:
            odds_data: Odds for each outcome
            total_inv_odds: Sum of inverse odds
            total_stake: Total amount to stake

        Returns:
            Dictionary of stakes per outcome
        """
        stakes = {}
        for outcome, odds in odds_data.items():
            stakes[outcome] = (total_stake / odds) / total_inv_odds

        return stakes

    def evaluate(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Evaluate for arbitrage opportunities.

        Args:
            market_data: Market data with multiple odds

        Returns:
            Arbitrage bet recommendation or None
        """
        # Extract odds for different outcomes
        odds_dict = {}
        if "home_odds" in market_data:
            odds_dict["home"] = market_data["home_odds"]
        if "draw_odds" in market_data:
            odds_dict["draw"] = market_data["draw_odds"]
        if "away_odds" in market_data:
            odds_dict["away"] = market_data["away_odds"]

        return self.detect_opportunity(odds_dict)
