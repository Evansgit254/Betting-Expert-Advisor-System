"""Risk management module with critical fixes applied.

CRITICAL FIXES:
1. Decimal precision for financial calculations
2. Circuit breaker for consecutive losses
3. Drawdown protection
4. Enhanced validation
"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, Optional

from src.config import settings
from src.db import get_consecutive_losses, get_current_bankroll, get_peak_bankroll, get_session
from src.logging_config import get_logger
from src.monitoring import send_alert

logger = get_logger(__name__)


def kelly_stake(p: float, odds: float, bank: float, kelly_frac: float = 0.25) -> float:
    """Calculate optimal Kelly stake with Decimal precision.

    CRITICAL FIX: Uses Decimal for precise financial calculations.

    Args:
        p: Win probability (0-1)
        odds: Decimal odds
        bank: Current bankroll
        kelly_frac: Fractional Kelly multiplier (default 0.25 = quarter Kelly)

    Returns:
        Optimal stake amount rounded to 2 decimal places
    """
    try:
        # Convert to Decimal for precise calculations
        p_dec = Decimal(str(p))
        odds_dec = Decimal(str(odds))
        bank_dec = Decimal(str(bank))
        kelly_frac_dec = Decimal(str(kelly_frac))

        # Validate inputs
        if p_dec <= 0 or p_dec >= 1:
            logger.warning(f"Invalid probability {p}, must be in (0,1)")
            return 0.0

        if odds_dec < Decimal("1.01"):
            logger.warning(f"Invalid odds {odds}, must be >= 1.01")
            return 0.0

        if bank_dec <= 0:
            logger.warning(f"Invalid bankroll {bank}, must be positive")
            return 0.0

        # Calculate Kelly edge
        q = Decimal("1") - p_dec
        edge = (p_dec * (odds_dec - Decimal("1")) - q) / (odds_dec - Decimal("1"))

        if edge <= 0:
            logger.debug(f"No edge: p={p}, odds={odds}, edge={edge}")
            return 0.0

        # Calculate optimal stake with fractional Kelly
        optimal = (edge * kelly_frac_dec * bank_dec).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        result = float(optimal)
        logger.debug(
            f"Kelly stake: p={p:.3f}, odds={odds:.2f}, bank={bank:.2f}, "
            f"edge={float(edge):.4f}, stake={result:.2f}"
        )

        return result

    except (InvalidOperation, ValueError) as e:
        logger.error(f"Error in Kelly calculation: {e}", exc_info=True)
        return 0.0


def stake_from_bankroll(
    win_prob: float,
    odds: float,
    bankroll: float,
    kelly_multiplier: Optional[float] = None,
) -> float:
    """Calculate a stake from bankroll respecting configured limits."""

    multiplier = (
        kelly_multiplier if kelly_multiplier is not None else settings.DEFAULT_KELLY_FRACTION
    )
    stake = kelly_stake(win_prob, odds, bankroll, multiplier)

    max_allowed = bankroll * settings.MAX_STAKE_FRAC
    if stake > max_allowed:
        stake = max_allowed

    if stake > bankroll:
        stake = bankroll

    return max(stake, 0.0)


def kelly_fraction(win_prob: float, odds: float, bankroll: float) -> float:
    """Public wrapper returning fractional Kelly stake respecting limits."""

    return stake_from_bankroll(win_prob, odds, bankroll, settings.DEFAULT_KELLY_FRACTION)


def check_risk_limits(
    stake: float,
    bankroll: float,
    open_bets_count: int,
    daily_loss: float,
    bet_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Check if bet passes all risk management rules.

    CRITICAL FIXES:
    - Added circuit breaker for consecutive losses
    - Added drawdown protection
    - Enhanced validation

    Returns:
        Dict with 'allowed' (bool) and 'reason' (str) if rejected
    """

    # 1. Basic validation
    if stake <= 0:
        return {"allowed": False, "reason": "Stake must be positive"}

    if bankroll <= 0:
        logger.error("Bankroll is non-positive, cannot place bets")
        send_alert("🚨 CRITICAL: Bankroll <= 0", level="critical")
        return {"allowed": False, "reason": "Insufficient bankroll"}

    # 2. Check max stake fraction
    max_stake_allowed = bankroll * settings.MAX_STAKE_FRAC
    if stake > max_stake_allowed:
        logger.warning(f"Stake {stake:.2f} exceeds max allowed {max_stake_allowed:.2f}")
        return {
            "allowed": False,
            "reason": f"Stake exceeds {settings.MAX_STAKE_FRAC*100:.1f}% of bankroll",
        }

    # 3. Check daily loss limit
    if daily_loss >= settings.DAILY_LOSS_LIMIT:
        logger.warning(f"Daily loss {daily_loss:.2f} >= limit {settings.DAILY_LOSS_LIMIT:.2f}")
        send_alert(f"⚠️ Daily loss limit reached: ${daily_loss:.2f}", level="warning")
        return {
            "allowed": False,
            "reason": f"Daily loss limit (${settings.DAILY_LOSS_LIMIT:.2f}) reached",
        }

    # 4. Check if bet would exceed daily loss limit
    potential_loss = stake
    if daily_loss + potential_loss > settings.DAILY_LOSS_LIMIT:
        logger.warning(
            f"Potential loss {daily_loss + potential_loss:.2f} would exceed "
            f"daily limit {settings.DAILY_LOSS_LIMIT:.2f}"
        )
        return {"allowed": False, "reason": "Bet would risk exceeding daily loss limit"}

    # 5. Check max open bets
    if open_bets_count >= settings.MAX_OPEN_BETS:
        logger.warning(f"Open bets {open_bets_count} >= max {settings.MAX_OPEN_BETS}")
        return {"allowed": False, "reason": f"Maximum open bets ({settings.MAX_OPEN_BETS}) reached"}

    is_dry_run = bool(bet_meta.get("dry_run")) if bet_meta else False

    # 6. CRITICAL FIX: Check consecutive losses circuit breaker (skip for dry-run)
    if not is_dry_run:
        with get_session() as session:
            consecutive_losses = get_consecutive_losses(session, max_recent=10)
            max_consecutive = 5  # Configurable threshold

            if consecutive_losses >= max_consecutive:
                logger.error(f"Circuit breaker triggered: {consecutive_losses} consecutive losses")
                send_alert(
                    f"🚨 CIRCUIT BREAKER: {consecutive_losses} consecutive losses detected. "
                    "Betting halted until manual review.",
                    level="critical",
                )
                return {
                    "allowed": False,
                    "reason": f"Circuit breaker: {consecutive_losses} consecutive losses",
                }
            elif consecutive_losses >= 3:
                # Warning at 3 losses
                logger.warning(f"Warning: {consecutive_losses} consecutive losses")
                send_alert(
                    f"⚠️ {consecutive_losses} consecutive losses - approaching circuit breaker",
                    level="warning",
                )

    # 7. CRITICAL FIX: Check drawdown protection (skip for dry-run)
    if not is_dry_run:
        with get_session() as session:
            peak_bankroll = get_peak_bankroll(session, days=30)
            current_bankroll = get_current_bankroll()

            if current_bankroll <= 0:
                current_bankroll = bankroll

            if peak_bankroll <= 0:
                peak_bankroll = max(bankroll, current_bankroll)

            if peak_bankroll > 0:
                drawdown = (peak_bankroll - current_bankroll) / peak_bankroll
                max_drawdown = 0.20  # 20% max drawdown (configurable)

                if drawdown > max_drawdown:
                    logger.error(
                        f"Drawdown protection triggered: current {drawdown:.1%} "
                        f"exceeds max {max_drawdown:.1%}"
                    )
                    send_alert(
                        f"🚨 DRAWDOWN PROTECTION: Current drawdown {drawdown:.1%} "
                        f"exceeds maximum {max_drawdown:.1%}. Betting halted.",
                        level="critical",
                    )
                    return {
                        "allowed": False,
                        "reason": f"Drawdown {drawdown:.1%} exceeds {max_drawdown:.1%}",
                    }
                elif drawdown > 0.15:
                    # Warning at 15% drawdown
                    logger.warning(f"High drawdown: {drawdown:.1%}")
                    send_alert(
                        f"⚠️ Drawdown warning: {drawdown:.1%} (max: {max_drawdown:.1%})",
                        level="warning",
                    )

    # All checks passed
    logger.debug("All risk checks passed")
    return {"allowed": True, "reason": ""}


