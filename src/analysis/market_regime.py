"""Market regime detection and analysis."""
import warnings
from enum import Enum
from typing import Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

# Suppress scikit-learn warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


class MarketRegime(Enum):
    """Market regime classifications."""

    TRENDING_UP = "Trending Up"
    TRENDING_DOWN = "Trending Down"
    VOLATILE = "High Volatility"
    RANGING = "Ranging"
    CRASH = "Market Crash"
    RECOVERY = "Recovery"
    BREAKOUT = "Breakout"
    BREAKDOWN = "Breakdown"
    LOW_VOLATILITY = "Low Volatility"
    HIGH_VOLATILITY = "High Volatility"


class MarketRegimeDetector:
    """
    Detects and classifies market regimes using statistical and machine learning methods.

    This class provides functionality to identify different market conditions such as
    trending, ranging, volatile, and crash regimes using a combination of technical
    indicators and unsupervised learning algorithms.
    """

    def __init__(self, n_regimes: int = 4, method: str = "gmm", lookback: int = 21):
        """
        Initialize the market regime detector.

        Args:
            n_regimes: Number of market regimes to identify (default: 4)
            method: Clustering method ('gmm' for Gaussian Mixture Model or 'kmeans' for K-Means)
            lookback: Number of periods to use for feature calculation (default: 21)
        """
        self.n_regimes = n_regimes
        self.method = method.lower()
        self.lookback = lookback
        self.model = None
        self.scaler = StandardScaler()
        self.pca = None
        self.regime_map = {}
        self.feature_importances_ = None

    def fit(
        self, prices: Union[pd.Series, pd.DataFrame], volume: Optional[pd.Series] = None
    ) -> "MarketRegimeDetector":
        """
        Fit the market regime detection model to historical price data.

        Args:
            prices: Series or DataFrame of price data (if DataFrame, should have 'close' column)
            volume: Optional series of trading volume data

        Returns:
            self: Returns the instance itself
        """
        if isinstance(prices, pd.DataFrame) and "close" in prices.columns:
            close_prices = prices["close"]
        else:
            close_prices = pd.Series(prices) if not isinstance(prices, pd.Series) else prices

        # Calculate features
        features = self._calculate_features(close_prices, volume)

        # Scale features
        scaled_features = self.scaler.fit_transform(features)

        # Reduce dimensionality if needed
        if scaled_features.shape[1] > 5:  # Only use PCA if we have many features
            self.pca = PCA(n_components=min(5, scaled_features.shape[1]))
            scaled_features = self.pca.fit_transform(scaled_features)

        # Fit the model
        if self.method == "gmm":
            self.model = GaussianMixture(
                n_components=self.n_regimes, random_state=42, covariance_type="full"
            )
        else:  # Default to K-Means
            self.model = KMeans(n_clusters=self.n_regimes, random_state=42, n_init=10)

        self.model.fit(scaled_features)

        # Map clusters to interpretable regimes
        self._map_regimes(features, close_prices)

        return self

    def predict(
        self, prices: Union[pd.Series, pd.DataFrame], volume: Optional[pd.Series] = None
    ) -> pd.Series:
        """
        Predict market regimes for the given price data.

        Args:
            prices: Series or DataFrame of price data
            volume: Optional series of trading volume data

        Returns:
            Series of regime labels
        """
        if self.model is None:
            raise RuntimeError("Model has not been fitted. Call fit() first.")

        if isinstance(prices, pd.DataFrame) and "close" in prices.columns:
            close_prices = prices["close"]
        else:
            close_prices = pd.Series(prices) if not isinstance(prices, pd.Series) else prices

        # Calculate features
        features = self._calculate_features(close_prices, volume)

        # Scale features
        scaled_features = self.scaler.transform(features)

        # Apply PCA if it was used during training
        if self.pca is not None:
            scaled_features = self.pca.transform(scaled_features)

        # Predict regimes
        if self.method == "gmm":
            regimes = self.model.predict(scaled_features)
            probabilities = self.model.predict_proba(scaled_features)
            confidence = np.max(probabilities, axis=1)
        else:  # K-Means
            regimes = self.model.predict(scaled_features)
            distances = self.model.transform(scaled_features)
            confidence = 1 / (1 + np.min(distances, axis=1))  # Convert distance to confidence

        # Map numeric regimes to interpretable labels
        regime_labels = pd.Series(
            [self.regime_map.get(r, MarketRegime.RANGING.value) for r in regimes],
            index=close_prices.index,
            name="regime",
        )

        # Add confidence scores
        confidence_series = pd.Series(confidence, index=close_prices.index, name="confidence")

        return pd.concat([regime_labels, confidence_series], axis=1)

    def _calculate_features(
        self, prices: pd.Series, volume: Optional[pd.Series] = None
    ) -> pd.DataFrame:
        """Calculate technical features for regime detection."""
        if not isinstance(prices, pd.Series):
            prices = pd.Series(prices)

        # Calculate returns and volatility
        returns = prices.pct_change().dropna()
        np.log1p(returns)

        # Initialize features DataFrame
        features = {}

        # 1. Trend features
        features["sma_20"] = prices.rolling(window=20).mean()
        features["sma_50"] = prices.rolling(window=50).mean()
        features["sma_200"] = prices.rolling(window=200).mean()
        features["ema_12"] = prices.ewm(span=12, adjust=False).mean()
        features["ema_26"] = prices.ewm(span=26, adjust=False).mean()

        # MACD
        macd = features["ema_12"] - features["ema_26"]
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        features["macd_hist"] = macd - macd_signal

        # 2. Momentum features
        features["rsi"] = self._calculate_rsi(prices, 14)
        features["stoch_k"], features["stoch_d"] = self._calculate_stochastic(prices, 14, 3)
        features["adx"] = self._calculate_adx(prices, 14)

        # 3. Volatility features
        features["atr"] = self._calculate_atr(prices, 14)
        (
            features["bb_upper"],
            features["bb_middle"],
            features["bb_lower"],
        ) = self._calculate_bollinger_bands(prices, 20)

        # 4. Volume features
        if volume is not None:
            volume = pd.Series(volume, index=prices.index)
            features["volume_ma"] = volume.rolling(window=20).mean()
            features["volume_ratio"] = volume / features["volume_ma"]
            features["obv"] = self._calculate_obv(prices, volume)

        # 5. Statistical features
        features["returns"] = returns
        features["volatility"] = returns.rolling(window=self.lookback).std()
        features["skewness"] = returns.rolling(window=self.lookback).skew()
        features["kurtosis"] = returns.rolling(window=self.lookback).kurt()

        # 6. Price-based features
        features["close_ma_ratio"] = prices / features["sma_20"]
        features["high_low_ratio"] = prices.rolling(window=self.lookback).apply(
            lambda x: x.max() / x.min() - 1 if len(x) == self.lookback else np.nan
        )

        # Convert to DataFrame and drop NA values
        features_df = pd.DataFrame(features).dropna()

        # Ensure we have enough data
        if len(features_df) < self.lookback * 2:
            raise ValueError(
                "Insufficient data points. Need at least "
                f"{self.lookback * 2} periods after feature calculation."
            )

        return features_df

    def _map_regimes(self, features: pd.DataFrame, prices: pd.Series) -> None:
        """Map numeric clusters to interpretable market regimes."""
        if self.model is None:
            return

        # Get cluster centers or means
        if self.method == "gmm":
            centers = self.model.means_
        else:  # K-Means
            centers = self.model.cluster_centers_

        # Calculate statistics for each cluster
        cluster_stats = []
        for i in range(self.n_regimes):
            if self.method == "gmm":
                # For GMM, we can use the means as cluster centers
                center = centers[i]
            else:  # K-Means
                center = centers[i]

            # Get the indices of points in this cluster
            cluster_indices = self.model.labels_ == i

            # Calculate statistics for this cluster
            stats = {
                "cluster": i,
                "mean_return": features.iloc[cluster_indices]["returns"].mean(),
                "volatility": features.iloc[cluster_indices]["returns"].std(),
                "mean_volume": features.iloc[cluster_indices].get("volume_ma", pd.Series(0)).mean(),
                "count": cluster_indices.sum(),
                "center": center,
            }
            cluster_stats.append(stats)

        # Sort clusters by return/volatility ratio (a simple way to identify regimes)
        cluster_stats.sort(
            key=lambda x: x["mean_return"] / (x["volatility"] + 1e-10)
            if x["volatility"] > 0
            else -np.inf,
            reverse=True,
        )

        # Map clusters to regimes based on their characteristics
        self.regime_map = {}
        regime_types = [
            MarketRegime.TRENDING_UP.value,  # High return, medium volatility
            MarketRegime.TRENDING_DOWN.value,  # Low return, medium volatility
            MarketRegime.VOLATILE.value,  # High volatility
            MarketRegime.RANGING.value,  # Low volatility, near-zero return
            MarketRegime.CRASH.value,  # Very low return, high volatility
            MarketRegime.RECOVERY.value,  # High return after crash
            MarketRegime.BREAKOUT.value,  # Sudden high return
            MarketRegime.BREAKDOWN.value,  # Sudden low return
            MarketRegime.LOW_VOLATILITY.value,  # Very low volatility
            MarketRegime.HIGH_VOLATILITY.value,  # Very high volatility
        ]

        # Assign the most appropriate regime types based on sorted clusters
        for i, stats in enumerate(cluster_stats):
            if i < len(regime_types):
                self.regime_map[stats["cluster"]] = regime_types[i]
            else:
                # If we have more clusters than regime types, assign the closest matching regime
                self.regime_map[stats["cluster"]] = self._get_closest_regime(
                    stats["mean_return"], stats["volatility"], stats.get("mean_volume", 0)
                )

    def _get_closest_regime(self, mean_return: float, volatility: float, volume: float = 0) -> str:
        """Determine the closest matching regime based on return and volatility."""
        # Define characteristics of each regime
        regime_chars = {
            MarketRegime.TRENDING_UP.value: {"return": 0.001, "vol": 0.01, "vol_weight": 0.5},
            MarketRegime.TRENDING_DOWN.value: {"return": -0.001, "vol": 0.01, "vol_weight": 0.5},
            MarketRegime.VOLATILE.value: {"return": 0.0, "vol": 0.03, "vol_weight": 0.5},
            MarketRegime.RANGING.value: {"return": 0.0, "vol": 0.005, "vol_weight": 0.5},
            MarketRegime.CRASH.value: {"return": -0.02, "vol": 0.05, "vol_weight": 0.5},
            MarketRegime.RECOVERY.value: {"return": 0.02, "vol": 0.04, "vol_weight": 0.5},
            MarketRegime.BREAKOUT.value: {"return": 0.015, "vol": 0.02, "vol_weight": 0.5},
            MarketRegime.BREAKDOWN.value: {"return": -0.015, "vol": 0.02, "vol_weight": 0.5},
            MarketRegime.LOW_VOLATILITY.value: {"return": 0.0, "vol": 0.002, "vol_weight": 0.5},
            MarketRegime.HIGH_VOLATILITY.value: {"return": 0.0, "vol": 0.1, "vol_weight": 0.5},
        }

        # Calculate distances to each regime
        distances = {}
        for regime, chars in regime_chars.items():
            return_dist = (mean_return - chars["return"]) ** 2
            vol_dist = (volatility - chars["vol"]) ** 2 * chars["vol_weight"]
            distances[regime] = np.sqrt(return_dist + vol_dist)

        # Return the closest regime
        return min(distances.items(), key=lambda x: x[1])[0]

    # Technical indicator helper methods
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index (RSI)."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calculate_stochastic(
        prices: pd.Series, k_period: int = 14, d_period: int = 3
    ) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic Oscillator (%K and %D)."""
        low_min = prices.rolling(window=k_period).min()
        high_max = prices.rolling(window=k_period).max()
        k = 100 * ((prices - low_min) / (high_max - low_min))
        d = k.rolling(window=d_period).mean()
        return k, d

    @staticmethod
    def _calculate_adx(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Average Directional Index (ADX)."""
        if not isinstance(prices, pd.Series):
            prices = pd.Series(prices)

        high = prices.rolling(window=2).max()
        low = prices.rolling(window=2).min()
        close = prices

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        plus_dm = high.diff()
        minus_dm = low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = abs(minus_dm)

        tr_smooth = tr.rolling(window=period).sum()
        plus_dm_smooth = plus_dm.rolling(window=period).sum()
        minus_dm_smooth = minus_dm.rolling(window=period).sum()

        plus_di = 100 * plus_dm_smooth / tr_smooth
        minus_di = 100 * minus_dm_smooth / tr_smooth

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx

    @staticmethod
    def _calculate_atr(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Average True Range (ATR)."""
        if not isinstance(prices, pd.Series):
            prices = pd.Series(prices)

        high = prices.rolling(window=2).max()
        low = prices.rolling(window=2).min()
        close = prices.shift(1)

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        return atr

    @staticmethod
    def _calculate_bollinger_bands(
        prices: pd.Series, period: int = 20, num_std: float = 2
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands."""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()

        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)

        return upper_band, sma, lower_band

    @staticmethod
    def _calculate_obv(prices: pd.Series, volume: pd.Series) -> pd.Series:
        """Calculate On-Balance Volume (OBV)."""
        if not isinstance(prices, pd.Series):
            prices = pd.Series(prices)
        if not isinstance(volume, pd.Series):
            volume = pd.Series(volume)

        obv = pd.Series(index=prices.index, dtype=float)
        obv.iloc[0] = volume.iloc[0] if len(volume) > 0 else 0

        for i in range(1, len(prices)):
            if prices.iloc[i] > prices.iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] + volume.iloc[i]
            elif prices.iloc[i] < prices.iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] - volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i - 1]

        return obv


