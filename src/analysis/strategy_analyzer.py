"""Strategy performance analysis and metrics calculation."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import List, Optional, Union

import numpy as np
import pandas as pd


class MetricPeriod(Enum):
    """Time periods for performance metrics calculation."""

    DAILY = auto()
    WEEKLY = auto()
    MONTHLY = auto()
    QUARTERLY = auto()
    YEARLY = auto()


@dataclass
class StrategyMetrics:
    """Comprehensive strategy performance metrics."""

    # Basic metrics
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    expectancy: float
    kelly_criterion: float
    calmar_ratio: float

    # Additional metrics
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    win_loss_ratio: float = 0.0
    recovery_factor: float = 0.0
    ulcer_index: float = 0.0
    tail_ratio: float = 0.0
    common_sense_ratio: float = 0.0
    risk_adjusted_return: float = 0.0

    # Risk metrics
    value_at_risk_95: float = 0.0
    conditional_var_95: float = 0.0
    downside_deviation: float = 0.0

    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    avg_trade_duration: timedelta = timedelta()

    # Time-based metrics
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert metrics to a dictionary."""
        result = asdict(self)
        # Convert timedelta to seconds for JSON serialization
        if isinstance(result.get("avg_trade_duration"), timedelta):
            result["avg_trade_duration_seconds"] = result["avg_trade_duration"].total_seconds()
            del result["avg_trade_duration"]
        return result


