"""Extended tests for the betting strategy module."""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch
from src.strategy import (
    find_value_bets,
    apply_bet_filters,
    filter_bets_by_sharpe,
    diversify_bets,
)


# Mock the database and risk modules
@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch("src.strategy.get_daily_loss", return_value=0), patch(
        "src.strategy.get_open_bets_count", return_value=0
    ), patch("src.strategy.logger"), patch(
        "src.strategy.validate_bet", return_value=(True, "")
    ) as mock_validate_bet, patch(
        "src.strategy.stake_from_bankroll", return_value=10.0
    ), patch(
        "src.strategy.calculate_expected_value"
    ) as mock_ev_calc:
        # Setup mock EV calculation: p*odds - 1
        mock_ev_calc.side_effect = lambda p, odds: p * odds - 1
        yield mock_validate_bet


def test_find_value_bets_skip_invalid_values():
    """Test that find_value_bets skips rows with invalid values."""
    # Create test data with various invalid values
    data = pd.DataFrame(
        {
            "market_id": ["m1", "m2", "m3", "m4", "m5"],
            "p_win": [0.6, np.nan, 0.5, 0.7, 0.8],  # m2 has NaN probability
            "odds": [2.0, 2.5, np.nan, 1.8, 1.5],  # m3 has NaN odds
            "home": ["TeamA", "TeamB", "TeamC", "TeamD", "TeamE"],
            "away": ["TeamB", "TeamC", "TeamD", "TeamE", "TeamF"],
        }
    )

    # Call the function
    bets = find_value_bets(data, proba_col="p_win", odds_col="odds", bank=1000.0, min_ev=0.0)

    # Should only process m1, m4, m5 (m2 and m3 have invalid values)
    assert len(bets) == 3
    assert all(bet["market_id"] in ["m1", "m4", "m5"] for bet in bets)


def test_find_value_bets_odds_filtering():
    """Test that find_value_bets respects odds filtering."""
    # Create test data with various odds
    data = pd.DataFrame(
        {
            "market_id": ["m1", "m2", "m3", "m4"],
            "p_win": [0.6, 0.6, 0.6, 0.6],
            "odds": [1.5, 2.0, 3.0, 4.0],
            "home": ["TeamA", "TeamB", "TeamC", "TeamD"],
            "away": ["TeamB", "TeamC", "TeamD", "TeamE"],
        }
    )

    # Mock validate_bet to always return True and stake_from_bankroll to return a valid stake
    with patch("src.strategy.validate_bet", return_value=(True, "")), patch(
        "src.strategy.stake_from_bankroll", return_value=10.0
    ):
        # Test with default odds range (1.01-100.0)
        bets = find_value_bets(
            data,
            proba_col="p_win",
            odds_col="odds",
            bank=1000.0,
            min_ev=-1.0,  # Very low EV threshold to ensure all bets pass
        )
        assert len(bets) == 4  # All 4 should pass

        # Test with custom odds range
        bets = find_value_bets(
            data,
            proba_col="p_win",
            odds_col="odds",
            bank=1000.0,
            min_odds=1.5,
            max_odds=3.0,
            min_ev=-1.0,
        )
        # Only m1 (1.5), m2 (2.0), m3 (3.0) should be included (m4 has odds 4.0 > max_odds 3.0)
        assert len(bets) == 3
        assert {bet["market_id"] for bet in bets} == {"m1", "m2", "m3"}
        assert all(1.5 <= bet["odds"] <= 3.0 for bet in bets)


def test_find_value_bets_zero_stake():
    """Test that find_value_bets skips bets with zero or negative stake."""
    # Create test data
    data = pd.DataFrame(
        {
            "market_id": ["m1", "m2"],
            "p_win": [0.6, 0.6],
            "odds": [2.0, 2.0],
            "home": ["TeamA", "TeamB"],
            "away": ["TeamB", "TeamC"],
        }
    )

    # Mock stake_from_bankroll to return 0 for the second bet
    with patch("src.strategy.stake_from_bankroll", side_effect=[10.0, 0.0]):
        bets = find_value_bets(data, proba_col="p_win", odds_col="odds", bank=1000.0)
        assert len(bets) == 1  # Only the first bet should be included
        assert bets[0]["market_id"] == "m1"


def test_find_value_bets_missing_columns():
    """Test that find_value_bets handles missing optional columns."""
    # Create test data with missing optional columns
    data = pd.DataFrame(
        {
            "market_id": ["m1", "m2"],
            "p_win": [0.6, 0.7],
            "odds": [2.0, 2.5],
            # Missing 'home', 'away', 'league' columns
        }
    )

    # Call the function - should not raise an exception
    bets = find_value_bets(data, proba_col="p_win", odds_col="odds", bank=1000.0)

    # Should process both bets with default values for missing columns
    assert len(bets) == 2
    for bet in bets:
        assert bet["home"] == "Unknown"
        assert bet["away"] == "Unknown"
        assert bet["league"] == "Unknown"


