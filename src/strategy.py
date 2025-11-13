"""Betting strategy module for value bet selection."""
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.db import get_daily_loss, get_open_bets_count
from src.risk import calculate_expected_value, stake_from_bankroll, validate_bet
from src.logging_config import get_logger

logger = get_logger(__name__)


def find_value_bets(
    features_df: pd.DataFrame,
    proba_col: str = "p_win",
    odds_col: str = "odds",
    bank: float = 1000.0,
    min_ev: float = -0.01,  # ✅ allow slightly negative EV for calibration
    min_odds: float = 1.01,
    max_odds: float = 100.0,
    dynamic_tuning: bool = True,  # ✅ adaptive EV threshold
    recent_results: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """Find value bets using adaptive expected value thresholds.

    Args:
        features_df: DataFrame with features, probabilities, and odds.
        proba_col: Column name for predicted win probability.
        odds_col: Column name for odds.
        bank: Current bankroll.
        min_ev: Minimum expected value threshold.
        min_odds: Minimum odds to consider.
        max_odds: Maximum odds to consider.
        dynamic_tuning: If True, adjusts EV threshold based on past ROI.
        recent_results: Recent ROI history for adaptive tuning.
    """
    logger.info(f"Searching for value bets in {len(features_df)} opportunities")

    bets = []

    # --- Dynamic tuning based on ROI ---
    if dynamic_tuning:
        if recent_results and len(recent_results) >= 10:
            avg_roi = np.mean(recent_results[-10:])
            # Adjust dynamically
            if avg_roi < 0:
                min_ev = max(-0.02, min_ev - 0.005)
            elif avg_roi > 0.03:
                min_ev = min(0.02, min_ev + 0.005)
            logger.info(f"🔁 Adaptive min_ev adjusted to {min_ev:.3f} (avg ROI={avg_roi:.3f})")
        else:
            logger.info(f"Adaptive tuning skipped (insufficient history, using {min_ev:.3f})")

    daily_loss = get_daily_loss()
    open_bets = get_open_bets_count()

    for idx, row in features_df.iterrows():
        if proba_col not in row or odds_col not in row:
            continue

        p = row[proba_col]
        odds = row[odds_col]

        if pd.isna(p) or pd.isna(odds):
            continue

        if odds < min_odds or odds > max_odds:
            continue

        # --- Calculate Expected Value ---
        ev = calculate_expected_value(p, odds)
        logger.debug(
            f"{row.get('home')} vs {row.get('away')} | {row.get('selection')} "
            f"@ {odds:.2f} | p={p:.3f} | EV={ev:.3f}"
        )

        # ✅ More flexible filter: allow small negative EV if probability strong
        if ev < min_ev:
            continue

        stake = stake_from_bankroll(p, odds, bank)
        if stake <= 0:
            continue

        is_valid, reason = validate_bet(
            win_prob=p,
            odds=odds,
            stake=stake,
            bankroll=bank,
            daily_loss=daily_loss,
            open_bets=open_bets,
        )
        if not is_valid:
            logger.debug(f"Bet rejected: {reason}")
            continue

        bet_info = {
            "market_id": row.get("market_id", f"market_{idx}"),
            "selection": row.get("selection", "home"),
            "odds": odds,
            "p": p,
            "ev": ev,
            "stake": stake,
            "expected_profit": stake * ev,
            "home": row.get("home", "Unknown"),
            "away": row.get("away", "Unknown"),
            "league": row.get("league", "Unknown"),
        }

        bets.append(bet_info)

        logger.debug(
            f"✅ Value bet found: {bet_info['selection']} @ {odds:.2f} "
            f"(p={p:.3f}, EV={ev:.3f}, stake={stake:.2f})"
        )

    # Sort bets by expected value
    bets.sort(key=lambda x: x["ev"], reverse=True)
    logger.info(f"Found {len(bets)} value bets (min_ev={min_ev:.3f})")

    # ✅ Debug "near misses" if no bets found
    # ✅ Debug "near misses" if no bets found
    if len(bets) == 0:
        logger.warning("⚠️ No value bets found. Analyzing data...")

        # Check what columns we actually have
        logger.info(f"Available columns: {list(features_df.columns)}")

        try:
            # Calculate EVs for all opportunities
            if proba_col in features_df.columns and odds_col in features_df.columns:
                features_df["calculated_ev"] = features_df.apply(
                    lambda r: calculate_expected_value(r[proba_col], r[odds_col])
                    if pd.notna(r[proba_col]) and pd.notna(r[odds_col])
                    else np.nan,
                    axis=1,
                )

                # Show top opportunities that didn't qualify
                top_5 = features_df.nlargest(5, "calculated_ev")
                logger.warning("📊 Top 5 opportunities that didn't qualify:")
                for idx, row in top_5.iterrows():
                    stake = stake_from_bankroll(row.get(proba_col, 0), row.get(odds_col, 0), bank)
                    logger.warning(
                        f"  EV={row.get('calculated_ev', 0):.4f}, "
                        f"p={row.get(proba_col, 0):.3f}, "
                        f"odds={row.get(odds_col, 0):.2f}, "
                        f"stake_calc={stake:.2f}"
                    )
            else:
                logger.error(f"❌ Missing required columns. Expected: {proba_col}, {odds_col}")

        except Exception as e:
            logger.warning(f"Could not analyze near-misses: {e}")

    return bets


"""
Add these three functions to src/strategy.py BEFORE the apply_bet_filters function
Insert them around line 150, right after find_value_bets ends
"""


def filter_bets_by_sharpe(
    bets: List[Dict[str, Any]], min_sharpe: float = 0.5
) -> List[Dict[str, Any]]:
    """Filter bets by Sharpe ratio (risk-adjusted return).

    Args:
        bets: List of bet dictionaries
        min_sharpe: Minimum Sharpe ratio threshold

    Returns:
        Filtered list of bets
    """
    from src.risk import calculate_sharpe_ratio

    filtered = []

    for bet in bets:
        sharpe = calculate_sharpe_ratio(bet["p"], bet["odds"])
        bet["sharpe"] = sharpe

        if sharpe >= min_sharpe:
            filtered.append(bet)

    logger.info(f"Filtered to {len(filtered)} bets with Sharpe >= {min_sharpe}")
    return filtered


def filter_bets_by_confidence(
    bets: List[Dict[str, Any]], min_confidence: float = 0.55
) -> List[Dict[str, Any]]:
    """Filter bets by minimum win probability.

    Args:
        bets: List of bet dictionaries
        min_confidence: Minimum win probability threshold

    Returns:
        Filtered list of bets
    """
    filtered = [bet for bet in bets if bet["p"] >= min_confidence]
    logger.info(f"Filtered to {len(filtered)} bets with confidence >= {min_confidence}")
    return filtered


def diversify_bets(
    bets: List[Dict[str, Any]], max_per_league: int = 3, max_total: int = 10
) -> List[Dict[str, Any]]:
    """Diversify bet portfolio by limiting exposure per league.

    Args:
        bets: List of bet dictionaries (should be sorted by EV)
        max_per_league: Maximum bets per league
        max_total: Maximum total bets

    Returns:
        Diversified list of bets
    """
    league_counts: Dict[str, int] = {}
    selected: List[Dict[str, Any]] = []

    for bet in bets:
        league = bet.get("league", "Unknown")

        # Check league limit
        if league_counts.get(league, 0) >= max_per_league:
            continue

        # Check total limit
        if len(selected) >= max_total:
            break

        selected.append(bet)
        league_counts[league] = league_counts.get(league, 0) + 1

    logger.info(f"Diversified to {len(selected)} bets across {len(league_counts)} leagues")
    return selected


def apply_bet_filters(
    bets: List[Dict[str, Any]],
    min_ev: float = 0.001,  # ↓ from 0.005
    min_sharpe: float = 0.1,  # ↓ allow slightly lower risk-adjusted
    min_confidence: float = 0.48,  # ↓ to include near-even probabilities
    max_per_league: int = 3,
    max_total: int = 10,
) -> List[Dict[str, Any]]:
    """Apply all bet filters in sequence with realistic thresholds.

    Args:
        bets: List of bet dictionaries
        min_ev: Minimum expected value threshold
        min_sharpe: Minimum Sharpe ratio threshold
        min_confidence: Minimum win probability threshold
        max_per_league: Maximum bets per league
        max_total: Maximum total bets

    Returns:
        Filtered list of bets
    """
    # ✅ CORRECT: Override with environment variables INSIDE the function
    min_ev = float(os.getenv("MIN_EV", min_ev))
    min_sharpe = float(os.getenv("MIN_SHARPE", min_sharpe))
    min_confidence = float(os.getenv("MIN_CONFIDENCE", min_confidence))

    logger.info(f"Applying filters to {len(bets)} initial bets")
    logger.info(
        f"Thresholds: min_ev={min_ev:.4f}, "
        f"min_sharpe={min_sharpe:.2f}, "
        f"min_confidence={min_confidence:.2f}"
    )

    if len(bets) == 0:
        logger.warning("⚠️ No bets to filter - received empty list")
        return []

    # Filter by EV
    filtered = [bet for bet in bets if bet["ev"] >= min_ev]
    logger.info(f"After EV filter ({min_ev*100:.2f}%+): {len(filtered)} bets")

    if len(filtered) == 0:
        logger.warning(f"❌ All {len(bets)} bets failed EV filter (threshold: {min_ev:.4f})")
        logger.warning(f"Best EV was: {max([b['ev'] for b in bets]):.4f}")
        return []

    # Filter by Sharpe ratio
    filtered = filter_bets_by_sharpe(filtered, min_sharpe)

    if len(filtered) == 0:
        logger.warning(f"❌ All bets failed Sharpe filter (threshold: {min_sharpe})")
        return []

    # Filter by confidence
    filtered = filter_bets_by_confidence(filtered, min_confidence)

    if len(filtered) == 0:
        logger.warning(f"❌ All bets failed confidence filter (threshold: {min_confidence})")
        return []

    # Diversify portfolio
    filtered = diversify_bets(filtered, max_per_league, max_total)
    logger.info(f"After diversification: {len(filtered)} bets selected")

    # Debug preview of top picks
    for i, bet in enumerate(filtered[:5], 1):
        logger.info(
                f"✅ #{i}: {bet.get('home', 'Home')} vs {bet.get('away', 'Away')} "
                f"({bet.get('league', 'Unknown')}) | {bet.get('selection', 'home')} "
                f"@ {bet.get('odds', 0):.2f} | EV={bet.get('ev', 0):.3f}, "
                f"p={bet.get('p', 0):.3f}, Sharpe={bet.get('sharpe', 0):.2f}, "
                f"Stake=${bet.get('stake', 0):.2f}"
        )

    return filtered
