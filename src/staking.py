"""Advanced staking algorithms and portfolio optimization."""
from typing import Any, Dict, List

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)


def fractional_kelly(
    win_prob: float, odds: float, bankroll: float, fraction: float = None, max_frac: float = None
) -> float:
    """Fractional Kelly criterion with floor/ceiling controls.

    Args:
        win_prob: Probability of winning (0-1)
        odds: Decimal odds
        bankroll: Current bankroll
        fraction: Kelly fraction multiplier (defaults to settings)
        max_frac: Max stake as fraction of bankroll (defaults to settings)

    Returns:
        Recommended stake
    """
    if fraction is None:
        fraction = settings.DEFAULT_KELLY_FRACTION
    if max_frac is None:
        max_frac = settings.MAX_STAKE_FRAC

    b = odds - 1.0

    if b <= 0:
        return 0.0

    edge = win_prob - (1.0 / odds)

    if edge <= 0:
        return 0.0

    # Full Kelly percentage
    raw_k = edge / b

    # Apply fractional Kelly
    stake = raw_k * fraction * bankroll

    # Apply cap
    cap = max_frac * bankroll

    return max(0.0, min(stake, cap))


def cvar_adjusted_stake(
    win_prob: float, odds: float, bankroll: float, var_level: float = 0.95
) -> float:
    """CVaR-based stake sizing (conservative approach).

    Adjusts stake downward based on tail risk (probability of large loss).

    Args:
        win_prob: Probability of winning
        odds: Decimal odds
        bankroll: Current bankroll
        var_level: Value-at-Risk confidence level

    Returns:
        Adjusted stake
    """
    # Start with base Kelly stake
    base_stake = fractional_kelly(win_prob, odds, bankroll)

    # Adjust based on tail risk
    # Higher loss probability = more conservative
    loss_prob = 1 - win_prob

    # Simple adjustment: reduce stake by loss probability factor
    adjustment = 1 - (loss_prob * 0.5)
    adjusted_stake = base_stake * adjustment

    return max(0.0, adjusted_stake)


def portfolio_allocate(bets: List[Dict[str, Any]], bankroll: float) -> List[float]:
    """Allocate bankroll across multiple bets using portfolio optimization.

    Simple implementation using proportional allocation by expected value.
    In production, could use mean-variance optimization (Markowitz) or
    Kelly-optimal portfolio allocation.

    Args:
        bets: List of bet dictionaries with 'p' (probability) and 'odds'
        bankroll: Total bankroll to allocate

    Returns:
        List of stake amounts for each bet
    """
    if not bets:
        return []

    # Calculate expected values
    evs = []
    for bet in bets:
        p = bet.get("p", 0.5)
        odds = bet.get("odds", 2.0)
        ev = p * (odds - 1) - (1 - p)
        evs.append(max(0, ev))  # Only positive EVs

    # Total positive EV
    total_ev = sum(evs)

    if total_ev <= 0:
        logger.warning("No positive EV bets in portfolio")
        return [0.0] * len(bets)

    # Proportional allocation by EV
    # Limit total allocation to MAX_STAKE_FRAC of bankroll
    max_total = bankroll * settings.MAX_STAKE_FRAC

    stakes = []
    for ev in evs:
        if total_ev > 0:
            proportion = ev / total_ev
            stake = proportion * max_total
        else:
            stake = 0.0
        stakes.append(stake)

    logger.info(f"Portfolio allocation: {len(stakes)} bets, total stake: {sum(stakes):.2f}")
    return stakes


def geometric_mean_staking(
    win_prob: float, odds: float, bankroll: float, num_bets: int = 100
) -> float:
    """Calculate stake that maximizes geometric mean growth.

    This is equivalent to Kelly criterion but derived from
    maximizing long-term growth rate.

    Args:
        win_prob: Probability of winning
        odds: Decimal odds
        bankroll: Current bankroll
        num_bets: Number of bets to simulate

    Returns:
        Optimal stake
    """
    # For single bet, this reduces to Kelly formula
    b = odds - 1.0
    p = win_prob

    if b <= 0 or p <= 0 or p >= 1:
        return 0.0

    # Kelly formula
    f = (b * p - (1 - p)) / b

    # Apply fractional Kelly for safety
    f = f * settings.DEFAULT_KELLY_FRACTION

    # Cap to max fraction
    f = min(f, settings.MAX_STAKE_FRAC)

    stake = f * bankroll
    return max(0.0, stake)


def dynamic_staking(
    win_prob: float, odds: float, bankroll: float, recent_performance: List[float], window: int = 20
) -> float:
    """Dynamic stake sizing based on recent performance.

    Reduces stakes after losing streaks, increases after winning streaks.

    Args:
        win_prob: Probability of winning
        odds: Decimal odds
        bankroll: Current bankroll
        recent_performance: List of recent P&L results
        window: Window size for performance calculation

    Returns:
        Adjusted stake
    """
    # Base Kelly stake
    base_stake = fractional_kelly(win_prob, odds, bankroll)

    if not recent_performance:
        return base_stake

    # Look at recent window
    recent = (
        recent_performance[-window:] if len(recent_performance) > window else recent_performance
    )

    # Calculate recent win rate
    wins = sum(1 for x in recent if x > 0)
    total = len(recent)

    if total == 0:
        return base_stake

    win_rate = wins / total

    # Adjust stake based on recent performance
    # If recent win rate > 60%, increase stake by up to 20%
    # If recent win rate < 40%, decrease stake by up to 40%
    if win_rate > 0.6:
        multiplier = 1.0 + min((win_rate - 0.6) * 0.5, 0.2)
    elif win_rate < 0.4:
        multiplier = 1.0 - min((0.4 - win_rate) * 1.0, 0.4)
    else:
        multiplier = 1.0

    adjusted_stake = base_stake * multiplier

    # Still respect max stake fraction
    max_stake = bankroll * settings.MAX_STAKE_FRAC
    adjusted_stake = min(adjusted_stake, max_stake)

    logger.debug(f"Dynamic staking: recent win rate {win_rate:.2%}, multiplier {multiplier:.2f}")

    return max(0.0, adjusted_stake)