class StrategyAnalyzer:
    """Analyzes strategy performance and calculates various metrics."""

    def __init__(
        self,
        returns: Union[pd.Series, List[float]],
        benchmark_returns: Optional[Union[pd.Series, List[float]]] = None,
    ):
        """
        Initialize the strategy analyzer with returns data.

        Args:
            returns: Series or list of strategy returns (e.g., [0.01, -0.02, 0.03])
            benchmark_returns: Optional series of benchmark returns for comparison
        """
        self.returns = self._prepare_returns(returns)
        self.benchmark_returns = (
            self._prepare_returns(benchmark_returns) if benchmark_returns is not None else None
        )
        self._equity_curve = None
        self._drawdown = None

    @staticmethod
    def _prepare_returns(returns: Union[pd.Series, List[float]]) -> pd.Series:
        """Convert returns to a pandas Series with datetime index if not already."""
        if isinstance(returns, pd.Series):
            if returns.index.dtype == "datetime64[ns]":
                return returns
            return pd.Series(returns.values)
        return pd.Series(returns)

    def calculate_metrics(self, risk_free_rate: float = 0.02) -> StrategyMetrics:
        """
        Calculate comprehensive performance metrics for the strategy.

        Args:
            risk_free_rate: Annual risk-free rate (default: 0.02 or 2%)

        Returns:
            StrategyMetrics: Object containing all calculated metrics
        """
        if self.returns.empty:
            return StrategyMetrics(
                **{
                    f.name: 0.0
                    for f in StrategyMetrics.__dataclass_fields__.values()
                    if f.type in (float, int)
                }
            )

        # Basic metrics
        n_periods = len(self.returns)
        total_return = (1 + self.returns).prod() - 1
        annualized_return = (1 + total_return) ** (252 / n_periods) - 1 if n_periods > 0 else 0

        # Risk metrics
        volatility = self.returns.std() * np.sqrt(252) if n_periods > 1 else 0
        downside_returns = self.returns[self.returns < 0]
        downside_volatility = (
            downside_returns.std() * np.sqrt(252) if len(downside_returns) > 1 else 0
        )

        # Risk-adjusted returns
        sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0
        sortino_ratio = (
            (annualized_return - risk_free_rate) / downside_volatility
            if downside_volatility > 0
            else 0
        )

        # Drawdown
        cum_returns = (1 + self.returns).cumprod()
        peak = cum_returns.expanding(min_periods=1).max()
        drawdown = (cum_returns - peak) / peak
        max_drawdown = drawdown.min() if not drawdown.empty else 0

        # Win/loss metrics
        wins = self.returns[self.returns > 0]
        losses = self.returns[self.returns < 0]
        breakeven = self.returns[self.returns == 0]

        total_trades = n_periods
        winning_trades = len(wins)
        losing_trades = len(losses)
        breakeven_trades = len(breakeven)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        avg_win = wins.mean() if winning_trades > 0 else 0
        avg_loss = losses.mean() if losing_trades > 0 else 0
        max_win = wins.max() if winning_trades > 0 else 0
        max_loss = losses.min() if losing_trades > 0 else 0

        profit_factor = (
            -avg_win * winning_trades / (avg_loss * losing_trades)
            if losing_trades > 0 and avg_loss < 0
            else float("inf")
        )
        win_loss_ratio = -avg_win / avg_loss if losing_trades > 0 and avg_loss < 0 else float("inf")

        # Kelly Criterion
        kelly = (win_rate * (win_loss_ratio + 1) - 1) / win_loss_ratio if win_loss_ratio > 0 else 0

        # Additional metrics
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown < 0 else 0
        recovery_factor = total_return / abs(max_drawdown) if max_drawdown < 0 else 0

        # Ulcer Index
        ulcer_index = np.sqrt((drawdown**2).mean()) if not drawdown.empty else 0

        # Tail ratio (95% percentile / 5% percentile of returns)
        if len(self.returns) >= 20:  # Need enough data points
            tail_ratio = abs(np.percentile(self.returns, 95) / np.percentile(self.returns, 5))
        else:
            tail_ratio = 0

        # Common Sense Ratio (average return / average loss)
        common_sense_ratio = -avg_win / avg_loss if avg_loss < 0 else float("inf")

        # Risk-adjusted return (Sortino ratio with different risk-free rate)
        risk_adjusted_return = (
            (annualized_return - risk_free_rate) / downside_volatility
            if downside_volatility > 0
            else 0
        )

        # Value at Risk (VaR) and Conditional VaR (CVaR)
        if len(self.returns) >= 10:  # Need enough data points
            var_95 = np.percentile(self.returns, 5)
            cvar_95 = self.returns[self.returns <= var_95].mean()
        else:
            var_95 = 0
            cvar_95 = 0

        # Create and return metrics object
        metrics = StrategyMetrics(
            total_return=float(total_return),
            annualized_return=float(annualized_return),
            volatility=float(volatility),
            sharpe_ratio=float(sharpe_ratio),
            sortino_ratio=float(sortino_ratio),
            max_drawdown=float(max_drawdown),
            win_rate=float(win_rate),
            profit_factor=float(profit_factor) if profit_factor != float("inf") else float("inf"),
            expectancy=float(avg_win * win_rate + avg_loss * (1 - win_rate)),
            kelly_criterion=float(kelly),
            calmar_ratio=float(calmar_ratio),
            avg_win=float(avg_win),
            avg_loss=float(avg_loss),
            max_win=float(max_win),
            max_loss=float(max_loss),
            win_loss_ratio=float(win_loss_ratio)
            if win_loss_ratio != float("inf")
            else float("inf"),
            recovery_factor=float(recovery_factor),
            ulcer_index=float(ulcer_index),
            tail_ratio=float(tail_ratio),
            common_sense_ratio=float(common_sense_ratio)
            if common_sense_ratio != float("inf")
            else float("inf"),
            risk_adjusted_return=float(risk_adjusted_return),
            value_at_risk_95=float(var_95),
            conditional_var_95=float(cvar_95),
            downside_deviation=float(downside_volatility / np.sqrt(252)) if n_periods > 1 else 0.0,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            breakeven_trades=breakeven_trades,
            start_date=self.returns.index[0] if not self.returns.empty else None,
            end_date=self.returns.index[-1] if not self.returns.empty else None,
        )

        return metrics

    def rolling_metrics(self, window: int = 21, min_periods: int = 5) -> pd.DataFrame:
        """
        Calculate rolling performance metrics.

        Args:
            window: Number of periods in the rolling window
            min_periods: Minimum number of observations required

        Returns:
            DataFrame with rolling metrics
        """
        if self.returns.empty:
            return pd.DataFrame()

        returns = self.returns

        # Calculate rolling metrics
        rolling_vol = returns.rolling(window=window, min_periods=min_periods).std() * np.sqrt(252)
        rolling_sharpe = (
            returns.rolling(window=window, min_periods=min_periods).mean()
            / returns.rolling(window=window, min_periods=min_periods).std()
            * np.sqrt(252)
        )

        rolling_max = (1 + returns).rolling(window=window, min_periods=1).max()
        rolling_drawdown = (1 + returns).cumsum() / rolling_max - 1

        rolling_win_rate = (returns > 0).rolling(window=window, min_periods=min_periods).mean()

        # Create result DataFrame
        result = pd.DataFrame(
            {
                "returns": returns,
                "volatility": rolling_vol,
                "sharpe_ratio": rolling_sharpe,
                "drawdown": rolling_drawdown,
                "win_rate": rolling_win_rate,
            }
        )

        return result

    def get_equity_curve(self, initial_capital: float = 1.0) -> pd.Series:
        """
        Calculate the equity curve over time.

        Args:
            initial_capital: Starting capital (default: 1.0 for normalized returns)

        Returns:
            Series with equity curve values
        """
        if self._equity_curve is None:
            if self.returns.empty:
                return pd.Series()
            self._equity_curve = (1 + self.returns).cumprod() * initial_capital
        return self._equity_curve

    def get_drawdown_series(self) -> pd.Series:
        """Calculate the drawdown series."""
        if self._drawdown is None:
            equity_curve = self.get_equity_curve()
            if equity_curve.empty:
                return pd.Series()
            rolling_max = equity_curve.expanding(min_periods=1).max()
            self._drawdown = (equity_curve - rolling_max) / rolling_max
        return self._drawdown

    def get_monthly_returns(self) -> pd.Series:
        """Calculate monthly returns."""
        if self.returns.empty:
            return pd.Series()

        if not isinstance(self.returns.index, pd.DatetimeIndex):
            raise ValueError("Returns must have a datetime index to calculate monthly returns")

        return self.returns.resample("M").apply(lambda x: (1 + x).prod() - 1)

    def get_annual_returns(self) -> pd.Series:
        """Calculate annual returns."""
        if self.returns.empty:
            return pd.Series()

        if not isinstance(self.returns.index, pd.DatetimeIndex):
            raise ValueError("Returns must have a datetime index to calculate annual returns")

        return self.returns.resample("A").apply(lambda x: (1 + x).prod() - 1)

    def get_rolling_volatility(self, window: int = 21) -> pd.Series:
        """Calculate rolling annualized volatility."""
        if self.returns.empty:
            return pd.Series()

        return self.returns.rolling(window=window).std() * np.sqrt(252)

    def get_rolling_sharpe(self, window: int = 21, risk_free_rate: float = 0.02) -> pd.Series:
        """Calculate rolling Sharpe ratio."""
        if self.returns.empty:
            return pd.Series()

        excess_returns = self.returns - (risk_free_rate / 252)  # Daily risk-free rate
        rolling_sharpe = (
            excess_returns.rolling(window=window).mean()
            / excess_returns.rolling(window=window).std()
            * np.sqrt(252)
        )
        return rolling_sharpe

    def get_rolling_sortino(self, window: int = 21, risk_free_rate: float = 0.02) -> pd.Series:
        """Calculate rolling Sortino ratio."""
        if self.returns.empty:
            return pd.Series()

        excess_returns = self.returns - (risk_free_rate / 252)  # Daily risk-free rate
        downside_returns = excess_returns.copy()
        downside_returns[downside_returns > 0] = 0

        rolling_sortino = (
            excess_returns.rolling(window=window).mean()
            / downside_returns.rolling(window=window).std().replace(0, np.nan)
            * np.sqrt(252)
        )
        return rolling_sortino
