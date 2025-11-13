"""Integration tests for data adapters and pipeline."""
from src.feature import build_features
from src.strategy import find_value_bets
from src.tools.synthetic_data import generate_synthetic_fixtures, generate_synthetic_odds


def test_integration_pipeline():
    """Test complete pipeline from data to bet selection."""
    # Generate synthetic data
    fixtures = generate_synthetic_fixtures(n_days=2, games_per_day=3)
    assert len(fixtures) > 0

    fixtures["market_id"].tolist()
    odds = generate_synthetic_odds(fixtures)
    assert len(odds) > 0

    # Build features
    features = build_features(fixtures, odds)
    assert len(features) > 0

    # Add dummy predictions
    features["p_win"] = 0.6

    # Find value bets
    bets = find_value_bets(features, bank=1000.0)

    # Should find some bets (though not guaranteed with random data)
    assert isinstance(bets, list)


def test_synthetic_fixtures_structure():
    """Test synthetic fixtures have required structure."""
    fixtures = generate_synthetic_fixtures(n_days=1, games_per_day=5)

    required_cols = ["market_id", "home", "away", "start", "sport", "league"]
    for col in required_cols:
        assert col in fixtures.columns


def test_synthetic_odds_structure():
    """Test synthetic odds have required structure."""
    fixtures = generate_synthetic_fixtures(n_days=1, games_per_day=2)
    odds = generate_synthetic_odds(fixtures)

    required_cols = ["market_id", "selection", "odds", "provider"]
    for col in required_cols:
        assert col in odds.columns


def test_synthetic_odds_realistic_range():
    """Test synthetic odds are in realistic range."""
    fixtures = generate_synthetic_fixtures(n_days=1, games_per_day=5)
    odds = generate_synthetic_odds(fixtures)

    # Odds should be between 1.01 and 50.0
    assert (odds["odds"] >= 1.01).all()
    assert (odds["odds"] <= 50.0).all()


def test_feature_building_with_synthetic_data():
    """Test feature engineering with synthetic data."""
    fixtures = generate_synthetic_fixtures(n_days=1, games_per_day=3)
    odds = generate_synthetic_odds(fixtures)

    features = build_features(fixtures, odds)

    # Should have more columns than input (due to feature engineering)
    assert len(features.columns) > len(fixtures.columns)

    # Should have numeric features
    numeric_cols = features.select_dtypes(include=["number"]).columns
    assert len(numeric_cols) > 0


def test_end_to_end_with_execution():
    """Test complete flow including execution."""
    from src.db import init_db
    from src.executor import Executor

    init_db()

    # Generate data
    fixtures = generate_synthetic_fixtures(n_days=1, games_per_day=2)
    odds = generate_synthetic_odds(fixtures)

    # Build features
    features = build_features(fixtures, odds)
    features["p_win"] = 0.65

    # Find bets
    bets = find_value_bets(features, bank=500.0)

    # Execute in dry-run
    if bets:
        executor = Executor()
        results = executor.execute_batch(bets, dry_run=True)
        assert len(results) == len(bets)
        assert all(r["status"] == "dry_run" for r in results)
