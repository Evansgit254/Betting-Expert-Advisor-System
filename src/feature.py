"""Feature engineering with critical fixes applied.

CRITICAL FIXES:
1. Proper timezone handling
2. Division by zero protection
3. Invalid odds handling
4. Enhanced validation
"""
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np
import pandas as pd
import pytz

from src.logging_config import get_logger

logger = get_logger(__name__)


def build_features(fixtures_df: pd.DataFrame, odds_df: pd.DataFrame) -> pd.DataFrame:
    """Build features with enhanced validation."""
    logger.info(f"Building features from {len(fixtures_df)} fixtures and {len(odds_df)} odds")

    if fixtures_df.empty:
        return pd.DataFrame()

    df = fixtures_df.copy()
    standard_selections = ["home", "away", "draw"]

    # Join with odds if available
    if not odds_df.empty:
        # Normalize selection to lowercase for consistent filtering
        odds_df["selection"] = odds_df["selection"].astype(str).str.lower()
        
        # CRITICAL FIX: Map team names to 'home'/'away'
        # We need to know which team is home/away for each market to map the odds correctly
        if "home" in df.columns and "away" in df.columns:
            # Create a mapping dataframe from fixtures
            mapping = df[["market_id", "home", "away"]].copy()
            mapping["home"] = mapping["home"].str.lower()
            mapping["away"] = mapping["away"].str.lower()
            
            # Merge odds with mapping
            odds_mapped = odds_df.merge(mapping, on="market_id", how="left")
            
            # Create normalized selection column
            conditions = [
                odds_mapped["selection"] == odds_mapped["home"],
                odds_mapped["selection"] == odds_mapped["away"],
                odds_mapped["selection"] == "draw"
            ]
            choices = ["home", "away", "draw"]
            
            odds_mapped["selection_norm"] = np.select(conditions, choices, default=np.nan)
            
            # Filter out unmapped selections
            odds_filtered = odds_mapped.dropna(subset=["selection_norm"]).copy()
            odds_filtered["selection"] = odds_filtered["selection_norm"]
            
            # Clean up
            odds_filtered = odds_filtered.drop(columns=["home", "away", "selection_norm"])
        else:
            # Fallback if home/away columns missing (shouldn't happen)
            odds_filtered = odds_df[odds_df["selection"].isin(standard_selections)].copy()

        if not odds_filtered.empty:
            # CRITICAL FIX: Convert odds to numeric and handle errors
            odds_filtered["odds"] = pd.to_numeric(odds_filtered["odds"], errors="coerce")

            # Drop rows where odds couldn't be converted
            odds_filtered = odds_filtered.dropna(subset=["odds"])

            # Pivot odds
            odds_pivot = odds_filtered.pivot_table(
                index="market_id", columns="selection", values="odds", aggfunc="first"
            ).reset_index()
            
            # Rename columns
            rename_map = {}
            for col in odds_pivot.columns:
                if col in standard_selections:
                    rename_map[col] = f"{col}_odds"

            if rename_map:
                odds_pivot = odds_pivot.rename(columns=rename_map)
            
            df = df.merge(odds_pivot, on="market_id", how="left")

    # Add features
    df = add_odds_features(df)
    df = add_temporal_features(df)
    df = add_team_features(df)
    df = add_advanced_features(df)  # Advanced features
    df = add_sentiment_features(df)  # NEW: Sentiment features

    logger.info(f"Generated {len(df.columns)} features")
    return df
    return df


