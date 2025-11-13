"""Tests for advanced staking algorithms."""
from src.staking import (
    cvar_adjusted_stake,
    dynamic_staking,
    fractional_kelly,
    geometric_mean_staking,
    portfolio_allocate,
)


def test_fractional_kelly_positive_edge():
    """Test fractional Kelly with positive edge."""
    stake = fractional_kelly(win_prob=0.6, odds=2.0, bankroll=1000.0, fraction=0.25, max_frac=0.05)

    # Should return positive stake
    assert stake > 0

    # Should not exceed max fraction
    assert stake <= 1000.0 * 0.05


def test_fractional_kelly_negative_edge():
    """Test fractional Kelly with negative edge."""
    stake = fractional_kelly(win_prob=0.3, odds=2.0, bankroll=1000.0)  # Low probability  # Low odds

    # Should return zero stake (no edge)
    assert stake == 0.0


def test_fractional_kelly_zero_odds():
    """Test fractional Kelly with invalid odds."""
    stake = fractional_kelly(win_prob=0.6, odds=1.0, bankroll=1000.0)  # No profit

    assert stake == 0.0


def test_fractional_kelly_respects_max_frac():
    """Test that fractional Kelly respects maximum stake fraction."""
    stake = fractional_kelly(
        win_prob=0.9,  # Very high probability
        odds=2.0,
        bankroll=1000.0,
        fraction=1.0,  # Full Kelly
        max_frac=0.05,  # 5% cap
    )

    # Should be capped at 5% of bankroll
    assert stake <= 50.0


def test_fractional_kelly_default_params():
    """Test fractional Kelly with default parameters."""
    stake = fractional_kelly(win_prob=0.6, odds=2.5, bankroll=1000.0)

    # Should use default settings
    assert stake >= 0
    assert stake <= 1000.0


def test_cvar_adjusted_stake_reduces_risk():
    """Test that CVaR adjustment reduces stake size."""
    base_stake = fractional_kelly(0.55, 2.0, 1000.0)
    cvar_stake = cvar_adjusted_stake(0.55, 2.0, 1000.0)

    # CVaR stake should be smaller or equal to base
    assert cvar_stake <= base_stake


def test_cvar_adjusted_stake_high_confidence():
    """Test CVaR stake with high win probability."""
    stake = cvar_adjusted_stake(win_prob=0.8, odds=2.0, bankroll=1000.0)

    assert stake > 0


def test_cvar_adjusted_stake_low_confidence():
    """Test CVaR stake with low win probability."""
    stake = cvar_adjusted_stake(win_prob=0.3, odds=2.0, bankroll=1000.0)

    # Should be very small or zero
    assert stake >= 0
    assert stake < 10.0  # Small stake


def test_portfolio_allocate_basic():
    """Test basic portfolio allocation."""
    bets = [{"p": 0.6, "odds": 2.5}, {"p": 0.55, "odds": 2.0}, {"p": 0.7, "odds": 1.8}]
    bankroll = 1000.0

    stakes = portfolio_allocate(bets, bankroll)

    # Should return stake for each bet
    assert len(stakes) == len(bets)

    # All stakes should be non-negative
    assert all(s >= 0 for s in stakes)

    # Total should not exceed MAX_STAKE_FRAC of bankroll
    assert sum(stakes) <= bankroll * 0.05  # Assuming MAX_STAKE_FRAC = 0.05


def test_portfolio_allocate_empty_bets():
    """Test portfolio allocation with no bets."""
    stakes = portfolio_allocate([], 1000.0)
    assert stakes == []


def test_portfolio_allocate_negative_ev():
    """Test portfolio allocation with all negative EV bets."""
    bets = [{"p": 0.3, "odds": 2.0}, {"p": 0.4, "odds": 1.8}]  # Negative EV  # Negative EV
    bankroll = 1000.0

    stakes = portfolio_allocate(bets, bankroll)

    # All stakes should be zero
    assert all(s == 0.0 for s in stakes)