def test_apply_bet_filters():
    """Test the apply_bet_filters function with all filters."""
    # Create test bets with different properties
    bets = [
        {
            "market_id": "m1",
            "odds": 2.0,
            "p": 0.6,  # EV = 0.2
            "stake": 50.0,
            "ev": 0.2,
            "sharpe": 0.6,  # Good sharpe
            "league": "Premier League",  # Only one in this league
        },
        {
            "market_id": "m2",
            "odds": 3.0,
            "p": 0.5,  # EV = 0.5
            "stake": 50.0,
            "ev": 0.5,
            "sharpe": 0.4,  # Low sharpe - should be filtered out
            "league": "La Liga",
        },
        {
            "market_id": "m3",
            "odds": 1.8,
            "p": 0.4,  # EV = -0.28 (below min_ev)
            "stake": 50.0,
            "ev": -0.28,  # Negative EV - should be filtered out
            "sharpe": 0.8,
            "league": "La Liga",
        },
        {
            "market_id": "m4",
            "odds": 2.5,
            "p": 0.6,  # EV = 0.5
            "stake": 50.0,
            "ev": 0.5,
            "sharpe": 0.7,  # Good sharpe
            "league": "La Liga",
        },
    ]

    # Mock the filter functions
    with patch("src.strategy.filter_bets_by_sharpe") as mock_sharpe, patch(
        "src.strategy.filter_bets_by_confidence"
    ) as mock_confidence, patch("src.strategy.diversify_bets") as mock_diversify:
        # Setup mocks
        # Filter out bets with sharpe < 0.5
        mock_sharpe.side_effect = lambda b, _: [bet for bet in b if bet.get("sharpe", 0) >= 0.5]
        # No filtering by confidence
        mock_confidence.side_effect = lambda b, _: b
        # Just return first 2 bets that pass other filters
        mock_diversify.side_effect = lambda b, *_: b[:2]

        # Apply filters
        filtered = apply_bet_filters(
            bets,
            min_ev=0.1,  # Exclude m3 (ev = -0.28)
            min_sharpe=0.5,  # Exclude m2 (sharpe = 0.4)
            min_confidence=0.4,  # All bets have p >= 0.4
            max_per_league=2,  # Allow 2 bets per league
            max_total=4,  # No total limit
        )

        # After filtering, we should have:
        # - m1: passes all filters (Premier League)
        # - m2: filtered out by sharpe (0.4 < 0.5)
        # - m3: filtered out by EV (-0.28 < 0.1)
        # - m4: passes all filters (La Liga)
        # Then diversify_bets will return the first 2 (m1 and m4)
        assert len(filtered) == 2
        assert {bet["market_id"] for bet in filtered} == {"m1", "m4"}


def test_apply_bet_filters_empty_input():
    """Test apply_bet_filters with empty input."""
    result = apply_bet_filters([], min_ev=0.0, min_sharpe=0.0, min_confidence=0.0)
    assert result == []


def test_find_value_bets_nan_handling():
    """Test handling of NaN values in find_value_bets."""
    # Create test data with NaN values
    data = pd.DataFrame(
        {
            "market_id": ["m1", "m2", "m3"],
            "p_win": [0.6, np.nan, 0.5],  # m2 has NaN probability
            "odds": [2.0, 2.5, np.nan],  # m3 has NaN odds
            "home": ["TeamA", "TeamB", "TeamC"],
            "away": ["TeamB", "TeamC", "TeamD"],
        }
    )

    with patch("src.strategy.validate_bet", return_value=(True, "")), patch(
        "src.strategy.stake_from_bankroll", return_value=10.0
    ):
        bets = find_value_bets(data, proba_col="p_win", odds_col="odds", bank=1000.0, min_ev=-1.0)
        # Only m1 should be included (m2 has NaN prob, m3 has NaN odds)
        assert len(bets) == 1
        assert bets[0]["market_id"] == "m1"


def test_find_value_bets_market_selection_defaults():
    """Test default market_id and selection values in find_value_bets."""
    data = pd.DataFrame({"p_win": [0.6], "odds": [2.0], "home": ["TeamA"], "away": ["TeamB"]})

    with patch("src.strategy.validate_bet", return_value=(True, "")), patch(
        "src.strategy.stake_from_bankroll", return_value=10.0
    ):
        bets = find_value_bets(data, proba_col="p_win", odds_col="odds", bank=1000.0)
        assert len(bets) == 1
        assert bets[0]["market_id"].startswith("market_")
        assert bets[0]["selection"] == "home"


def test_filter_bets_by_sharpe():
    """Test the filter_bets_by_sharpe function."""
    bets = [
        {"p": 0.6, "odds": 2.0, "stake": 10.0, "ev": 0.2, "market_id": "m1"},
        {"p": 0.5, "odds": 3.0, "stake": 10.0, "ev": 0.5, "market_id": "m2"},
    ]

    # Mock the calculate_sharpe_ratio function from src.risk
    with patch("src.risk.calculate_sharpe_ratio") as mock_sharpe:
        # Set up the mock to return different values for each call
        mock_sharpe.side_effect = [0.4, 0.6]

        # Call the function under test
        filtered = filter_bets_by_sharpe(bets, min_sharpe=0.5)

        # Verify the results
        assert len(filtered) == 1
        assert filtered[0]["market_id"] == "m2"
        assert filtered[0]["sharpe"] == 0.6

        # Verify calculate_sharpe_ratio was called with the right arguments
        assert mock_sharpe.call_count == 2
        mock_sharpe.assert_any_call(0.6, 2.0)  # First bet
        mock_sharpe.assert_any_call(0.5, 3.0)  # Second bet


def test_diversify_bets():
    """Test the diversify_bets function."""
    bets = [
        {"market_id": "m1", "league": "EPL", "ev": 0.3},
        {"market_id": "m2", "league": "EPL", "ev": 0.2},
        {"market_id": "m3", "league": "LaLiga", "ev": 0.25},
        {"market_id": "m4", "league": "EPL", "ev": 0.15},
        {"market_id": "m5", "league": "LaLiga", "ev": 0.1},
    ]

    # Test max_per_league limit
    diversified = diversify_bets(bets, max_per_league=1, max_total=10)
    assert len(diversified) == 2  # 1 from EPL, 1 from LaLiga

    # Test max_total limit
    diversified = diversify_bets(bets, max_per_league=2, max_total=3)
    assert len(diversified) == 3  # 2 from EPL, 1 from LaLiga
