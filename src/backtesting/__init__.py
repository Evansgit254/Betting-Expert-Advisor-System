"""Backtesting module for evaluating betting strategies."""
from .engine import BacktestEngine, BacktestResult, Position, Trade
from .strategies import (
    BreakoutStrategy,
    MachineLearningStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
)

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "Trade",
    "Position",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "BreakoutStrategy",
    "MachineLearningStrategy",
]
