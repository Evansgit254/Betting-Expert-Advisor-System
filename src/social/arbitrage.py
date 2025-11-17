"""Arbitrage opportunity detection across bookmakers."""
from typing import Dict, List, Optional

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)


def detect_arbitrage(odds_data: List[Dict]) -> Optional[Dict]:
    """Detect arbitrage opportunities in odds data.

    Args:
        odds_data: List of dicts with keys:
            - bookmaker: str
            - selection: str (home, away, draw)
            - odds: float

    Returns:
        Dict with arbitrage details if found, None otherwise:
            - is_arbitrage: bool
            - profit_margin: float (percentage profit)
            - total_stake: float (normalized to 100)
            - legs: List[Dict] with bookmaker, selection, odds, stake, payout
            - commission_adjusted_profit: float
    """
    if not odds_data or len(odds_data) < 2:
        return None

    # Group by selection to find best odds
    best_odds = {}
    for item in odds_data:
        selection = item["selection"]
        odds = item["odds"]
        bookmaker = item["bookmaker"]

        if selection not in best_odds or odds > best_odds[selection]["odds"]:
            best_odds[selection] = {
                "bookmaker": bookmaker,
                "odds": odds,
                "selection": selection,
            }

    # Need at least 2 selections for arbitrage
    if len(best_odds) < 2:
        return None

    # Calculate implied probabilities
    implied_probs = []
    for selection, data in best_odds.items():
        implied_prob = 1.0 / data["odds"]
        implied_probs.append(implied_prob)

    total_implied_prob = sum(implied_probs)

    # Arbitrage exists if total implied probability < 1.0
    if total_implied_prob >= 1.0:
        return None

    # Calculate profit margin (before commission)
    profit_margin = (1.0 - total_implied_prob) * 100  # Percentage

    # Calculate stakes (normalized to total stake of 100)
    total_stake = 100.0
    legs = []

    for selection, data in best_odds.items():
        implied_prob = 1.0 / data["odds"]
        stake = (implied_prob / total_implied_prob) * total_stake
        payout = stake * data["odds"]

        legs.append({
            "bookmaker": data["bookmaker"],
            "selection": selection,
            "odds": data["odds"],
            "stake": round(stake, 2),
            "payout": round(payout, 2),
        })

    # Adjust for commission
    commission_rate = settings.ARBITRAGE_COMMISSION_RATE
    commission_adjusted_profit = profit_margin - (commission_rate * 100)

    # Only return if still profitable after commission
    if commission_adjusted_profit <= 0:
        logger.debug(
            f"Arbitrage found but not profitable after {commission_rate*100}% commission: "
            f"{profit_margin:.2f}% -> {commission_adjusted_profit:.2f}%"
        )
        return None

    logger.info(
        f"Arbitrage opportunity detected: {profit_margin:.2f}% profit "
        f"({commission_adjusted_profit:.2f}% after commission)"
    )

    return {
        "is_arbitrage": True,
        "profit_margin": round(profit_margin, 2),
        "commission_adjusted_profit": round(commission_adjusted_profit, 2),
        "total_stake": total_stake,
        "legs": legs,
        "commission_rate": commission_rate,
    }


def calculate_arbitrage_stakes(
    odds_list: List[float], total_stake: float = 100.0
) -> List[float]:
    """Calculate optimal stakes for arbitrage.

    Args:
        odds_list: List of odds for each outcome
        total_stake: Total amount to stake

    Returns:
        List of stakes for each outcome
    """
    implied_probs = [1.0 / odds for odds in odds_list]
    total_implied = sum(implied_probs)

    if total_implied >= 1.0:
        raise ValueError("No arbitrage opportunity: total implied probability >= 1.0")

    stakes = [(prob / total_implied) * total_stake for prob in implied_probs]
    return [round(stake, 2) for stake in stakes]


def is_arbitrage_profitable(
    odds_list: List[float], commission_rate: Optional[float] = None
) -> bool:
    """Check if arbitrage is profitable after commission.

    Args:
        odds_list: List of odds for each outcome
        commission_rate: Commission rate (default from config)

    Returns:
        True if profitable after commission
    """
    if commission_rate is None:
        commission_rate = settings.ARBITRAGE_COMMISSION_RATE

    implied_probs = [1.0 / odds for odds in odds_list]
    total_implied = sum(implied_probs)

    if total_implied >= 1.0:
        return False

    profit_margin = (1.0 - total_implied) * 100
    adjusted_profit = profit_margin - (commission_rate * 100)

    return adjusted_profit > 0
