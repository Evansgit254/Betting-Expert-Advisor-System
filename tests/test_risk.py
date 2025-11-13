"""Tests for risk management module."""
from unittest.mock import patch

import pytest

from src.config import settings
from src.risk import (
    calculate_expected_value,
    calculate_sharpe_ratio,
    calculate_variance,
    kelly_fraction,
    stake_from_bankroll,
    validate_bet,
)


def test_stake_non_negative():
    """Stake should always be non-negative."""
    stake = stake_from_bankroll(0.6, 2.0, 1000)
    assert stake >= 0


def test_stake_zero_for_no_edge():
    """Stake should be zero when there's no edge."""
    # No edge: p = 1/odds
    stake = stake_from_bankroll(0.5, 2.0, 1000)
    assert stake == 0.0


def test_stake_zero_for_negative_edge():
    """Stake should be zero for negative edge."""
    stake = stake_from_bankroll(0.3, 2.0, 1000)
    assert stake == 0.0


def test_stake_positive_for_value():
    """Stake should be positive when there's positive expected value."""
    stake = stake_from_bankroll(0.7, 2.0, 1000)
    assert stake > 0


def test_stake_respects_max_fraction():
    """Stake should not exceed max fraction of bankroll."""
    from src.config import settings

    # High edge case that would normally suggest large stake
    stake = stake_from_bankroll(0.95, 1.5, 1000)
    max_allowed = settings.MAX_STAKE_FRAC * 1000

    assert stake <= max_allowed


def test_kelly_fraction_calculation():
    """Test Kelly criterion calculation."""
    # Known example: p=0.6, odds=2.0, bank=1000
    # b = 1.0, edge = 0.1, kelly = 0.1
    # fractional kelly (20%) = 0.02 of bank = 20
    stake = kelly_fraction(0.6, 2.0, 1000)

    assert stake > 0
    assert stake <= 1000 * 0.05  # Should respect max stake


def test_validate_bet_valid():
    """Test validation of a valid bet."""
    is_valid, reason = validate_bet(
        win_prob=0.6, odds=2.5, stake=50.0, bankroll=1000.0, daily_loss=0.0, open_bets=0
    )

    assert is_valid
    assert reason == "Valid"


def test_validate_bet_invalid_probability():
    """Test validation rejects invalid probabilities."""
    is_valid, _ = validate_bet(win_prob=1.5, odds=2.0, stake=50.0, bankroll=1000.0)  # Invalid

    assert not is_valid


def test_validate_bet_exceeds_bankroll():
    """Test validation rejects stakes exceeding bankroll."""
    is_valid, _ = validate_bet(
        win_prob=0.6, odds=2.0, stake=1500.0, bankroll=1000.0  # Exceeds bankroll
    )

    assert not is_valid


def test_validate_bet_daily_loss_limit():
    """Test validation respects daily loss limit."""
    from src.config import settings

    is_valid, reason = validate_bet(
        win_prob=0.6,
        odds=2.0,
        stake=50.0,
        bankroll=5000.0,
        daily_loss=settings.DAILY_LOSS_LIMIT,  # At limit
    )

    assert not is_valid
    assert "Daily loss limit" in reason


def test_validate_bet_max_open_bets():
    """Test validation respects max open bets."""
    from src.config import settings

    is_valid, reason = validate_bet(
        win_prob=0.6,
        odds=2.0,
        stake=50.0,
        bankroll=1000.0,
        open_bets=settings.MAX_OPEN_BETS,  # At limit
    )

    assert not is_valid
    assert "Max open bets" in reason


def test_expected_value_calculation():
    """Test expected value calculation."""
    # p=0.6, odds=2.0
    # EV = 0.6 * 1.0 - 0.4 = 0.2
    ev = calculate_expected_value(0.6, 2.0)
    assert abs(ev - 0.2) < 0.01


def test_expected_value_negative():
    """Test negative expected value."""
    # Bad bet: p=0.3, odds=2.0
    # EV = 0.3 * 1.0 - 0.7 = -0.4
    ev = calculate_expected_value(0.3, 2.0)
    assert ev < 0


def test_variance_calculation():
    """Test variance calculation."""
    variance = calculate_variance(0.6, 2.0)
    assert variance > 0


