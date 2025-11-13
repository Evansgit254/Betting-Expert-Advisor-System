"""Backtesting module for historical simulation."""
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

import pandas as pd

try:
    from src.feature import build_features
    from src.strategy import find_value_bets
    from src.tools.synthetic_data import generate_complete_dataset
    from src.logging_config import get_logger
    from src.utils import setup_logging
except ModuleNotFoundError:  # pragma: no cover - fallback for direct execution
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from src.feature import build_features
    from src.strategy import find_value_bets
    from src.tools.synthetic_data import generate_complete_dataset
    from src.logging_config import get_logger
    from src.utils import setup_logging

setup_logging()
logger = get_logger(__name__)


class Backtester:
    """Backtest engine for evaluating betting strategies."""

    def __init__(self, initial_bankroll: float = 10000.0):
        """Initialize backtester.

        Args:
            initial_bankroll: Starting bankroll amount
        """
        self.initial_bankroll = initial_bankroll
        self.bankroll = initial_bankroll
        self.bet_history: List[Dict[str, Any]] = []
        self.daily_stats: List[Dict[str, Any]] = []

        logger.info(f"Backtester initialized with ${initial_bankroll:.2f}")

    def run(
        self,
        fixtures_df: pd.DataFrame,
        odds_df: pd.DataFrame,
        results_df: pd.DataFrame,
        model_predictions: Optional[pd.DataFrame] = None,
        default_win_prob: float = 0.55,
    ) -> Dict[str, Any]:
        """Run backtest simulation.

        Args:
            fixtures_df: Historical fixtures
            odds_df: Historical odds
            results_df: Actual results
            model_predictions: Model predictions (if available)
            default_win_prob: Default probability if no model predictions

        Returns:
            Dictionary with backtest results
        """
        logger.info(f"Starting backtest on {len(fixtures_df)} fixtures")

        # Build features
        features = build_features(fixtures_df, odds_df)

        # Add predictions
        if model_predictions is not None:
            features = features.merge(model_predictions, on="market_id", how="left")
        else:
            # Use default probability
            features["p_win"] = default_win_prob

        # Merge with results
        features = features.merge(results_df, on="market_id", how="left")

        # Filter to valid bets only (where we have results)
        features = features.dropna(subset=["result"])

        # Sort by date to simulate time progression
        if "start" in features.columns:
            features = features.sort_values("start")

        # Track daily performance
        current_date = None
        daily_bets = 0
        daily_stake = 0.0
        daily_pnl = 0.0

        for _, row in features.iterrows():
            # Check if we need to finalize daily stats
            bet_date = row.get("start")
            if bet_date and current_date and bet_date.date() != current_date.date():
                # Save daily stats
                self.daily_stats.append(
                    {
                        "date": current_date.date(),
                        "bets": daily_bets,
                        "stake": daily_stake,
                        "pnl": daily_pnl,
                        "bankroll": self.bankroll,
                    }
                )
                daily_bets = 0
                daily_stake = 0.0
                daily_pnl = 0.0

            current_date = bet_date

            # Find value bets for this row
            bet_data = pd.DataFrame([row])
            bets = find_value_bets(
                bet_data,
                proba_col="p_win",
                odds_col="odds",
                bank=self.bankroll,
                min_ev=0.01,  # 1% minimum edge for real markets
            )

            # Process each bet
            for bet in bets:
                stake = bet["stake"]
                odds = bet["odds"]
                selection = bet["selection"]
                actual_result = row["result"]

                # Determine outcome
                if selection == actual_result:
                    # Win
                    profit = stake * (odds - 1)
                    outcome = "win"
                else:
                    # Loss
                    profit = -stake
                    outcome = "loss"

                # Update bankroll
                self.bankroll += profit

                # Record bet
                bet_record = {
                    **bet,
                    "outcome": outcome,
                    "profit": profit,
                    "bankroll_after": self.bankroll,
                    "date": bet_date,
                }
                self.bet_history.append(bet_record)

                # Update daily stats
                daily_bets += 1
                daily_stake += stake
                daily_pnl += profit

                logger.debug(
                    f"{bet_date.date()} - {selection} @ {odds:.2f} - "
                    f"{outcome.upper()} - P/L: ${profit:.2f} - "
                    f"Bankroll: ${self.bankroll:.2f}"
                )

                # Stop if bankroll depleted
                if self.bankroll <= 0:
                    logger.warning("Bankroll depleted - stopping backtest")
                    break

            if self.bankroll <= 0:
                break

        # Finalize last day
        if current_date:
            self.daily_stats.append(
                {
                    "date": current_date.date(),
                    "bets": daily_bets,
                    "stake": daily_stake,
                    "pnl": daily_pnl,
                    "bankroll": self.bankroll,
                }
            )

        # Calculate summary statistics
        results = self._calculate_summary()

        logger.info(
            f"Backtest complete: {results['total_bets']} bets, "
            f"Final P/L: ${results['total_pnl']:.2f}"
        )

        return results

    def _calculate_summary(self) -> Dict[str, Any]:
        """Calculate summary statistics from backtest."""
        # Initialize default values
        summary = {
            "total_bets": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "roi": 0.0,
            "win_rate": 0.0,
            "avg_odds": 0.0,
            "avg_stake": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "final_bankroll": self.bankroll,
            "bankroll_change": self.bankroll - self.initial_bankroll,
            "bankroll_change_pct": (
                (self.bankroll - self.initial_bankroll) / self.initial_bankroll * 100
            )
            if self.initial_bankroll > 0
            else 0.0,
        }

        if not self.bet_history:
            return summary

        try:
            df = pd.DataFrame(self.bet_history)

            # Basic metrics
            summary["total_bets"] = len(df)
            summary["wins"] = int(df["outcome"].eq("win").sum()) if "outcome" in df.columns else 0
            summary["losses"] = (
                int(df["outcome"].eq("loss").sum()) if "outcome" in df.columns else 0
            )

            # Calculate win rate
            summary["win_rate"] = (
                (summary["wins"] / summary["total_bets"] * 100)
                if summary["total_bets"] > 0
                else 0.0
            )

            # Calculate P&L and ROI
            if "profit" in df.columns:
                summary["total_pnl"] = float(df["profit"].sum())

            if "stake" in df.columns:
                total_stake = float(df["stake"].sum())
                summary["roi"] = (
                    (summary["total_pnl"] / total_stake * 100) if total_stake > 0 else 0.0
                )
                summary["avg_stake"] = float(df["stake"].mean()) if len(df) > 0 else 0.0

            # Calculate average odds
            if "odds" in df.columns:
                summary["avg_odds"] = float(df["odds"].mean()) if len(df) > 0 else 0.0

            # Calculate Sharpe-like ratio
            if len(df) > 1 and "profit" in df.columns and "stake" in df.columns:
                returns = df["profit"] / df["stake"]
                if len(returns) > 1 and returns.std() > 0:
                    summary["sharpe_ratio"] = float(returns.mean() / returns.std())

            # Calculate max drawdown
            if "bankroll_after" in df.columns:
                cummax = df["bankroll_after"].cummax()
                drawdown = (df["bankroll_after"] - cummax) / cummax
                if not drawdown.empty:
                    summary["max_drawdown_pct"] = float(drawdown.min() * 100)

            return summary

        except Exception as e:
            logger.error(f"Error calculating summary: {e}")
            return summary

    def save_results(self, output_path: str = "backtest_results.csv") -> None:
        """Save backtest results to CSV.

        Args:
            output_path: Path to save results
        """
        if not self.bet_history:
            logger.warning("No bets to save")
            return

        # Create parent directories if they don't exist
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame(self.bet_history)
        df.to_csv(path, index=False)
        logger.info(f"Results saved to {path}")

    def print_summary(self) -> None:
        """Print backtest summary to console."""
        summary = self._calculate_summary()

        print("\n" + "=" * 60)
        print("BACKTEST SUMMARY")
        print("=" * 60)
        print(f"Total Bets:          {summary.get('total_bets', 0)}")
        print(f"Wins / Losses:       {summary.get('wins', 0)} / {summary.get('losses', 0)}")
        print(f"Win Rate:            {summary.get('win_rate', 0.0):.2f}%")
        print(f"\nTotal P/L:          ${summary.get('total_pnl', 0.0):,.2f}")
        print(f"ROI:                 {summary.get('roi', 0.0):.2f}%")
        print(f"Avg Odds:            {summary.get('avg_odds', 0.0):.2f}")
        print(f"Avg Stake:           ${summary.get('avg_stake', 0.0):,.2f}")
        print(f"Sharpe Ratio:        {summary.get('sharpe_ratio', 0.0):.2f}")
        print(f"Max Drawdown:        {summary.get('max_drawdown_pct', 0.0):.2f}%")
        print("\n" + "-" * 60)
        print(f"Starting Bankroll:   ${self.initial_bankroll:,.2f}")
        print(f"Final Bankroll:      ${summary.get('final_bankroll', self.initial_bankroll):,.2f}")
        print(
            f"Net Change:          ${summary.get('bankroll_change', 0.0):+,.2f} "
            f"({summary.get('bankroll_change_pct', 0.0):+.2f}%)"
        )
        print("=" * 60)


def run_backtest(
    days: int = 90, initial_bank: float = 10000.0, games_per_day: int = 5
) -> pd.DataFrame:
    """Run a complete backtest with synthetic data.

    Args:
        days: Number of days to simulate
        initial_bank: Initial bankroll
        games_per_day: Average games per day

    Returns:
        DataFrame with backtest results
    """
    logger.info(f"Running {days}-day backtest with ${initial_bank:.2f} bankroll")

    # Generate synthetic data
    fixtures, odds, results = generate_complete_dataset(n_days=days, games_per_day=games_per_day)

    # Create backtester
    backtester = Backtester(initial_bankroll=initial_bank)

    # Run backtest
    backtester.run(fixtures, odds, results)

    # Save and print results
    backtester.save_results()
    backtester.print_summary()

    return pd.DataFrame(backtester.bet_history)


if __name__ == "__main__":
    # Run backtest when executed directly
    results_df = run_backtest(days=60, initial_bank=5000.0, games_per_day=8)
    print("\nBacktest complete. Results saved to backtest_results.csv")
    print(f"Total bets placed: {len(results_df)}")