def add_odds_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add odds-derived features with division-by-zero protection.

    CRITICAL FIXES:
    - Replace zeros with NaN
    - Safe division with inf/nan handling
    - Clip extreme ratios
    """
    df = df.copy()

    # Allow shorthand columns like 'home'/'away' to be treated as odds ONLY if they are numeric
    # and not the team names. But since 'home'/'away' are usually team names, we should be careful.
    # Safest is to NOT rename 'home'/'away' automatically if they might be strings.
    
    # rename_candidates = {
    #     "home": "home_odds",
    #     "away": "away_odds",
    #     "draw": "draw_odds",
    # }
    # for source, target in rename_candidates.items():
    #     if source in df.columns and target not in df.columns:
    #         # Check if it looks numeric? 
    #         # For now, let's DISABLE this to prevent clobbering team names.
    #         pass

    # Convert odds columns to numeric (in case they're strings)
    for col in ["home_odds", "away_odds", "draw_odds"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

            # CRITICAL FIX: Replace zeros with NaN
            df[col] = df[col].replace(0, np.nan)

    # Calculate implied probabilities
    if "home_odds" in df.columns:
        df["implied_prob_home"] = np.where(df["home_odds"] > 0, 1.0 / df["home_odds"], np.nan)
        df["implied_prob_home"] = df["implied_prob_home"].clip(0, 1)

    if "away_odds" in df.columns:
        df["implied_prob_away"] = np.where(df["away_odds"] > 0, 1.0 / df["away_odds"], np.nan)
        df["implied_prob_away"] = df["implied_prob_away"].clip(0, 1)

    if "draw_odds" in df.columns:
        df["implied_prob_draw"] = np.where(df["draw_odds"] > 0, 1.0 / df["draw_odds"], np.nan)
        df["implied_prob_draw"] = df["implied_prob_draw"].clip(0, 1)

    # Calculate bookmaker margin
    prob_cols = ["implied_prob_home", "implied_prob_away", "implied_prob_draw"]
    available_probs = [c for c in prob_cols if c in df.columns]

    if available_probs:
        df["bookmaker_margin"] = df[available_probs].sum(axis=1) - 1.0

        # Create normalized probabilities
        total_implied = df[available_probs].sum(axis=1)

        # Only normalize where total > 0
        if "home_prob" not in df.columns:
            if "implied_prob_home" in df.columns:
                df["home_prob"] = np.where(
                    total_implied > 0,
                    df["implied_prob_home"] / total_implied,
                    df["implied_prob_home"],
                )
                df["home_prob"] = df["home_prob"].clip(0, 1)

        if "away_prob" not in df.columns:
            if "implied_prob_away" in df.columns:
                df["away_prob"] = np.where(
                    total_implied > 0,
                    df["implied_prob_away"] / total_implied,
                    df["implied_prob_away"],
                )
                df["away_prob"] = df["away_prob"].clip(0, 1)

        if "draw_prob" not in df.columns:
            if "implied_prob_draw" in df.columns:
                df["draw_prob"] = np.where(
                    total_implied > 0,
                    df["implied_prob_draw"] / total_implied,
                    df["implied_prob_draw"],
                )
                df["draw_prob"] = df["draw_prob"].clip(0, 1)

    # Favorite indicator with safe comparison
    if "home_odds" in df.columns and "away_odds" in df.columns:
        df["home_favorite"] = (
            (df["home_odds"].notna())
            & (df["away_odds"].notna())
            & (df["home_odds"] < df["away_odds"])
        ).astype(int)

        df["odds_differential"] = df["away_odds"] - df["home_odds"]

        # CRITICAL FIX: Safe odds ratio with default for invalid cases
        df["odds_ratio"] = np.where(
            (df["home_odds"] > 0) & (df["away_odds"] > 0),
            df["away_odds"] / df["home_odds"],
            1.0,  # Default to 1.0 for invalid ratios
        )

        # CRITICAL FIX: Clip extreme ratios
        df["odds_ratio"] = df["odds_ratio"].clip(0.01, 100)

    return df


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add time-based features with proper timezone handling.

    CRITICAL FIX: Explicit timezone normalization to UTC.
    """
    if "start" not in df.columns:
        return df

    # CRITICAL FIX: Ensure datetime and normalize to UTC
    if not pd.api.types.is_datetime64_any_dtype(df["start"]):
        df["start"] = pd.to_datetime(df["start"], utc=True)
    else:
        # If timezone-naive, assume UTC
        if df["start"].dt.tz is None:
            logger.debug("Localizing timezone-naive timestamps to UTC")
            df["start"] = df["start"].dt.tz_localize("UTC")
        else:
            # Convert to UTC
            logger.debug(f"Converting timestamps from {df['start'].dt.tz} to UTC")
            df["start"] = df["start"].dt.tz_convert("UTC")

    # Now safely compute features in UTC
    now = pd.Timestamp.now(tz=timezone.utc)
    if getattr(now, "tzinfo", None) is None:
        now = now.tz_localize(timezone.utc)

    df["day_of_week"] = df["start"].dt.dayofweek
    df["hour_of_day"] = df["start"].dt.hour
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["days_until_match"] = (df["start"] - now).dt.total_seconds() / 86400

    logger.debug(
        f"Temporal features: days_until_match range [{df['days_until_match'].min():.1f}, {df['days_until_match'].max():.1f}]"
    )

    return df


