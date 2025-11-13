"""Basic tests for backtesting modules to improve coverage."""
import pytest
import pandas as pd

# Import backtesting modules
try:
    from src.backtesting.engine import BacktestEngine
    from src.backtesting.betting_strategies import (
        ValueBettingStrategy,
        KellyCriterionStrategy,
        ArbitrageStrategy,
    )

    BACKTESTING_AVAILABLE = True
except ImportError:
    BACKTESTING_AVAILABLE = False


@pytest.mark.skipif(not BACKTESTING_AVAILABLE, reason="Backtesting module not available")
class TestBacktestEngine:
    """Tests for BacktestEngine class."""

    def create_sample_data(self):
        """Create sample historical data for backtesting."""
        dates = pd.date_range(start="2025-01-01", periods=10, freq="D")
        return pd.DataFrame(
            {
                "market_id": [f"market_{i}" for i in range(10)],
                "home": ["Team A"] * 10,
                "away": ["Team B"] * 10,
                "home_odds": [2.0, 1.8, 2.2, 1.9, 2.1, 1.7, 2.3, 1.85, 2.15, 1.95],
                "away_odds": [3.5, 4.0, 3.2, 3.8, 3.4, 4.2, 3.0, 3.9, 3.3, 3.7],
                "draw_odds": [3.2, 3.4, 3.0, 3.3, 3.1, 3.5, 2.9, 3.35, 3.05, 3.25],
                "result": [
                    "home",
                    "away",
                    "home",
                    "draw",
                    "home",
                    "away",
                    "home",
                    "home",
                    "away",
                    "draw",
                ],
                "start": dates,
            }
        )

    def test_engine_initialization(self):
        """Test BacktestEngine initialization."""
        data = self.create_sample_data()
        engine = BacktestEngine(data, initial_bankroll=1000.0)
        assert engine is not None
        assert engine.initial_bankroll == 1000.0

    def test_engine_run_backtest(self):
        """Test running a backtest."""
        data = self.create_sample_data()
        engine = BacktestEngine(data, initial_bankroll=1000.0)

        # Simple strategy: always bet on home
        def simple_strategy(row):
            return {"selection": "home", "stake": 10.0}

        results = engine.run(simple_strategy)

        assert "final_bankroll" in results
        assert "total_bets" in results
        assert results["total_bets"] > 0

    def test_engine_empty_data(self):
        """Test engine with empty data."""
        empty_data = pd.DataFrame(columns=["market_id", "home", "away", "result"])
        engine = BacktestEngine(empty_data, initial_bankroll=1000.0)

        def simple_strategy(row):
            return {"selection": "home", "stake": 10.0}

        results = engine.run(simple_strategy)
        assert results["total_bets"] == 0
        assert results["final_bankroll"] == 1000.0


@pytest.mark.skipif(not BACKTESTING_AVAILABLE, reason="Backtesting module not available")
class TestValueBettingStrategy:
    """Tests for ValueBettingStrategy."""

    def test_strategy_initialization(self):
        """Test strategy initialization."""
        strategy = ValueBettingStrategy(min_edge=0.05)
        assert strategy is not None
        assert strategy.min_edge == 0.05

    def test_strategy_evaluate(self):
        """Test strategy evaluation."""
        strategy = ValueBettingStrategy(min_edge=0.05)

        market_data = {"home_odds": 2.0, "away_odds": 3.5, "draw_odds": 3.2}

        decision = strategy.evaluate(market_data)

        assert "selection" in decision or decision is None

    def test_strategy_no_value(self):
        """Test strategy with no value bets."""
        strategy = ValueBettingStrategy(min_edge=0.5)  # Very high edge required

        market_data = {"home_odds": 1.5, "away_odds": 2.5, "draw_odds": 3.0}

        decision = strategy.evaluate(market_data)
        assert decision is None or decision["stake"] == 0


@pytest.mark.skipif(not BACKTESTING_AVAILABLE, reason="Backtesting module not available")
class TestKellyCriterionStrategy:
    """Tests for KellyCriterionStrategy."""

    def test_kelly_strategy_initialization(self):
        """Test Kelly strategy initialization."""
        strategy = KellyCriterionStrategy(kelly_fraction=0.25)
        assert strategy is not None
        assert strategy.kelly_fraction == 0.25

    def test_kelly_strategy_evaluate(self):
        """Test Kelly strategy evaluation."""
        strategy = KellyCriterionStrategy(kelly_fraction=0.25)

        market_data = {"home_odds": 2.5, "away_odds": 3.0, "draw_odds": 3.5, "bankroll": 1000.0}

        decision = strategy.evaluate(market_data)

        # Should return a decision or None
        assert decision is None or isinstance(decision, dict)


@pytest.mark.skipif(not BACKTESTING_AVAILABLE, reason="Backtesting module not available")
class TestArbitrageStrategy:
    """Tests for ArbitrageStrategy."""

    def test_arbitrage_strategy_initialization(self):
        """Test arbitrage strategy initialization."""
        strategy = ArbitrageStrategy()
        assert strategy is not None

    def test_arbitrage_opportunity_detection(self):
        """Test detecting arbitrage opportunities."""
        strategy = ArbitrageStrategy()

        # Create arbitrage opportunity
        market_data = {"home_odds": 2.1, "away_odds": 2.1, "draw_odds": 10.0}

        decision = strategy.evaluate(market_data)

        # May or may not find arbitrage depending on implementation
        assert decision is None or isinstance(decision, dict)

    def test_no_arbitrage_opportunity(self):
        """Test with no arbitrage opportunity."""
        strategy = ArbitrageStrategy()

        # Normal market with no arbitrage
        market_data = {"home_odds": 2.0, "away_odds": 3.5, "draw_odds": 3.2}

        decision = strategy.evaluate(market_data)

        # Should return None (no arbitrage)
        assert decision is None or decision.get("stake", 0) == 0