# Example usage
if __name__ == "__main__":
    # Generate sample price data
    np.random.seed(42)
    n_periods = 1000
    dates = pd.date_range(start="2020-01-01", periods=n_periods, freq="D")

    # Create different market regimes
    trend_up = np.cumsum(np.random.normal(0.001, 0.01, 200)) + 100
    trend_down = np.cumsum(np.random.normal(-0.0005, 0.008, 200)) + trend_up[-1]
    volatile = np.cumsum(np.random.normal(0.0001, 0.02, 200)) + trend_down[-1]
    ranging = np.cumsum(np.random.normal(0.0001, 0.005, 200)) + volatile[-1]
    crash = np.cumsum(np.random.normal(-0.005, 0.03, 200)) + ranging[-1]

    # Combine all regimes
    prices = pd.Series(
        np.concatenate([trend_up, trend_down, volatile, ranging, crash]), index=dates
    )

    # Add some noise
    prices += np.random.normal(0, 0.1, len(prices))

    # Initialize and fit the detector
    detector = MarketRegimeDetector(n_regimes=5)
    detector.fit(prices)

    # Predict regimes
    results = detector.predict(prices)

    # Print results
    print("\nDetected Regimes:")
    print(results["regime"].value_counts())

    # Plot results
    import matplotlib.pyplot as plt

    plt.figure(figsize=(14, 8))

    # Plot price and regimes
    for regime in results["regime"].unique():
        mask = results["regime"] == regime
        plt.plot(prices.index[mask], prices[mask], ".", label=regime, alpha=0.6)

    plt.title("Market Regime Detection")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()