def add_team_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add team-based features (placeholder)."""
    df = df.copy()

    if "home" not in df.columns or "away" not in df.columns:
        return df

    # Team strength proxies (hash-based for demo)
    df["home_strength"] = df["home"].apply(lambda x: (hash(x) % 100) / 100.0)
    df["away_strength"] = df["away"].apply(lambda x: (hash(x) % 100) / 100.0)
    df["strength_differential"] = df["home_strength"] - df["away_strength"]

    return df


def select_features(df: pd.DataFrame, feature_names: Optional[List[str]] = None) -> pd.DataFrame:
    """Select features for modeling with validation.

    CRITICAL FIX: Only numeric features, proper validation.
    """
    if feature_names is not None:
        available_features = [f for f in feature_names if f in df.columns]
        result = df[available_features].fillna(0)

        # Ensure only numeric
        result = result.select_dtypes(include=[np.number])

        return result

    # Auto-select core numeric features
    core_features = [
        "draw_odds",
        "bookmaker_margin",
        "implied_prob_draw",
        "day_of_week",
        "hour_of_day",
        "is_weekend",
        "days_until_match",
    ]

    # Add home/away odds
    for home_col in ["home_odds"]:
        if home_col in df.columns:
            core_features.insert(0, home_col)
            break

    for away_col in ["away_odds"]:
        if away_col in df.columns:
            core_features.insert(1, away_col)
            break

    # Find available features
    available = [f for f in core_features if f in df.columns]

    if not available:
        # Fallback: all numeric excluding certain columns
        exclude_cols = [
            "market_id",
            "start",
            "sport",
            "league",
            "selection",
            "provider",
            "home",
            "away",
            "home_strength",
            "away_strength",
            "strength_differential",
            "home_favorite",
            "odds_differential",
            "odds_ratio",
        ]
        numeric_df = df.select_dtypes(include=[np.number])
        available = [c for c in numeric_df.columns if c not in exclude_cols]

    # CRITICAL FIX: Ensure only numeric data, handle inf/nan
    result = df[available].copy()
    result = result.select_dtypes(include=[np.number])

    # Replace inf with nan, then fill
    result = result.replace([np.inf, -np.inf], np.nan)
    result = result.fillna(0)

    logger.debug(f"Selected {len(result.columns)} features: {list(result.columns)}")

    return result


def prepare_training_data(df: pd.DataFrame, target_col: str = "result") -> tuple:
    """Prepare feature matrix and target vector."""
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found")

    y = df[target_col]
    X = select_features(df.drop(columns=[target_col]))

    logger.info(f"Prepared training data: X shape {X.shape}, y shape {y.shape}")

    return X, y


# --- Advanced Features ---

def generate_synthetic_form_data(team_name: str, seed: Optional[int] = None) -> dict:
    """Generate synthetic form data for a team.
    
    Args:
        team_name: Name of the team
        seed: Random seed for reproducibility
        
    Returns:
        Dict with form statistics
    """
    if seed is None:
        seed = hash(team_name) % 100000
    np.random.seed(seed)
    
    # Simulate last 5 matches: W=3, D=1, L=0 points
    matches = np.random.choice(['W', 'D', 'L'], size=5, p=[0.4, 0.3, 0.3])
    points = sum(3 if m == 'W' else 1 if m == 'D' else 0 for m in matches)
    
    # Goals scored/conceded in last 5 matches
    goals_for = np.random.poisson(1.5, 5).sum()
    goals_against = np.random.poisson(1.2, 5).sum()
    
    return {
        'form_points': points,
        'form_wins': (matches == 'W').sum(),
        'form_draws': (matches == 'D').sum(),
        'form_losses': (matches == 'L').sum(),
        'form_goals_for': goals_for,
        'form_goals_against': goals_against,
        'form_goal_diff': goals_for - goals_against
    }


def generate_synthetic_injury_data(team_name: str, seed: Optional[int] = None) -> dict:
    """Generate synthetic injury data for a team.
    
    Args:
        team_name: Name of the team
        seed: Random seed for reproducibility
        
    Returns:
        Dict with injury statistics
    """
    if seed is None:
        seed = hash(team_name) % 100000 + 1000
    np.random.seed(seed)
    
    # Number of injured key players (0-3)
    num_injuries = np.random.choice([0, 1, 2, 3], p=[0.5, 0.3, 0.15, 0.05])
    
    # Impact score: 0 (no injuries) to 1 (severe)
    if num_injuries == 0:
        impact = 0.0
    else:
        impact = min(num_injuries * 0.15 + np.random.uniform(0, 0.2), 1.0)
    
    return {
        'injury_count': num_injuries,
        'injury_impact': impact
    }


def generate_synthetic_h2h_data(home_team: str, away_team: str, seed: Optional[int] = None) -> dict:
    """Generate synthetic head-to-head data.
    
    Args:
        home_team: Home team name
        away_team: Away team name
        seed: Random seed for reproducibility
        
    Returns:
        Dict with H2H statistics
    """
    if seed is None:
        seed = (hash(home_team) + hash(away_team)) % 100000
    np.random.seed(seed)
    
    # Simulate last 5 H2H matches
    home_wins = np.random.randint(0, 4)
    draws = np.random.randint(0, 3)
    away_wins = max(0, 5 - home_wins - draws)
    
    # Goals in H2H
    home_goals = np.random.poisson(1.5, 5).sum()
    away_goals = np.random.poisson(1.3, 5).sum()
    
    return {
        'h2h_home_wins': home_wins,
        'h2h_draws': draws,
        'h2h_away_wins': away_wins,
        'h2h_home_goals': home_goals,
        'h2h_away_goals': away_goals,
        'h2h_home_advantage': (home_wins - away_wins) / 5.0  # Normalized advantage
    }


def add_advanced_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add advanced features: form, injuries, H2H.
    
    Args:
        df: DataFrame with fixtures
        
    Returns:
        DataFrame with added advanced features
    """
    if df.empty:
        return df
    
    logger.info("Adding advanced features (form, injuries, H2H)...")
    
    # Initialize feature columns
    for prefix in ['home', 'away']:
        df[f'{prefix}_form_points'] = 0
        df[f'{prefix}_form_wins'] = 0
        df[f'{prefix}_form_goal_diff'] = 0
        df[f'{prefix}_injury_count'] = 0
        df[f'{prefix}_injury_impact'] = 0.0
    
    df['h2h_home_wins'] = 0
    df['h2h_away_wins'] = 0
    df['h2h_home_advantage'] = 0.0
    
    # Generate features for each match
    for idx, row in df.iterrows():
        if pd.notna(row.get('home')) and pd.notna(row.get('away')):
            home_team = str(row['home'])
            away_team = str(row['away'])
            
            # Home team form
            home_form = generate_synthetic_form_data(home_team)
            df.loc[idx, 'home_form_points'] = home_form['form_points']
            df.loc[idx, 'home_form_wins'] = home_form['form_wins']
            df.loc[idx, 'home_form_goal_diff'] = home_form['form_goal_diff']
            
            # Away team form
            away_form = generate_synthetic_form_data(away_team)
            df.loc[idx, 'away_form_points'] = away_form['form_points']
            df.loc[idx, 'away_form_wins'] = away_form['form_wins']
            df.loc[idx, 'away_form_goal_diff'] = away_form['form_goal_diff']
            
            # Home team injuries
            home_injuries = generate_synthetic_injury_data(home_team)
            df.loc[idx, 'home_injury_count'] = home_injuries['injury_count']
            df.loc[idx, 'home_injury_impact'] = home_injuries['injury_impact']
            
            # Away team injuries
            away_injuries = generate_synthetic_injury_data(away_team)
            df.loc[idx, 'away_injury_count'] = away_injuries['injury_count']
            df.loc[idx, 'away_injury_impact'] = away_injuries['injury_impact']
            
            # Head-to-head
            h2h = generate_synthetic_h2h_data(home_team, away_team)
            df.loc[idx, 'h2h_home_wins'] = h2h['h2h_home_wins']
            df.loc[idx, 'h2h_away_wins'] = h2h['h2h_away_wins']
            df.loc[idx, 'h2h_home_advantage'] = h2h['h2h_home_advantage']
    
    # Derived features
    df['form_differential'] = df['home_form_points'] - df['away_form_points']
    df['injury_differential'] = df['away_injury_impact'] - df['home_injury_impact']  # Positive = home advantage
    
    logger.info(f"Added {13} advanced feature columns")
    return df