def validate_bet_parameters(
    market_id: str, selection: str, stake: float, odds: float, probability: Optional[float] = None
) -> Dict[str, Any]:
    """Validate bet parameters are within acceptable ranges.

    Enhanced validation with Decimal precision checks.

    Returns:
        Dict with 'valid' (bool) and 'errors' (list of str)
    """
    errors = []

    # Market ID validation
    if not market_id or not isinstance(market_id, str):
        errors.append("Invalid market_id")

    # Selection validation
    if not selection or not isinstance(selection, str):
        errors.append("Invalid selection")

    # Stake validation with Decimal precision
    try:
        stake_dec = Decimal(str(stake))
        if stake_dec <= 0:
            errors.append("Stake must be positive")
        if stake_dec > Decimal("100000"):
            errors.append("Stake unreasonably large (>100k)")
    except (InvalidOperation, ValueError):
        errors.append("Invalid stake format")

    # Odds validation
    try:
        odds_dec = Decimal(str(odds))
        if odds_dec < Decimal("1.01"):
            errors.append("Odds must be >= 1.01")
        if odds_dec > Decimal("1000"):
            errors.append("Odds unreasonably high (>1000)")
    except (InvalidOperation, ValueError):
        errors.append("Invalid odds format")

    # Probability validation
    if probability is not None:
        try:
            p_dec = Decimal(str(probability))
            if p_dec <= 0 or p_dec >= 1:
                errors.append("Probability must be in (0, 1)")
        except (InvalidOperation, ValueError):
            errors.append("Invalid probability format")

    return {"valid": len(errors) == 0, "errors": errors}


