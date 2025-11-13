"""Backtesting engine for evaluating betting strategies."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd
from tqdm import tqdm

from src.logging_config import get_logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)


class TradeDirection(Enum):
    """Direction of a trade."""

    LONG = auto()
    SHORT = auto()


@dataclass
class Trade:
    """Represents a single trade in the backtest."""

    id: str
    direction: TradeDirection
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    size: float = 0.0
    pnl: Optional[float] = None
    return_pct: Optional[float] = None
    commission: float = 0.0
    slippage: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_open(self) -> bool:
        """Check if the trade is still open."""
        return self.exit_price is None

    def close(
        self,
        exit_price: float,
        exit_time: Optional[datetime] = None,
        commission: float = 0.0,
        slippage: float = 0.0,
    ) -> None:
        """Close the trade and calculate P&L."""
        self.exit_price = exit_price
        self.exit_time = exit_time or datetime.utcnow()
        self.commission += commission
        self.slippage += slippage

        # Calculate P&L
        if self.direction == TradeDirection.LONG:
            self.return_pct = (self.exit_price / self.entry_price - 1) * 100
        else:  # SHORT
            self.return_pct = (1 - self.exit_price / self.entry_price) * 100

        self.pnl = (self.size * self.return_pct / 100) - self.commission - self.slippage


@dataclass
class BacktestResult:
    """Results of a backtest."""

    strategy_name: str
    parameters: Dict[str, Any]
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_equity: float
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    max_win: float
    max_loss: float
    avg_trade_duration: timedelta
    trades: List[Trade]
    equity_curve: pd.Series
    drawdown: pd.Series


class BacktestEngine:
    """Backtesting engine for evaluating trading strategies."""

    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission: float = 0.001,  # 0.1% commission per trade
        slippage: float = 0.0005,  # 0.05% slippage per trade
        position_sizing: str = "fixed",  # 'fixed', 'percent_risk', 'volatility'
        risk_per_trade: float = 0.01,  # 1% risk per trade
        max_position_size: float = 0.1,  # Max 10% of portfolio per position
        stop_loss_pct: Optional[float] = 0.02,  # 2% stop loss
        take_profit_pct: Optional[float] = 0.04,
    ):  # 4% take profit
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_sizing = position_sizing
        self.risk_per_trade = risk_per_trade
        self.max_position_size = max_position_size
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        # Internal state
        self.current_equity = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, List[Trade]] = {}
        self.closed_trades: List[Trade] = []
        self.equity_curve = []
        self.drawdown = []
        self.current_date: Optional[datetime] = None
        self.current_prices: Dict[str, float] = {}

        # Performance metrics
        self.peak_equity = initial_capital
        self.max_drawdown = 0.0
        self.total_commission = 0.0
        self.total_slippage = 0.0
        self.trade_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0

    def run(self, data: pd.DataFrame, strategy: Callable, **strategy_params) -> BacktestResult:
        """Run the backtest with the given strategy and data."""
        if not isinstance(data, pd.DataFrame) or not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must be a pandas DataFrame with a DatetimeIndex")

        # Reset state
        self._reset()
        self.current_date = data.index[0]

        # Generate signals using the strategy
        signals = strategy(data, **strategy_params)
        signals = signals.reindex(data.index).fillna(0)

        # Main backtest loop
        for i, (timestamp, row) in enumerate(
            tqdm(data.iterrows(), total=len(data), desc="Backtesting")
        ):
            self.current_date = timestamp
            self.current_prices = row.to_dict()

            # Update current signals
            current_signals = signals.loc[timestamp].to_dict() if timestamp in signals.index else {}

            # Update open positions and check for exits
            self._update_positions()

            # Generate new trades based on signals
            self._generate_trades(current_signals)

            # Update equity curve and drawdown
            self._update_equity_curve()

        # Close any remaining open positions at the last price
        self._close_all_positions()

        # Final equity curve update
        self._update_equity_curve(final=True)

        # Calculate performance metrics
        return self._calculate_performance_metrics()

    def _reset(self) -> None:
        """Reset the backtest engine to its initial state."""
        self.current_equity = self.initial_capital
        self.cash = self.initial_capital
        self.positions = {}
        self.closed_trades = []
        self.equity_curve = []
        self.drawdown = []
        self.current_date = None
        self.current_prices = {}
        self.peak_equity = self.initial_capital
        self.max_drawdown = 0.0
        self.total_commission = 0.0
        self.total_slippage = 0.0
        self.trade_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0

    def _update_positions(self) -> None:
        """Update open positions and check for exits."""
        if not self.positions:
            return

        for symbol, trades in list(self.positions.items()):
            if symbol not in self.current_prices:
                continue

            current_price = self.current_prices[symbol]

            # Check each trade for exit conditions
            for trade in list(trades):
                if trade.is_open():
                    # Check stop loss
                    if self.stop_loss_pct is not None and (
                        (
                            trade.direction == TradeDirection.LONG
                            and current_price <= trade.entry_price * (1 - self.stop_loss_pct)
                        )
                        or (
                            trade.direction == TradeDirection.SHORT
                            and current_price >= trade.entry_price * (1 + self.stop_loss_pct)
                        )
                    ):
                        self._close_trade(trade, current_price, reason="stop_loss")

                    # Check take profit
                    elif self.take_profit_pct is not None and (
                        (
                            trade.direction == TradeDirection.LONG
                            and current_price >= trade.entry_price * (1 + self.take_profit_pct)
                        )
                        or (
                            trade.direction == TradeDirection.SHORT
                            and current_price <= trade.entry_price * (1 - self.take_profit_pct)
                        )
                    ):
                        self._close_trade(trade, current_price, reason="take_profit")

            # Remove empty positions
            self.positions[symbol] = [t for t in trades if t.is_open()]
            if not self.positions[symbol]:
                del self.positions[symbol]

    def _generate_trades(self, signals: Dict[str, float]) -> None:
        """Generate new trades based on current signals."""
        for symbol, signal in signals.items():
            if symbol not in self.current_prices:
                continue

            current_price = self.current_prices[symbol]

            # Determine position size
            if self.position_sizing == "fixed":
                position_size = self.initial_capital * self.max_position_size
            elif self.position_sizing == "percent_risk":
                position_size = min(
                    self.current_equity * self.risk_per_trade / (self.stop_loss_pct or 0.01),
                    self.current_equity * self.max_position_size,
                )
            else:  # 'volatility' or default
                position_size = self.current_equity * self.max_position_size

            # Generate buy/sell signals
            if signal > 0:  # Buy signal
                self._open_trade(
                    symbol=symbol,
                    direction=TradeDirection.LONG,
                    price=current_price,
                    size=position_size,
                    stop_loss=current_price * (1 - self.stop_loss_pct)
                    if self.stop_loss_pct
                    else None,
                    take_profit=current_price * (1 + self.take_profit_pct)
                    if self.take_profit_pct
                    else None,
                )
            elif signal < 0:  # Sell/short signal
                self._open_trade(
                    symbol=symbol,
                    direction=TradeDirection.SHORT,
                    price=current_price,
                    size=position_size,
                    stop_loss=current_price * (1 + self.stop_loss_pct)
                    if self.stop_loss_pct
                    else None,
                    take_profit=current_price * (1 - self.take_profit_pct)
                    if self.take_profit_pct
                    else None,
                )

    def _open_trade(
        self,
        symbol: str,
        direction: TradeDirection,
        price: float,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Optional[Trade]:
        """Open a new trade."""
        if size <= 0 or price <= 0 or size > self.cash:
            return None

        # Calculate commission and slippage
        commission = self.commission * size
        slippage = self.slippage * size

        # Create the trade
        trade = Trade(
            id=f"{symbol}_{self.current_date.timestamp()}_{direction.name[0]}",
            direction=direction,
            entry_time=self.current_date,
            entry_price=price,
            size=size,
            commission=commission,
            slippage=slippage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={
                "symbol": symbol,
                "price": price,
                "size": size,
                "equity": self.current_equity,
                "cash": self.cash,
                "timestamp": self.current_date.timestamp(),
            },
        )

        # Update cash and metrics
        self.cash -= size + commission + slippage
        self.total_commission += commission
        self.total_slippage += slippage
        self.trade_count += 1

        # Add to positions
        if symbol not in self.positions:
            self.positions[symbol] = []
        self.positions[symbol].append(trade)

        return trade

    def _close_trade(self, trade: Trade, exit_price: float, reason: str = "") -> None:
        """Close an open trade."""
        if not trade.is_open():
            return

        # Calculate commission and slippage
        commission = self.commission * trade.size
        slippage = self.slippage * trade.size

        # Close the trade
        trade.close(
            exit_price=exit_price,
            exit_time=self.current_date,
            commission=commission,
            slippage=slippage,
        )

        # Update cash and metrics
        self.cash += trade.size + trade.pnl
        self.total_commission += commission
        self.total_slippage += slippage

        if trade.pnl > 0:
            self.winning_trades += 1
        elif trade.pnl < 0:
            self.losing_trades += 1

        # Move to closed trades
        self.closed_trades.append(trade)

    def _close_all_positions(self) -> None:
        """Close all open positions at the current price."""
        for symbol, trades in list(self.positions.items()):
            if symbol in self.current_prices:
                for trade in list(trades):
                    if trade.is_open():
                        self._close_trade(
                            trade, self.current_prices[symbol], reason="end_of_backtest"
                        )

        # Clear positions
        self.positions = {}

    def _update_equity_curve(self, final: bool = False) -> None:
        """Update the equity curve and drawdown."""
        if self.current_date is None:
            return

        # Calculate current equity (cash + open positions)
        position_value = 0.0

        for symbol, trades in self.positions.items():
            if symbol in self.current_prices:
                price = self.current_prices[symbol]
                for trade in trades:
                    if trade.is_open():
                        if trade.direction == TradeDirection.LONG:
                            position_value += trade.size * (price / trade.entry_price - 1)
                        else:  # SHORT
                            position_value += trade.size * (1 - price / trade.entry_price)

        self.current_equity = self.cash + position_value

        # Update peak equity and drawdown
        self.peak_equity = max(self.peak_equity, self.current_equity)
        current_drawdown = (
            (self.peak_equity - self.current_equity) / self.peak_equity
            if self.peak_equity > 0
            else 0.0
        )
        self.max_drawdown = max(self.max_drawdown, current_drawdown)

        # Record equity and drawdown
        self.equity_curve.append((self.current_date, self.current_equity))
        self.drawdown.append((self.current_date, current_drawdown))

    def _calculate_performance_metrics(self) -> BacktestResult:
        """Calculate performance metrics for the backtest."""
        if not self.equity_curve:
            raise ValueError("No equity curve data available")

        # Convert to pandas Series
        equity_dates, equity_values = zip(*self.equity_curve)
        equity_series = pd.Series(equity_values, index=equity_dates)

        drawdown_dates, drawdown_values = zip(*self.drawdown)
        drawdown_series = pd.Series(drawdown_values, index=drawdown_dates)

        # Calculate returns
        returns = equity_series.pct_change().dropna()

        # Calculate metrics
        total_return = (equity_series.iloc[-1] / equity_series.iloc[0]) - 1

        # Annualized return
        days = (equity_series.index[-1] - equity_series.index[0]).days
        years = max(days / 365.25, 0.08)  # At least 1 month to avoid division by zero
        annualized_return = (1 + total_return) ** (1 / years) - 1

        # Volatility (annualized)
        volatility = returns.std() * np.sqrt(252) if not returns.empty else 0.0

        # Sharpe ratio (assuming risk-free rate of 0)
        sharpe_ratio = (annualized_return / volatility) if volatility > 0 else 0.0

        # Sortino ratio (only downside deviation)
        downside_returns = returns[returns < 0]
        downside_volatility = (
            downside_returns.std() * np.sqrt(252) if not downside_returns.empty else 0.0
        )
        sortino_ratio = (
            (annualized_return / downside_volatility) if downside_volatility > 0 else 0.0
        )

        # Win rate and profit factor
        winning_trades = [t for t in self.closed_trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in self.closed_trades if t.pnl and t.pnl < 0]

        total_win = sum(t.pnl for t in winning_trades) if winning_trades else 0.0
        total_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0.0

        win_rate = len(winning_trades) / len(self.closed_trades) if self.closed_trades else 0.0
        profit_factor = total_win / total_loss if total_loss > 0 else float("inf")

        # Average win/loss
        avg_win = np.mean([t.return_pct for t in winning_trades]) / 100 if winning_trades else 0.0
        avg_loss = np.mean([t.return_pct for t in losing_trades]) / 100 if losing_trades else 0.0

        # Max win/loss
        max_win = max([t.return_pct for t in winning_trades], default=0.0) / 100
        max_loss = min([t.return_pct for t in losing_trades], default=0.0) / 100

        # Average trade duration
        durations = [t.exit_time - t.entry_time for t in self.closed_trades if t.exit_time]
        avg_trade_duration = (
            sum(durations, timedelta()) / len(durations) if durations else timedelta()
        )

        return BacktestResult(
            strategy_name="Backtest",
            parameters={
                "initial_capital": self.initial_capital,
                "commission": self.commission,
                "slippage": self.slippage,
                "position_sizing": self.position_sizing,
                "risk_per_trade": self.risk_per_trade,
                "max_position_size": self.max_position_size,
                "stop_loss_pct": self.stop_loss_pct,
                "take_profit_pct": self.take_profit_pct,
            },
            start_date=equity_series.index[0],
            end_date=equity_series.index[-1],
            initial_capital=self.initial_capital,
            final_equity=equity_series.iloc[-1],
            total_return=float(total_return),
            annualized_return=float(annualized_return),
            volatility=float(volatility),
            sharpe_ratio=float(sharpe_ratio),
            sortino_ratio=float(sortino_ratio),
            max_drawdown=float(self.max_drawdown),
            win_rate=float(win_rate),
            profit_factor=float(profit_factor) if profit_factor != float("inf") else float("inf"),
            total_trades=len(self.closed_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_win=float(avg_win),
            avg_loss=float(avg_loss),
            max_win=float(max_win),
            max_loss=float(max_loss),
            avg_trade_duration=avg_trade_duration,
            trades=self.closed_trades,
            equity_curve=equity_series,
            drawdown=drawdown_series,
        )
