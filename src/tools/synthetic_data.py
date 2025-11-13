"""Synthetic data generator for testing and backtesting."""
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd

from src.logging_config import get_logger

logger = get_logger(__name__)


def generate_synthetic_fixtures(
    n_days: int = 100, games_per_day: int = 10, start_date: Optional[datetime] = None
) -> pd.DataFrame:
    """Generate synthetic fixture data for testing.

    Args:
        n_days: Number of days to generate
        games_per_day: Average games per day
        start_date: Start date (defaults to n_days ago)

    Returns:
        DataFrame with fixture data
    """
    if start_date is None:
        start_date = datetime.now(timezone.utc) - timedelta(days=n_days)

    logger.info(f"Generating {n_days} days of synthetic fixtures ({games_per_day} games/day)")

    # Generate team pool
    teams = [f"Team_{chr(65+i)}" for i in range(40)]  # Team_A to Team_M
    leagues = ["Premier League", "Championship", "La Liga", "Serie A", "Bundesliga"]

    rows = []
    game_id = 0

    for day in range(n_days):
        current_date = start_date + timedelta(days=day)

        # Vary number of games per day
        n_games = max(1, int(np.random.normal(games_per_day, games_per_day * 0.3)))

        for game in range(n_games):
            # Select random teams
            home_team = np.random.choice(teams)
            away_team = np.random.choice([t for t in teams if t != home_team])

            # Random league
            league = np.random.choice(leagues)

            # Random start time during the day
            hour = np.random.randint(12, 23)
            minute = np.random.choice([0, 15, 30, 45])

            start_time = current_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

            market_id = f"m_{game_id:06d}"
            game_id += 1

            rows.append(
                {
                    "market_id": market_id,
                    "home": home_team,
                    "away": away_team,
                    "start": start_time,
                    "sport": "soccer",
                    "league": league,
                }
            )

    df = pd.DataFrame(rows)
    logger.info(f"Generated {len(df)} synthetic fixtures")

    return df


def generate_synthetic_odds(fixtures_df: pd.DataFrame, add_margin: float = 0.05) -> pd.DataFrame:
    """Generate synthetic odds with realistic bookmaker margins.

    Args:
        fixtures_df: DataFrame with fixtures
        add_margin: Bookmaker margin to add (e.g., 0.05 = 5%)

    Returns:
        DataFrame with odds data
    """
    logger.info(f"Generating synthetic odds for {len(fixtures_df)} fixtures")

    rows = []

    for _, fixture in fixtures_df.iterrows():
        market_id = fixture["market_id"]

        # Generate "true" probabilities using beta distribution
        # This creates realistic variation in match odds
        home_strength = np.random.beta(2, 2)  # Centered around 0.5

        # Home advantage
        home_advantage = 0.1

        # Adjust for home advantage
        p_home = np.clip(home_strength + home_advantage, 0.2, 0.8)
        p_away = np.clip(1 - p_home - 0.25, 0.1, 0.7)
        p_draw = 1 - p_home - p_away

        # Add bookmaker margin by adjusting probabilities
        margin_multiplier = 1 + add_margin
        p_home_adj = p_home * margin_multiplier
        p_away_adj = p_away * margin_multiplier
        p_draw_adj = p_draw * margin_multiplier

        # Normalize to ensure they sum to > 1 (overround)
        total = p_home_adj + p_away_adj + p_draw_adj
        p_home_adj = p_home_adj / total * (1 + add_margin)
        p_away_adj = p_away_adj / total * (1 + add_margin)
        p_draw_adj = p_draw_adj / total * (1 + add_margin)

        # Convert to decimal odds
        odds_home = 1.0 / p_home_adj if p_home_adj > 0 else 100.0
        odds_away = 1.0 / p_away_adj if p_away_adj > 0 else 100.0
        odds_draw = 1.0 / p_draw_adj if p_draw_adj > 0 else 100.0

        # Clamp to reasonable range
        odds_home = np.clip(odds_home, 1.01, 50.0)
        odds_away = np.clip(odds_away, 1.01, 50.0)
        odds_draw = np.clip(odds_draw, 1.01, 50.0)

        # Add to rows
        rows.append(
            {
                "market_id": market_id,
                "selection": "home",
                "odds": round(odds_home, 2),
                "provider": "SyntheticBookie",
                "true_prob": p_home,  # Store for result simulation
            }
        )

        rows.append(
            {
                "market_id": market_id,
                "selection": "away",
                "odds": round(odds_away, 2),
                "provider": "SyntheticBookie",
                "true_prob": p_away,
            }
        )

        rows.append(
            {
                "market_id": market_id,
                "selection": "draw",
                "odds": round(odds_draw, 2),
                "provider": "SyntheticBookie",
                "true_prob": p_draw,
            }
        )

    df = pd.DataFrame(rows)
    logger.info(f"Generated {len(df)} synthetic odds entries")

    return df


def generate_synthetic_results(fixtures_df: pd.DataFrame, odds_df: pd.DataFrame) -> pd.DataFrame:
    """Generate synthetic match results based on true probabilities.

    Args:
        fixtures_df: DataFrame with fixtures
        odds_df: DataFrame with odds (must include true_prob column)

    Returns:
        DataFrame with results
    """
    logger.info(f"Generating synthetic results for {len(fixtures_df)} fixtures")

    results = []

    for market_id in fixtures_df["market_id"].unique():
        # Get odds for this market
        market_odds = odds_df[odds_df["market_id"] == market_id]

        if market_odds.empty or "true_prob" not in market_odds.columns:
            # No odds data, skip
            continue

        # Get true probabilities
        probs = {}
        for _, row in market_odds.iterrows():
            probs[row["selection"]] = row["true_prob"]

        # Simulate result based on true probabilities
        selections = list(probs.keys())
        probabilities = [probs[s] for s in selections]

        # Normalize probabilities to sum to 1
        total_prob = sum(probabilities)
        if total_prob > 0:
            probabilities = [p / total_prob for p in probabilities]
        else:
            probabilities = [1.0 / len(selections)] * len(selections)

        # Sample result
        result = np.random.choice(selections, p=probabilities)

        results.append({"market_id": market_id, "result": result})

    df = pd.DataFrame(results)
    logger.info(f"Generated {len(df)} synthetic results")

    return df


def generate_complete_dataset(
    n_days: int = 100,
    games_per_day: int = 10,
    start_date: Optional[datetime] = None,
    add_margin: float = 0.05,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate complete synthetic dataset with fixtures, odds, and results.

    Args:
        n_days: Number of days
        games_per_day: Games per day
        start_date: Start date
        add_margin: Bookmaker margin

    Returns:
        Tuple of (fixtures_df, odds_df, results_df)
    """
    fixtures = generate_synthetic_fixtures(n_days, games_per_day, start_date)
    odds = generate_synthetic_odds(fixtures, add_margin)
    results = generate_synthetic_results(fixtures, odds)

    return fixtures, odds, results
