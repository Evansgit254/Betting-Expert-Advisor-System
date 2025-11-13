"""Tests for betting strategy module."""
import pandas as pd
from src.strategy import (
    find_value_bets,
    filter_bets_by_sharpe,
    filter_bets_by_confidence,
    diversify_bets,
)


def test_find_value_bets_returns_list():
    """Test that find_value_bets returns a list."""
    data = pd.DataFrame(
        {
            "market_id": ["m1", "m2"],
            "p_win": [0.6, 0.7],
            "odds": [2.0, 2.5],
            "home": ["TeamA", "TeamC"],
            "away": ["TeamB", "TeamD"],
            "selection": ["home", "home"],
        }
    )

    bets = find_value_bets(data, bank=1000.0)
    assert isinstance(bets, list)


def test_find_value_bets_positive_ev_only():
    """Test that only positive EV bets are returned."""
    data = pd.DataFrame(
        {
            "market_id": ["m1", "m2", "m3"],
            "p_win": [0.6, 0.4, 0.55],  # m1 has edge, m2 doesn't, m3 marginal
            "odds": [2.0, 2.0, 2.0],
            "home": ["A", "B", "C"],
            "away": ["D", "E", "F"],
            "selection": ["home", "home", "home"],
        }
    )

    bets = find_value_bets(data, bank=1000.0, min_ev=0.0)

    # Should only include bets with positive EV
    for bet in bets:
        assert bet["ev"] > 0


def test_find_value_bets_sorted_by_ev():
    """Test that bets are sorted by expected value."""
    data = pd.DataFrame(
        {
            "market_id": ["m1", "m2", "m3"],
            "p_win": [0.6, 0.7, 0.65],
            "odds": [2.0, 2.2, 2.1],
            "home": ["A", "B", "C"],
            "away": ["D", "E", "F"],
            "selection": ["home", "home", "home"],
        }
    )

    bets = find_value_bets(data, bank=1000.0)

    if len(bets) > 1:
        # Check descending order
        evs = [bet["ev"] for bet in bets]
        assert evs == sorted(evs, reverse=True)


def test_find_value_bets_empty_dataframe():
    """Test handling of empty DataFrame."""
    data = pd.DataFrame()
    bets = find_value_bets(data, bank=1000.0)
    assert bets == []


def test_find_value_bets_respects_min_ev():
    """Test minimum EV threshold."""
    data = pd.DataFrame(
        {
            "market_id": ["m1", "m2"],
            "p_win": [0.55, 0.7],  # m1 has small edge, m2 has large edge
            "odds": [2.0, 2.0],
            "home": ["A", "B"],
            "away": ["C", "D"],
            "selection": ["home", "home"],
        }
    )

    bets = find_value_bets(data, bank=1000.0, min_ev=0.15)

    # Only high-EV bets should be included
    assert all(bet["ev"] >= 0.15 for bet in bets)


def test_filter_bets_by_sharpe():
    """Test Sharpe ratio filtering."""
    bets = [
        {"market_id": "m1", "p": 0.7, "odds": 2.0, "ev": 0.4},
        {"market_id": "m2", "p": 0.55, "odds": 2.0, "ev": 0.1},
    ]

    filtered = filter_bets_by_sharpe(bets, min_sharpe=0.3)

    # Should filter based on Sharpe ratio
    assert all("sharpe" in bet for bet in filtered)
    assert all(bet["sharpe"] >= 0.3 for bet in filtered)


def test_filter_bets_by_confidence():
    """Test confidence/probability filtering."""
    bets = [
        {"market_id": "m1", "p": 0.7, "odds": 2.0},
        {"market_id": "m2", "p": 0.5, "odds": 2.5},
        {"market_id": "m3", "p": 0.6, "odds": 2.2},
    ]

    filtered = filter_bets_by_confidence(bets, min_confidence=0.6)

    assert len(filtered) == 2  # m1 and m3
    assert all(bet["p"] >= 0.6 for bet in filtered)


def test_diversify_bets():
    """Test bet diversification by league."""
    bets = [
        {"market_id": "m1", "league": "PL", "ev": 0.3},
        {"market_id": "m2", "league": "PL", "ev": 0.2},
        {"market_id": "m3", "league": "PL", "ev": 0.1},
        {"market_id": "m4", "league": "La Liga", "ev": 0.25},
        {"market_id": "m5", "league": "La Liga", "ev": 0.15},
    ]

    # Limit to 2 per league
    diversified = diversify_bets(bets, max_per_league=2, max_total=10)

    # Count by league
    league_counts = {}
    for bet in diversified:
        league = bet["league"]
        league_counts[league] = league_counts.get(league, 0) + 1

    # No league should have more than 2 bets
    assert all(count <= 2 for count in league_counts.values())


def test_diversify_bets_respects_max_total():
    """Test total bet limit in diversification."""
    bets = [{"market_id": f"m{i}", "league": f"L{i}", "ev": 0.1} for i in range(20)]

    diversified = diversify_bets(bets, max_per_league=5, max_total=10)

    assert len(diversified) <= 10


def test_find_value_bets_with_missing_columns():
    """Test graceful handling of missing columns."""
    data = pd.DataFrame(
        {
            "market_id": ["m1"],
            "p_win": [0.6],
            # Missing 'odds' column
        }
    )

    bets = find_value_bets(data, bank=1000.0)
    assert bets == []