def calculate_expected_value(probability: float, odds: float, stake: float = 1.0) -> float:
    """Calculate expected value with Decimal precision.

    EV = (probability * (odds - 1) * stake) - ((1 - probability) * stake)

    Args:
        probability: Win probability (0-1)
        odds: Decimal odds
        stake: Bet stake

    Returns:
        Expected value (can be negative)
    """
    try:
        p_dec = Decimal(str(probability))
        odds_dec = Decimal(str(odds))
        stake_dec = Decimal(str(stake))

        win_return = (odds_dec - Decimal("1")) * stake_dec
        loss_return = -stake_dec

        expected = (p_dec * win_return) + ((Decimal("1") - p_dec) * loss_return)
        ev = expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return float(ev)

    except (InvalidOperation, ValueError) as e:
        logger.error(f"Error calculating EV: {e}")
        return 0.0


def calculate_variance(probability: float, odds: float, stake: float = 1.0) -> float:
    """Calculate variance of bet returns using Decimal arithmetic."""

    try:
        p_dec = Decimal(str(probability))
        odds_dec = Decimal(str(odds))
        stake_dec = Decimal(str(stake))

        win_return = (odds_dec - Decimal("1")) * stake_dec
        loss_return = -stake_dec

        mean = Decimal(
            str(calculate_expected_value(probability, float(odds_dec), float(stake_dec)))
        )

        win_dev = win_return - mean
        loss_dev = loss_return - mean

        variance = (p_dec * (win_dev**2)) + ((Decimal("1") - p_dec) * (loss_dev**2))
        return float(variance.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError) as exc:
        logger.error(f"Error calculating variance: {exc}")
        return 0.0


