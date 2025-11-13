"""Basic tests for analysis modules to improve coverage."""
import numpy as np
import pandas as pd
import pytest

# Import analysis modules
try:
    from src.analysis.performance_utils import (
        PerformanceAnalyzer,
        calculate_max_drawdown,
        calculate_roi,
        calculate_sharpe_ratio,
        calculate_win_rate,
    )

    PERFORMANCE_AVAILABLE = True
except ImportError:
    PERFORMANCE_AVAILABLE = False


@pytest.mark.skipif(not PERFORMANCE_AVAILABLE, reason="Performance module not available")
class TestPerformanceMetrics:
    """Tests for performance calculation functions."""

    def test_calculate_roi_positive(self):
        """Test ROI calculation with profit."""
        roi = calculate_roi(total_profit=500, total_stake=1000)
        assert roi == 50.0

    def test_calculate_roi_negative(self):
        """Test ROI calculation with loss."""
        roi = calculate_roi(total_profit=-200, total_stake=1000)
        assert roi == -20.0

    def test_calculate_roi_zero_stake(self):
        """Test ROI with zero stake."""
        roi = calculate_roi(total_profit=100, total_stake=0)
        assert roi == 0.0

    def test_calculate_win_rate(self):
        """Test win rate calculation."""
        win_rate = calculate_win_rate(wins=7, total_bets=10)
        assert win_rate == 70.0

    def test_calculate_win_rate_no_bets(self):
        """Test win rate with no bets."""
        win_rate = calculate_win_rate(wins=0, total_bets=0)
        assert win_rate == 0.0

    def test_calculate_sharpe_ratio(self):
        """Test Sharpe ratio calculation."""
        returns = [0.05, -0.02, 0.03, 0.01, -0.01]
        sharpe = calculate_sharpe_ratio(returns)
        assert isinstance(sharpe, float)

    def test_calculate_sharpe_ratio_empty(self):
        """Test Sharpe ratio with empty returns."""
        sharpe = calculate_sharpe_ratio([])
        assert sharpe == 0.0

    def test_calculate_max_drawdown(self):
        """Test max drawdown calculation."""
        equity = [1000, 1100, 1050, 900, 950, 1000]
        max_dd = calculate_max_drawdown(equity)
        # Max drawdown from 1100 to 900 is 18.18% (returned as positive)
        assert max_dd > 0  # Returns positive value
        assert max_dd > 15  # Should be significant (around 18%)sonable

    def test_calculate_max_drawdown_no_drawdown(self):
        """Test max drawdown with only gains."""
        equity_curve = [1000, 1100, 1200, 1300]
        max_dd = calculate_max_drawdown(equity_curve)
        assert max_dd == 0.0


@pytest.mark.skipif(not PERFORMANCE_AVAILABLE, reason="Performance module not available")
class TestPerformanceAnalyzer:
    """Tests for PerformanceAnalyzer class."""

    def create_sample_bets(self):
        """Create sample bet data for testing."""
        return pd.DataFrame(
            {
                "stake": [100, 100, 100, 100, 100],
                "odds": [2.0, 1.5, 3.0, 2.5, 1.8],
                "result": ["win", "loss", "win", "loss", "win"],
                "profit_loss": [100, -100, 200, -100, 80],
                "placed_at": pd.date_range(start="2025-01-01", periods=5, freq="D"),
            }
        )

    def test_analyzer_initialization(self):
        """Test PerformanceAnalyzer initialization."""
        bets_df = self.create_sample_bets()
        analyzer = PerformanceAnalyzer(bets_df)
        assert analyzer is not None
        assert len(analyzer.bets_df) == 5

    def test_analyzer_calculate_metrics(self):
        """Test calculating performance metrics."""
        bets_df = self.create_sample_bets()
        analyzer = PerformanceAnalyzer(bets_df)
        metrics = analyzer.calculate_metrics()

        assert "total_bets" in metrics
        assert "win_rate" in metrics
        assert "roi" in metrics
        assert metrics["total_bets"] == 5

    def test_analyzer_empty_dataframe(self):
        """Test analyzer with empty dataframe."""
        empty_df = pd.DataFrame(columns=["stake", "odds", "result", "profit_loss"])
        analyzer = PerformanceAnalyzer(empty_df)
        metrics = analyzer.calculate_metrics()

        assert metrics["total_bets"] == 0
        assert metrics["win_rate"] == 0.0

    def test_analyzer_get_equity_curve(self):
        """Test equity curve generation."""
        bets_df = self.create_sample_bets()
        analyzer = PerformanceAnalyzer(bets_df)
        equity = analyzer.get_equity_curve()

        assert isinstance(equity, (list, np.ndarray, pd.Series))
        assert len(equity) > 0
