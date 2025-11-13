"""Strategy implementations for backtesting."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

import numpy as np
import pandas as pd


class StrategyType(Enum):
    """Types of trading strategies."""

    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    MACHINE_LEARNING = "machine_learning"


@dataclass
class StrategyResult:
    """Container for strategy results."""

    signals: pd.DataFrame
    indicators: Dict[str, pd.Series]
    params: Dict[str, Any]

    def __post_init__(self):
        """Validate the result."""
        if not isinstance(self.signals, pd.DataFrame):
            raise ValueError("Signals must be a pandas DataFrame")
        if not all(isinstance(v, pd.Series) for v in self.indicators.values()):
            raise ValueError("All indicators must be pandas Series")


class MeanReversionStrategy:
    """Mean reversion trading strategy."""

    def __init__(self, lookback: int = 20, zscore_threshold: float = 2.0):
        """
        Initialize the mean reversion strategy.

        Args:
            lookback: Number of periods for mean and std calculation
            zscore_threshold: Z-score threshold for entry/exit signals
        """
        self.lookback = lookback
        self.zscore_threshold = zscore_threshold

    def __call__(self, data: pd.DataFrame, **kwargs) -> StrategyResult:
        """
        Generate trading signals based on mean reversion.

        Args:
            data: DataFrame with price data (must have 'close' column)

        Returns:
            StrategyResult: Contains signals and indicators
        """
        if "close" not in data.columns:
            raise ValueError("Input data must contain 'close' column")

        close = data["close"]

        # Calculate rolling mean and standard deviation
        rolling_mean = close.rolling(window=self.lookback).mean()
        rolling_std = close.rolling(window=self.lookback).std()

        # Calculate z-score
        zscore = (close - rolling_mean) / rolling_std

        # Generate signals
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals.loc[zscore < -self.zscore_threshold, "signal"] = 1  # Buy signal
        signals.loc[zscore > self.zscore_threshold, "signal"] = -1  # Sell signal

        # Store indicators
        indicators = {"zscore": zscore, "rolling_mean": rolling_mean, "rolling_std": rolling_std}

        return StrategyResult(
            signals=signals,
            indicators=indicators,
            params={
                "strategy": "mean_reversion",
                "lookback": self.lookback,
                "zscore_threshold": self.zscore_threshold,
            },
        )


class MomentumStrategy:
    """Momentum trading strategy."""

    def __init__(self, lookback: int = 20, ma_fast: int = 10, ma_slow: int = 30):
        """
        Initialize the momentum strategy.

        Args:
            lookback: Number of periods for momentum calculation
            ma_fast: Fast moving average period
            ma_slow: Slow moving average period
        """
        self.lookback = lookback
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow

    def __call__(self, data: pd.DataFrame, **kwargs) -> StrategyResult:
        """
        Generate trading signals based on momentum.

        Args:
            data: DataFrame with price data (must have 'close' column)

        Returns:
            StrategyResult: Contains signals and indicators
        """
        if "close" not in data.columns:
            raise ValueError("Input data must contain 'close' column")

        close = data["close"]

        # Calculate momentum
        returns = close.pct_change(periods=self.lookback)

        # Calculate moving averages
        ma_fast = close.rolling(window=self.ma_fast).mean()
        ma_slow = close.rolling(window=self.ma_slow).mean()

        # Generate signals
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0

        # Long when fast MA crosses above slow MA and momentum is positive
        long_condition = (ma_fast > ma_slow) & (returns > 0)
        signals.loc[long_condition, "signal"] = 1

        # Short when fast MA crosses below slow MA and momentum is negative
        short_condition = (ma_fast < ma_slow) & (returns < 0)
        signals.loc[short_condition, "signal"] = -1

        # Store indicators
        indicators = {"returns": returns, "ma_fast": ma_fast, "ma_slow": ma_slow}

        return StrategyResult(
            signals=signals,
            indicators=indicators,
            params={
                "strategy": "momentum",
                "lookback": self.lookback,
                "ma_fast": self.ma_fast,
                "ma_slow": self.ma_slow,
            },
        )


class BreakoutStrategy:
    """Breakout trading strategy."""

    def __init__(self, lookback: int = 20, atr_period: int = 14, atr_multiplier: float = 2.0):
        """
        Initialize the breakout strategy.

        Args:
            lookback: Number of periods for high/low calculation
            atr_period: Period for Average True Range calculation
            atr_multiplier: Multiplier for ATR to determine breakout threshold
        """
        self.lookback = lookback
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Calculate Average True Range (ATR)."""
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=self.atr_period).mean()

    def __call__(self, data: pd.DataFrame, **kwargs) -> StrategyResult:
        """
        Generate trading signals based on breakouts.

        Args:
            data: DataFrame with price data (must have 'high', 'low', 'close' columns)

        Returns:
            StrategyResult: Contains signals and indicators
        """
        required_columns = {"high", "low", "close"}
        if not required_columns.issubset(data.columns):
            raise ValueError(f"Input data must contain columns: {required_columns}")

        high = data["high"]
        low = data["low"]
        close = data["close"]

        # Calculate recent high/low
        recent_high = high.rolling(window=self.lookback).max()
        recent_low = low.rolling(window=self.lookback).min()

        # Calculate ATR for volatility-based thresholds
        atr = self._calculate_atr(high, low, close)

        # Generate signals
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0

        # Breakout above recent high + ATR threshold
        breakout_up = close > (recent_high + atr * self.atr_multiplier)
        signals.loc[breakout_up, "signal"] = 1

        # Breakout below recent low - ATR threshold
        breakout_down = close < (recent_low - atr * self.atr_multiplier)
        signals.loc[breakout_down, "signal"] = -1

        # Store indicators
        indicators = {
            "recent_high": recent_high,
            "recent_low": recent_low,
            "atr": atr,
            "upper_band": recent_high + atr * self.atr_multiplier,
            "lower_band": recent_low - atr * self.atr_multiplier,
        }

        return StrategyResult(
            signals=signals,
            indicators=indicators,
            params={
                "strategy": "breakout",
                "lookback": self.lookback,
                "atr_period": self.atr_period,
                "atr_multiplier": self.atr_multiplier,
            },
        )