def calculate_sharpe_ratio(win_prob: float, odds: float, stake: float = 1.0) -> float:
    """Compute Sharpe ratio (return over volatility) for a single bet."""

    ev = calculate_expected_value(win_prob, odds, stake)
    variance = calculate_variance(win_prob, odds, stake)

    if variance <= 0:
        return 0.0

    std_dev = variance**0.5
    if std_dev == 0:
        return 0.0

    return ev / std_dev


def get_recommended_stake(
    probability: float,
    odds: float,
    bankroll: float,
    min_ev: float = 0.01,
    kelly_fraction: float = 0.25,
) -> Dict[str, Any]:
    """Get recommended stake with all risk checks applied.

    Returns:
        Dict with:
        - stake: Recommended stake amount
        - ev: Expected value
        - edge: Betting edge
        - kelly_pct: Percentage of bankroll (Kelly)
        - reason: Explanation if stake is 0
    """

    # Validate inputs
    validation = validate_bet_parameters(
        market_id="dummy",
        selection="dummy",
        stake=1.0,  # Dummy stake for validation
        odds=odds,
        probability=probability,
    )

    if not validation["valid"]:
        return {
            "stake": 0.0,
            "ev": 0.0,
            "edge": 0.0,
            "kelly_pct": 0.0,
            "reason": "; ".join(validation["errors"]),
        }

    # Calculate Kelly stake
    stake = kelly_stake(probability, odds, bankroll, kelly_fraction)

    if stake <= 0:
        return {
            "stake": 0.0,
            "ev": 0.0,
            "edge": 0.0,
            "kelly_pct": 0.0,
            "reason": "No positive edge",
        }

    # Calculate metrics
    ev = calculate_expected_value(probability, odds, stake)

    try:
        p_dec = Decimal(str(probability))
        odds_dec = Decimal(str(odds))
        edge = float(
            (p_dec * odds_dec - Decimal("1")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        )
    except:
        edge = 0.0

    kelly_pct = (stake / bankroll) if bankroll > 0 else 0.0

    # Check minimum EV
    if ev < min_ev:
        return {
            "stake": 0.0,
            "ev": ev,
            "edge": edge,
            "kelly_pct": kelly_pct,
            "reason": f"EV {ev:.2f} below minimum {min_ev:.2f}",
        }

    return {"stake": stake, "ev": ev, "edge": edge, "kelly_pct": kelly_pct, "reason": ""}


def validate_bet(
    win_prob: float,
    odds: float,
    stake: float,
    bankroll: float,
    daily_loss: float = 0.0,
    open_bets: int = 0,
) -> tuple[bool, str]:
    """Validate bet parameters against risk and bankroll constraints."""

    if win_prob <= 0 or win_prob >= 1:
        return False, "Invalid win probability"

    if odds <= 1.01:
        return False, "Odds too low"

    if odds > 1000:
        return False, "Odds too high"

    if stake <= 0:
        return False, "Invalid stake amount"

    if bankroll <= 0:
        return False, "Invalid bankroll"

    max_allowed = bankroll * settings.MAX_STAKE_FRAC
    if stake > max_allowed:
        return (
            False,
            f"Stake {stake} exceeds max {settings.MAX_STAKE_FRAC*100:.1f}% of bankroll",
        )

    if stake > bankroll:
        return False, f"Stake {stake} exceeds bankroll {bankroll}"

    if daily_loss >= settings.DAILY_LOSS_LIMIT:
        return False, "Daily loss limit reached"

    if daily_loss + stake > settings.DAILY_LOSS_LIMIT:
        return False, "Daily loss limit would be exceeded"

    if open_bets >= settings.MAX_OPEN_BETS:
        return False, "Max open bets reached"

    ev = calculate_expected_value(win_prob, odds, stake)
    if ev <= 0:
        return False, "No positive edge"

    return True, "Valid"


def reset_daily_limits():
    """Reset daily tracking (should be called at start of each day).

    This is a placeholder - actual implementation would update DailyStats table.
    """
    logger.info("Daily limits reset")
    send_alert("📊 Daily limits reset - new trading day", level="info")