# --- Sentiment Features ---

def add_sentiment_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add sentiment-based features using sentiment analyzer.
    
    Args:
        df: DataFrame with fixtures
        
    Returns:
        DataFrame with added sentiment features
    """
    if df.empty:
        return df
    
    logger.info("Adding sentiment features...")
    
    # Import here to avoid circular dependency
    from src.sentiment_analyzer import SentimentAnalyzer
    
    # Initialize analyzer
    analyzer = SentimentAnalyzer(model_type='synthetic')
    
    # Initialize feature columns
    df['sentiment_home'] = 0.0
    df['sentiment_away'] = 0.0
    df['sentiment_differential'] = 0.0
    df['sentiment_confidence'] = 0.0
    df['social_volume'] = 0
    df['sentiment_momentum_home'] = 0.0
    
    # Generate features for each match
    for idx, row in df.iterrows():
        if pd.notna(row.get('home')) and pd.notna(row.get('away')):
            home_team = str(row['home'])
            away_team = str(row['away'])
            
            # Get match sentiment
            sentiment = analyzer.get_match_sentiment(home_team, away_team, synthetic=True)
            
            df.loc[idx, 'sentiment_home'] = sentiment.get('sentiment_home', 0.0)
            df.loc[idx, 'sentiment_away'] = sentiment.get('sentiment_away', 0.0)
            df.loc[idx, 'sentiment_differential'] = sentiment.get('sentiment_differential', 0.0)
            df.loc[idx, 'sentiment_confidence'] = sentiment.get('sentiment_confidence', 0.0)
            df.loc[idx, 'social_volume'] = sentiment.get('social_volume', 0)
            df.loc[idx, 'sentiment_momentum_home'] = sentiment.get('sentiment_momentum_home', 0.0)
    
    logger.info(f"Added {6} sentiment feature columns")
    return df