class MachineLearningStrategy:
    """Machine learning-based trading strategy."""

    def __init__(
        self,
        model: Any,
        feature_columns: list,
        target_column: str = "target",
        prediction_threshold: float = 0.5,
        lookahead: int = 1,
    ):
        """
        Initialize the ML strategy.

        Args:
            model: Trained ML model with predict_proba method
            feature_columns: List of feature column names
            target_column: Name of the target column
            prediction_threshold: Probability threshold for signals
            lookahead: Number of periods ahead to predict
        """
        self.model = model
        self.feature_columns = feature_columns
        self.target_column = target_column
        self.prediction_threshold = prediction_threshold
        self.lookahead = lookahead

    def __call__(self, data: pd.DataFrame, **kwargs) -> StrategyResult:
        """
        Generate trading signals using a machine learning model.

        Args:
            data: DataFrame with feature and target columns

        Returns:
            StrategyResult: Contains signals and indicators
        """
        # Check for required columns
        missing_cols = set(self.feature_columns + [self.target_column]) - set(data.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Make predictions
        X = data[self.feature_columns].copy()

        # Handle NaN values (simple forward fill for demonstration)
        X = X.ffill().bfill()

        # Get predicted probabilities
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(X)[:, 1]  # Probability of positive class
        else:
            proba = self.model.predict(X)  # For models without predict_proba

        # Create signals based on prediction threshold
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0
        signals.loc[proba > (1 - self.prediction_threshold), "signal"] = 1  # Buy signal
        signals.loc[proba < self.prediction_threshold, "signal"] = -1  # Sell signal

        # Store indicators
        indicators = {
            "prediction": pd.Series(proba, index=data.index),
            "signal_strength": pd.Series(
                np.abs(proba - 0.5) * 2, index=data.index
            ),  # 0-1 range of confidence
        }

        return StrategyResult(
            signals=signals,
            indicators=indicators,
            params={
                "strategy": "machine_learning",
                "feature_columns": self.feature_columns,
                "target_column": self.target_column,
                "prediction_threshold": self.prediction_threshold,
                "lookahead": self.lookahead,
            },
        )


def create_strategy(strategy_type: str, **kwargs) -> callable:
    """
    Factory function to create a strategy instance.

    Args:
        strategy_type: Type of strategy to create
        **kwargs: Strategy-specific parameters

    Returns:
        callable: Strategy instance
    """
    strategy_map = {
        "mean_reversion": MeanReversionStrategy,
        "momentum": MomentumStrategy,
        "breakout": BreakoutStrategy,
        "machine_learning": MachineLearningStrategy,
    }

    if strategy_type not in strategy_map:
        raise ValueError(
            f"Unknown strategy type: {strategy_type}. "
            f"Available strategies: {list(strategy_map.keys())}"
        )

    return strategy_map[strategy_type](**kwargs)
