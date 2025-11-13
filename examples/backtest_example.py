"""
Example script demonstrating how to use the backtesting engine with a sample strategy.
"""
# Add the project root to the Python path
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))

from src.backtesting.engine import BacktestEngine, TradeDirection
from src.backtesting.strategies import BreakoutStrategy, MeanReversionStrategy, MomentumStrategy


def generate_sample_data(
    days: int = 365,
    freq: str = "D",
    trend: float = 0.0001,
    volatility: float = 0.01,
    start_price: float = 100.0,
) -> pd.DataFrame:
    """
    Generate sample price data with a trend and random noise.

    Args:
        days: Number of days of data to generate
        freq: Frequency of data ('D' for daily, 'H' for hourly, etc.)
        trend: Daily trend factor (0 = no trend, > 0 = upward trend, < 0 = downward trend)
        volatility: Daily volatility (standard deviation of returns)
        start_price: Starting price

    Returns:
        pd.DataFrame: DataFrame with OHLCV data
    """
    # Generate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date, freq=freq)

    # Generate random returns with trend and volatility
    np.random.seed(42)
    n = len(dates)
    returns = np.random.normal(trend, volatility, n)

    # Add some autocorrelation to make it more realistic
    for i in range(1, n):
        returns[i] = 0.7 * returns[i - 1] + 0.3 * returns[i]

    # Calculate price series
    price = start_price * (1 + returns).cumprod()

    # Generate OHLC data (simplified - in a real scenario, generate realistic OHLC)
    df = pd.DataFrame(index=dates)
    df["open"] = price
    df["high"] = price * (1 + np.abs(np.random.normal(0, volatility / 2, n)))
    df["low"] = price * (1 - np.abs(np.random.normal(0, volatility / 2, n)))
    df["close"] = price
    df["volume"] = np.random.lognormal(mean=10, sigma=1, size=n)

    # Ensure high >= close >= low
    df["high"] = df[["high", "close"]].max(axis=1)
    df["low"] = df[["low", "close"]].min(axis=1)

    return df


def plot_backtest_results(result, strategy_name: str):
    """Plot backtest results."""
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(12, 12), gridspec_kw={"height_ratios": [3, 1, 1]}
    )

    # Plot equity curve
    ax1.plot(
        result.equity_curve.index, result.equity_curve.values, label="Equity Curve", color="blue"
    )
    ax1.set_title(f"{strategy_name} - Equity Curve")
    ax1.set_ylabel("Equity ($)")
    ax1.grid(True)

    # Add annotations for final return and max drawdown
    final_return = (result.final_equity / result.initial_capital - 1) * 100
    ax1.annotate(
        f"Final Return: {final_return:.2f}%",
        xy=(0.02, 0.95),
        xycoords="axes fraction",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    ax1.annotate(
        f"Max Drawdown: {result.max_drawdown*100:.2f}%",
        xy=(0.02, 0.88),
        xycoords="axes fraction",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    # Plot drawdown
    ax2.fill_between(
        result.drawdown.index,
        result.drawdown.values * 100,
        0,
        color="red",
        alpha=0.3,
        label="Drawdown",
    )
    ax2.set_title("Drawdown")
    ax2.set_ylabel("Drawdown (%)")
    ax2.grid(True)

    # Plot signals
    # For simplicity, just plot buy/sell signals on the equity curve
    trades = result.trades
    if trades:
        buy_dates = [t.entry_time for t in trades if t.direction == TradeDirection.LONG]
        buy_equity = [
            result.equity_curve[t.entry_time]
            for t in trades
            if t.direction == TradeDirection.LONG and t.entry_time in result.equity_curve.index
        ]

        sell_dates = [t.entry_time for t in trades if t.direction == TradeDirection.SHORT]
        sell_equity = [
            result.equity_curve[t.entry_time]
            for t in trades
            if t.direction == TradeDirection.SHORT and t.entry_time in result.equity_curve.index
        ]

        ax1.scatter(
            buy_dates, buy_equity, color="green", marker="^", label="Buy Signal", alpha=0.7, s=100
        )
        ax1.scatter(
            sell_dates, sell_equity, color="red", marker="v", label="Sell Signal", alpha=0.7, s=100
        )

    ax1.legend()

    # Plot returns distribution
    returns = result.equity_curve.pct_change().dropna()
    ax3.hist(returns * 100, bins=50, alpha=0.7, color="blue", edgecolor="black")
    ax3.axvline(returns.mean() * 100, color="red", linestyle="dashed", linewidth=1)
    ax3.set_title("Daily Returns Distribution")
    ax3.set_xlabel("Return (%)")
    ax3.set_ylabel("Frequency")
    ax3.grid(True)

    plt.tight_layout()
    plt.show()


def run_mean_reversion_strategy():
    """Run a backtest with a mean reversion strategy."""
    print("\n=== Running Mean Reversion Strategy ===")

    # Generate sample data
    data = generate_sample_data(days=365, trend=0.0001, volatility=0.01)

    # Initialize strategy
    strategy = MeanReversionStrategy(lookback=20, zscore_threshold=1.5)

    # Initialize backtest engine
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.001,  # 0.1% commission
        slippage=0.0005,  # 0.05% slippage
        position_sizing="fixed",
        max_position_size=0.1,  # Max 10% of portfolio per position
        stop_loss_pct=0.02,  # 2% stop loss
        take_profit_pct=0.04,  # 4% take profit
    )

    # Run backtest
    result = engine.run(data, strategy)

    # Print results
    print(f"\nStrategy: {result.strategy_name}")
    print(f"Period: {result.start_date.date()} to {result.end_date.date()}")
    print(f"Initial Capital: ${result.initial_capital:,.2f}")
    print(f"Final Equity: ${result.final_equity:,.2f}")
    print(f"Total Return: {result.total_return*100:.2f}%")
    print(f"Annualized Return: {result.annualized_return*100:.2f}%")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {result.max_drawdown*100:.2f}%")
    print(f"Win Rate: {result.win_rate*100:.2f}%")
    print(f"Total Trades: {result.total_trades}")
    print(f"Winning Trades: {result.winning_trades}")
    print(f"Losing Trades: {result.losing_trades}")

    # Plot results
    plot_backtest_results(result, "Mean Reversion Strategy")


def run_momentum_strategy():
    """Run a backtest with a momentum strategy."""
    print("\n=== Running Momentum Strategy ===")

    # Generate sample data with a stronger trend
    data = generate_sample_data(days=365, trend=0.0003, volatility=0.015)

    # Initialize strategy
    strategy = MomentumStrategy(lookback=20, ma_fast=10, ma_slow=30)

    # Initialize backtest engine
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.001,  # 0.1% commission
        slippage=0.0005,  # 0.05% slippage
        position_sizing="fixed",
        max_position_size=0.1,  # Max 10% of portfolio per position
        stop_loss_pct=0.03,  # 3% stop loss
        take_profit_pct=0.06,  # 6% take profit
    )

    # Run backtest
    result = engine.run(data, strategy)

    # Print results
    print(f"\nStrategy: {result.strategy_name}")
    print(f"Period: {result.start_date.date()} to {result.end_date.date()}")
    print(f"Initial Capital: ${result.initial_capital:,.2f}")
    print(f"Final Equity: ${result.final_equity:,.2f}")
    print(f"Total Return: {result.total_return*100:.2f}%")
    print(f"Annualized Return: {result.annualized_return*100:.2f}%")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {result.max_drawdown*100:.2f}%")
    print(f"Win Rate: {result.win_rate*100:.2f}%")
    print(f"Total Trades: {result.total_trades}")

    # Plot results
    plot_backtest_results(result, "Momentum Strategy")