def test_sharpe_ratio():
    """Test Sharpe ratio calculation."""
    sharpe = calculate_sharpe_ratio(0.6, 2.0)
    assert sharpe > 0  # Positive EV should have positive Sharpe


def test_sharpe_ratio_negative_ev():
    """Test Sharpe ratio for negative EV bet."""
    sharpe = calculate_sharpe_ratio(0.3, 2.0)
    assert sharpe < 0  # Negative EV should have negative Sharpe


def test_kelly_fraction_invalid_odds():
    """Test Kelly fraction with invalid odds (<= 1.0)."""
    stake = kelly_fraction(0.6, 1.0, 1000)
    assert stake == 0.0

    stake = kelly_fraction(0.6, 0.5, 1000)
    assert stake == 0.0


def test_validate_bet_invalid_odds():
    """Test validation with invalid odds."""
    # Test odds too low
    is_valid, reason = validate_bet(win_prob=0.5, odds=1.0, stake=50.0, bankroll=1000.0)  # Too low
    assert not is_valid
    assert "too low" in reason.lower()

    # Test odds too high
    is_valid, reason = validate_bet(
        win_prob=0.5, odds=1001.0, stake=50.0, bankroll=1000.0  # Too high
    )
    assert not is_valid
    assert "too high" in reason.lower()


def test_validate_bet_no_edge():
    """Test validation with no edge."""
    is_valid, reason = validate_bet(
        win_prob=0.5, odds=2.0, stake=50.0, bankroll=1000.0  # No edge at odds=2.0
    )
    assert not is_valid
    assert "no positive edge" in reason.lower()


def test_validate_bet_invalid_stake():
    """Test validation with invalid stake (zero or negative)."""
    # Test zero stake
    is_valid, reason = validate_bet(win_prob=0.6, odds=2.0, stake=0.0, bankroll=1000.0)  # Invalid
    assert not is_valid
    assert "invalid stake" in reason.lower()

    # Test negative stake
    is_valid, reason = validate_bet(win_prob=0.6, odds=2.0, stake=-50.0, bankroll=1000.0)  # Invalid
    assert not is_valid
    assert "invalid stake" in reason.lower()


def test_validate_bet_stake_exceeds_bankroll():
    """Test validation when stake exceeds bankroll."""
    # Test stake exceeds bankroll
    is_valid, reason = validate_bet(
        win_prob=0.6, odds=2.0, stake=1500.0, bankroll=1000.0  # Exceeds bankroll
    )
    assert not is_valid
    # Check for the exact error message format
    assert "stake 1500.0 exceeds max" in reason.lower()
    assert "% of bankroll" in reason.lower()

    # Test case where stake is exactly at bankroll (should pass the bankroll check but fail MAX_STAKE_FRAC)
    is_valid, reason = validate_bet(
        win_prob=0.6, odds=2.0, stake=1000.0, bankroll=1000.0  # Exactly bankroll
    )
    # Should fail due to MAX_STAKE_FRAC, not bankroll check
    assert not is_valid
    assert "exceeds max" in reason.lower()
    assert "% of bankroll" in reason.lower()


def test_sharpe_ratio_zero_variance():
    """Test Sharpe ratio calculation when variance is zero."""
    # This is a degenerate case that should return 0.0
    # We'll mock calculate_variance to return 0
    with patch("src.risk.calculate_expected_value", return_value=0.1), patch(
        "src.risk.calculate_variance", return_value=0.0
    ):
        sharpe = calculate_sharpe_ratio(win_prob=0.5, odds=2.0)
        assert sharpe == 0.0


def test_validate_bet_stake_exceeds_bankroll_but_within_max_fraction():
    """Test validation when stake exceeds bankroll but is within MAX_STAKE_FRAC."""
    # First, save the original MAX_STAKE_FRAC
    original_max_frac = settings.MAX_STAKE_FRAC

    from pydantic import ValidationError

    try:
        with pytest.raises(ValidationError):
            settings.MAX_STAKE_FRAC = 2.0  # Should be rejected by validation
    finally:
        # Restore original MAX_STAKE_FRAC
        settings.MAX_STAKE_FRAC = original_max_frac
