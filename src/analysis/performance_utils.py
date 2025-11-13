"""Simple performance calculation utilities for testing."""
from typing import Optional

import pandas as pd


def calculate_roi(total_profit: float, total_stake: float) -> float:
    """Calculate return on investment.

    Args:
        total_profit: Total profit/loss
        total_stake: Total amount staked

    Returns:
        ROI as percentage
    """
    if total_stake == 0:
        return 0.0
    return (total_profit / total_stake) * 100.0


def calculate_win_rate(wins: int, total_bets: int) -> float:
    """Calculate win rate percentage.

    Args:
        wins: Number of winning bets
        total_bets: Total number of bets

    Returns:
        Win rate as percentage
    """
    if total_bets == 0:
        return 0.0
    return (wins / total_bets) * 100.0


def calculate_sharpe_ratio(returns, risk_free_rate: float = 0.0) -> float:
    """Calculate Sharpe ratio.

    Args:
        returns: Series or list of returns
        risk_free_rate: Risk-free rate (default 0)

    Returns:
        Sharpe ratio
    """
    # Convert to pandas Series if needed
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)

    if returns.empty or len(returns) == 0:
        return 0.0

    excess_returns = returns - risk_free_rate
    if excess_returns.std() == 0:
        return 0.0

    return excess_returns.mean() / excess_returns.std()


def calculate_max_drawdown(equity_curve) -> float:
    """Calculate maximum drawdown from equity curve.

    Args:
        equity_curve: Series or list of equity values

    Returns:
        Maximum drawdown as percentage
    """
    # Convert to pandas Series if needed
    if not isinstance(equity_curve, pd.Series):
        equity_curve = pd.Series(equity_curve)

    if equity_curve.empty or len(equity_curve) == 0:
        return 0.0

    # Calculate running maximum
    running_max = equity_curve.expanding().max()

    # Calculate drawdown
    drawdown = (equity_curve - running_max) / running_max * 100

    return abs(drawdown.min())


class PerformanceAnalyzer:
    """Analyzer for bet performance metrics."""

    def __init__(self, bets_df: Optional[pd.DataFrame] = None):
        """Initialize the analyzer.

        Args:
            bets_df: DataFrame with bet data
        """
        self.bets_df = bets_df if bets_df is not None else pd.DataFrame()

    def calculate_metrics(self) -> dict:
        """Calculate all performance metrics.

        Returns:
            Dictionary with metrics
        """
        if self.bets_df.empty:
            return {
                "total_bets": 0,
                "total_stake": 0.0,
                "total_profit": 0.0,
                "win_rate": 0.0,
                "roi": 0.0,
            }

        total_bets = len(self.bets_df)
        total_stake = self.bets_df["stake"].sum() if "stake" in self.bets_df else 0.0
        total_profit = self.bets_df["profit_loss"].sum() if "profit_loss" in self.bets_df else 0.0

        wins = 0
        if "result" in self.bets_df:
            wins = (self.bets_df["result"] == "win").sum()

        return {
            "total_bets": total_bets,
            "total_stake": total_stake,
            "total_profit": total_profit,
            "win_rate": calculate_win_rate(wins, total_bets),
            "roi": calculate_roi(total_profit, total_stake),
        }

    def get_equity_curve(self) -> pd.Series:
        """Calculate cumulative equity curve.

        Returns:
            Series of cumulative profit/loss
        """
        if self.bets_df.empty or "profit_loss" not in self.bets_df:
            return pd.Series()

        return self.bets_df["profit_loss"].cumsum()