def run_breakout_strategy():
    """Run a backtest with a breakout strategy."""
    print("\n=== Running Breakout Strategy ===")

    # Generate sample data with some ranging periods and breakouts
    np.random.seed(42)
    days = 365
    dates = pd.date_range(end=datetime.now(), periods=days, freq="D")

    # Create price series with ranging and trending periods
    price = np.ones(days) * 100

    for i in range(1, days):
        # Add some volatility
        ret = np.random.normal(0, 0.005)

        # Add trends and breakouts
        if 30 <= i < 90:  # First trending period
            ret += 0.0015
        elif 150 <= i < 210:  # Second trending period
            ret -= 0.0015
        elif 270 <= i < 330:  # Third trending period
            ret += 0.002

        price[i] = price[i - 1] * (1 + ret)

    # Create DataFrame with OHLC data
    data = pd.DataFrame(index=dates)
    data["close"] = price
    data["open"] = data["close"].shift(1) * (1 + np.random.normal(0, 0.002, days))
    data["high"] = data[["open", "close"]].max(axis=1) * (
        1 + np.abs(np.random.normal(0, 0.002, days))
    )
    data["low"] = data[["open", "close"]].min(axis=1) * (
        1 - np.abs(np.random.normal(0, 0.002, days))
    )
    data["volume"] = np.random.lognormal(10, 0.5, days)
    data = data.dropna()

    # Initialize strategy
    strategy = BreakoutStrategy(lookback=20, atr_period=14, atr_multiplier=1.5)

    # Initialize backtest engine
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.001,  # 0.1% commission
        slippage=0.0005,  # 0.05% slippage
        position_sizing="fixed",
        max_position_size=0.1,  # Max 10% of portfolio per position
        stop_loss_pct=0.025,  # 2.5% stop loss
        take_profit_pct=0.05,  # 5% take profit
    )

    # Run backtest
    result = engine.run(data, strategy)

    # Print results
    print(f"\nStrategy: {result.strategy_name}")
    print(f"Period: {result.start_date.date()} to {result.end_date.date()}")
    print(f"Initial Capital: ${result.initial_capital:,.2f}")
    print(f"Final Equity: ${result.final_equity:,.2f}")
    print(f"Total Return: {result.total_return*100:.2f}%")
    print(f"Annualized Return: {result.annualized_return*100:.2f}%")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {result.max_drawdown*100:.2f}%")
    print(f"Win Rate: {result.win_rate*100:.2f}%")
    print(f"Total Trades: {result.total_trades}")

    # Plot results
    plot_backtest_results(result, "Breakout Strategy")


if __name__ == "__main__":
    # Run all strategy examples
    run_mean_reversion_strategy()
    run_momentum_strategy()
    run_breakout_strategy()