def test_portfolio_allocate_proportional():
    """Test that allocation is proportional to EV."""
    bets = [{"p": 0.6, "odds": 3.0}, {"p": 0.55, "odds": 2.0}]  # High EV  # Lower EV
    bankroll = 1000.0

    stakes = portfolio_allocate(bets, bankroll)

    # First bet should get larger stake (higher EV)
    assert stakes[0] > stakes[1]


def test_geometric_mean_staking_positive_edge():
    """Test geometric mean staking with positive edge."""
    stake = geometric_mean_staking(win_prob=0.6, odds=2.5, bankroll=1000.0)

    assert stake > 0
    assert stake <= 1000.0 * 0.05  # Should respect max fraction


def test_geometric_mean_staking_negative_edge():
    """Test geometric mean staking with negative edge."""
    stake = geometric_mean_staking(win_prob=0.3, odds=2.0, bankroll=1000.0)

    assert stake == 0.0


def test_geometric_mean_staking_invalid_inputs():
    """Test geometric mean staking with invalid inputs."""
    # Zero probability
    stake = geometric_mean_staking(0.0, 2.0, 1000.0)
    assert stake == 0.0

    # Probability = 1
    stake = geometric_mean_staking(1.0, 2.0, 1000.0)
    assert stake == 0.0

    # Zero odds
    stake = geometric_mean_staking(0.6, 1.0, 1000.0)
    assert stake == 0.0


def test_dynamic_staking_no_history():
    """Test dynamic staking with no performance history."""
    stake = dynamic_staking(win_prob=0.6, odds=2.0, bankroll=1000.0, recent_performance=[])

    # Should return base stake
    base_stake = fractional_kelly(0.6, 2.0, 1000.0)
    assert stake == base_stake


def test_dynamic_staking_winning_streak():
    """Test dynamic staking after winning streak."""
    # Recent wins
    recent_performance = [10.0, 5.0, 15.0, 8.0, 12.0]  # All positive

    stake = dynamic_staking(
        win_prob=0.6, odds=2.0, bankroll=1000.0, recent_performance=recent_performance
    )

    # Should increase stake
    base_stake = fractional_kelly(0.6, 2.0, 1000.0)
    assert stake >= base_stake


def test_dynamic_staking_losing_streak():
    """Test dynamic staking after losing streak."""
    # Recent losses
    recent_performance = [-10.0, -5.0, -15.0, -8.0, -12.0]  # All negative

    stake = dynamic_staking(
        win_prob=0.6, odds=2.0, bankroll=1000.0, recent_performance=recent_performance
    )

    # Should decrease stake
    base_stake = fractional_kelly(0.6, 2.0, 1000.0)
    assert stake < base_stake


def test_dynamic_staking_mixed_results():
    """Test dynamic staking with mixed results."""
    recent_performance = [10.0, -5.0, 15.0, -8.0, 12.0]  # Mixed

    stake = dynamic_staking(
        win_prob=0.6, odds=2.0, bankroll=1000.0, recent_performance=recent_performance
    )

    # Should be close to base stake
    base_stake = fractional_kelly(0.6, 2.0, 1000.0)
    assert stake > 0
    # Should be within reasonable range of base
    assert stake / base_stake >= 0.5
    assert stake / base_stake <= 1.5


def test_dynamic_staking_respects_max_frac():
    """Test that dynamic staking respects maximum stake fraction."""
    # Strong winning streak
    recent_performance = [20.0] * 20

    stake = dynamic_staking(
        win_prob=0.9, odds=3.0, bankroll=1000.0, recent_performance=recent_performance
    )

    # Should not exceed max fraction even with great performance
    assert stake <= 1000.0 * 0.05


def test_dynamic_staking_window_size():
    """Test that dynamic staking uses correct window size."""
    # Long history, but should only consider recent window
    long_history = [-10.0] * 50 + [20.0] * 10  # Old losses, recent wins

    stake = dynamic_staking(
        win_prob=0.6, odds=2.0, bankroll=1000.0, recent_performance=long_history, window=10
    )

    # Should be influenced by recent wins, not old losses
    base_stake = fractional_kelly(0.6, 2.0, 1000.0)
    assert stake >= base_stake
