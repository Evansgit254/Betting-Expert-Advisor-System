"""Performance analysis for betting strategies."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import pandas as pd

from src.db import BetRecord, handle_db_errors


class PerformanceMetric(Enum):
    """Available performance metrics."""

    PROFIT_LOSS = "total_profit_loss"
    WIN_RATE = "win_rate"
    PROFIT_MARGIN = "profit_margin"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    TRADE_COUNT = "total_bets"


@dataclass
class PerformanceReport:
    """Container for strategy performance report."""

    strategy_name: str
    start_date: datetime
    end_date: datetime
    metrics: Dict[str, float]
    trades: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert the report to a pandas DataFrame."""
        metrics_df = pd.DataFrame([self.metrics])
        trades_df = pd.DataFrame(self.trades)
        return metrics_df, trades_df

    def plot_equity_curve(self, save_path: Optional[str] = None) -> plt.Figure:
        """Plot the equity curve.

        Args:
            save_path: If provided, save the plot to this path

        Returns:
            Matplotlib figure
        """
        if self.equity_curve.empty:
            raise ValueError("No equity curve data available")

        fig, ax = plt.subplots(figsize=(12, 6))
        self.equity_curve.plot(ax=ax, title=f"{self.strategy_name} - Equity Curve")
        ax.set_ylabel("Equity")
        ax.grid(True)

        if save_path:
            fig.savefig(save_path, bbox_inches="tight")

        return fig


class StrategyAnalyzer:
    """Analyze performance of betting strategies."""

    def __init__(self, strategy_name: str):
        """Initialize the analyzer for a specific strategy.

        Args:
            strategy_name: Name of the strategy to analyze
        """
        self.strategy_name = strategy_name
        self._trades: Optional[pd.DataFrame] = None
        self._performance: Optional[Dict[str, Any]] = None

    def load_data(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> "StrategyAnalyzer":
        """Load trade and performance data from the database.

        Args:
            start_date: Filter trades after this date
            end_date: Filter trades before this date

        Returns:
            Self for method chaining
        """
        with handle_db_errors() as session:
            # Load trades
            query = session.query(BetRecord).filter(BetRecord.strategy == self.strategy_name)

            if start_date:
                query = query.filter(BetRecord.placed_at >= start_date)
            if end_date:
                query = query.filter(BetRecord.placed_at <= end_date)

            trades = query.order_by(BetRecord.placed_at).all()

            # Convert to DataFrame
            self._trades = pd.DataFrame(
                [
                    {
                        "id": t.id,
                        "market_id": t.market_id,
                        "selection": t.selection,
                        "stake": t.stake,
                        "odds": t.odds,
                        "result": t.result,
                        "profit_loss": t.profit_loss or 0.0,
                        "placed_at": t.placed_at,
                        "settled_at": t.settled_at,
                        "is_dry_run": t.is_dry_run,
                        "strategy_params": t.strategy_params,
                    }
                    for t in trades
                ]
            )

            # Performance data calculated from trades
            self._performance = None

        return self

    def generate_report(self) -> PerformanceReport:
        """Generate a performance report.

        Returns:
            PerformanceReport object with analysis results

        Raises:
            ValueError: If no data has been loaded
        """
        if self._trades is None:
            raise ValueError("No data loaded. Call load_data() first.")

        # Calculate equity curve
        equity_curve = self._calculate_equity_curve()

        # Create report
        report = PerformanceReport(
            strategy_name=self.strategy_name,
            start_date=self._performance["start_date"],
            end_date=self._performance["end_date"],
            metrics={
                "total_profit_loss": self._performance["total_profit_loss"],
                "total_bets": self._performance["total_bets"],
                "win_rate": self._performance["win_rate"],
                "profit_margin": self._performance["profit_margin"],
                "sharpe_ratio": self._performance["sharpe_ratio"],
                "max_drawdown": self._performance["max_drawdown"],
                "total_staked": self._performance["total_staked"],
                "roi": (self._performance["total_profit_loss"] / self._performance["total_staked"])
                * 100
                if self._performance["total_staked"] > 0
                else 0.0,
            },
            trades=self._trades.to_dict("records"),
            equity_curve=equity_curve,
        )

        return report

    def _calculate_equity_curve(self) -> pd.Series:
        """Calculate the equity curve from trades."""
        if self._trades is None or self._trades.empty:
            return pd.Series()

        # Sort trades by settlement date
        trades_sorted = self._trades.sort_values("settled_at")

        # Calculate cumulative P&L
        equity = trades_sorted["profit_loss"].cumsum()
        equity.index = trades_sorted["settled_at"]

        # Resample to daily data
        equity_daily = equity.resample("D").last().ffill()

        return equity_daily

    def compare_strategies(self, other_analyzers: List["StrategyAnalyzer"]) -> Dict[str, Any]:
        """Compare this strategy's performance to others.

        Args:
            other_analyzers: List of other StrategyAnalyzer instances to compare with

        Returns:
            Dictionary with comparison metrics
        """
        if self._performance is None:
            self.load_data()

        comparison = {
            "strategies": [self.strategy_name] + [a.strategy_name for a in other_analyzers],
            "metrics": {},
        }

        # Get all analyzers including self
        all_analyzers = [self] + other_analyzers

        # Compare key metrics
        for metric in ["total_profit_loss", "win_rate", "sharpe_ratio", "max_drawdown"]:
            comparison["metrics"][metric] = [
                getattr(a._performance or {}, metric, None) for a in all_analyzers
            ]

        return comparison

    @staticmethod
    def plot_performance_comparison(
        comparison: Dict[str, Any], metric: str, title: str = None, save_path: str = None
    ) -> plt.Figure:
        """Plot a bar chart comparing strategies on a specific metric.

        Args:
            comparison: Result from compare_strategies()
            metric: Metric to plot
            title: Plot title (defaults to metric name)
            save_path: If provided, save the plot to this path

        Returns:
            Matplotlib figure
        """
        if metric not in comparison["metrics"]:
            raise ValueError(f"Unknown metric: {metric}")

        fig, ax = plt.subplots(figsize=(10, 6))

        # Create bar plot
        y_pos = range(len(comparison["strategies"]))
        ax.bar(y_pos, comparison["metrics"][metric])

        # Add labels and title
        ax.set_xticks(y_pos)
        ax.set_xticklabels(comparison["strategies"], rotation=45, ha="right")
        ax.set_ylabel(metric.replace("_", " ").title())
        ax.set_title(title or f"Strategy Comparison: {metric.replace('_', ' ').title()}")

        # Add value labels on top of bars
        for i, v in enumerate(comparison["metrics"][metric]):
            if v is not None:
                ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, bbox_inches="tight")

        return fig
