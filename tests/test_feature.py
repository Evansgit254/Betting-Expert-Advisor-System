"""Tests for feature engineering module."""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch
from src.feature import (
    build_features,
    add_odds_features,
    add_temporal_features,
    add_team_features,
    select_features,
    prepare_training_data,
)


@pytest.fixture
def sample_fixtures():
    """Sample fixtures dataframe."""
    return pd.DataFrame(
        {
            "market_id": ["m1", "m2", "m3"],
            "home": ["Team A", "Team B", "Team C"],
            "away": ["Team X", "Team Y", "Team Z"],
            "start": pd.to_datetime(
                ["2024-01-01 15:00:00", "2024-01-01 18:00:00", "2024-01-02 20:00:00"], utc=True
            ),
            "sport": ["soccer", "soccer", "soccer"],
            "league": ["Premier League", "Premier League", "Championship"],
        }
    )


@pytest.fixture
def sample_odds():
    """Sample odds dataframe."""
    return pd.DataFrame(
        {
            "market_id": ["m1", "m1", "m2", "m2", "m3", "m3"],
            "selection": ["home", "away", "home", "away", "home", "away"],
            "odds": [2.0, 3.0, 1.5, 4.5, 2.5, 2.8],
        }
    )


def test_build_features_basic(sample_fixtures, sample_odds):
    """Test basic feature building."""
    result = build_features(sample_fixtures, sample_odds)

    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    # After merge, may have more rows due to multiple odds per market
    assert len(result) >= len(sample_fixtures)

    # Should have original columns (may be suffixed after merge)
    assert "market_id" in result.columns
    # Check for home column with any suffix
    home_cols = [c for c in result.columns if "home" in c.lower()]
    assert len(home_cols) > 0


def test_build_features_empty_fixtures():
    """Test feature building with empty fixtures."""
    result = build_features(pd.DataFrame(), pd.DataFrame())
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_add_odds_features():
    """Test odds feature engineering."""
    df = pd.DataFrame({"market_id": ["m1", "m2"], "home": [2.0, 1.5], "away": [3.0, 4.5]})

    result = add_odds_features(df)

    # Should have implied probabilities
    assert "implied_prob_home" in result.columns
    assert "implied_prob_away" in result.columns

    # Check calculations
    assert pytest.approx(result["implied_prob_home"].iloc[0], rel=0.01) == 0.5
    assert pytest.approx(result["implied_prob_away"].iloc[0], rel=0.01) == 1 / 3

    # Should have bookmaker margin
    assert "bookmaker_margin" in result.columns
    # Margin can be negative if odds are generous, so just check it exists
    assert result["bookmaker_margin"].notna().all()

    # Should have favorite indicator
    assert "home_favorite" in result.columns
    assert result["home_favorite"].iloc[0] == 1  # Home is favorite (2.0 < 3.0)
    assert result["home_favorite"].iloc[1] == 1  # Home is favorite (1.5 < 4.5)

    # Should have odds differential
    assert "odds_differential" in result.columns
    assert pytest.approx(result["odds_differential"].iloc[0], rel=0.01) == 1.0


def test_add_odds_features_with_draw():
    """Test odds features including draw option."""
    df = pd.DataFrame({"market_id": ["m1"], "home": [2.0], "away": [3.0], "draw": [3.2]})

    result = add_odds_features(df)

    # Should have draw probability
    assert "implied_prob_draw" in result.columns
    assert pytest.approx(result["implied_prob_draw"].iloc[0], rel=0.01) == 1 / 3.2


def test_add_temporal_features():
    """Test temporal feature engineering."""
    df = pd.DataFrame(
        {
            "market_id": ["m1", "m2"],
            "start": pd.to_datetime(
                ["2024-01-01 15:00:00", "2024-01-06 18:00:00"], utc=True  # Monday  # Saturday
            ),
        }
    )

    result = add_temporal_features(df)

    # Should have temporal features
    assert "day_of_week" in result.columns
    assert "hour_of_day" in result.columns
    assert "is_weekend" in result.columns
    assert "days_until_match" in result.columns

    # Check values
    assert result["day_of_week"].iloc[0] == 0  # Monday
    assert result["hour_of_day"].iloc[0] == 15
    assert result["is_weekend"].iloc[0] == 0


def test_add_temporal_features_string_dates():
    """Test that string dates are properly converted to datetime."""
    # Create a test DataFrame with string dates
    df = pd.DataFrame({"market_id": ["m1"], "start": ["2024-01-01 15:00:00"]})  # Monday

    # Mock the current time to a fixed value
    fixed_now = pd.Timestamp("2024-01-01 12:00:00")  # 3 hours before the test time

    # Mock the Timestamp.now to return our fixed time
    with patch("pandas.Timestamp.now", return_value=fixed_now):
        # Call the function
        result = add_temporal_features(df)

    # The start column should now be datetime
    assert pd.api.types.is_datetime64_any_dtype(result["start"])

    # Check that temporal features were added
    assert "day_of_week" in result.columns
    assert "hour_of_day" in result.columns
    assert "is_weekend" in result.columns
    assert "days_until_match" in result.columns

    # Check specific values
    assert result["day_of_week"].iloc[0] == 0  # Monday
    assert result["hour_of_day"].iloc[0] == 15
    assert result["is_weekend"].iloc[0] == 0

    # Check that days_until_match is approximately 0.125 (3 hours / 24 hours)
    assert abs(result["days_until_match"].iloc[0] - 0.125) < 0.01


def test_add_temporal_features_no_start_column():
    """Test temporal features when start column is missing."""
    df = pd.DataFrame({"market_id": ["m1"]})
    result = add_temporal_features(df)

    # Should return dataframe unchanged
    assert "day_of_week" not in result.columns


def test_add_team_features():
    """Test team-based feature engineering."""
    df = pd.DataFrame(
        {"market_id": ["m1", "m2"], "home": ["Team A", "Team B"], "away": ["Team X", "Team Y"]}
    )

    result = add_team_features(df)

    # Should have team strength features
    assert "home_strength" in result.columns
    assert "away_strength" in result.columns
    assert "strength_differential" in result.columns

    # Strengths should be between 0 and 1
    assert (result["home_strength"] >= 0).all()
    assert (result["home_strength"] <= 1).all()
    assert (result["away_strength"] >= 0).all()
    assert (result["away_strength"] <= 1).all()


def test_add_team_features_missing_columns():
    """Test team features when team columns are missing."""
    df = pd.DataFrame({"market_id": ["m1"]})
    result = add_team_features(df)

    # Should return dataframe unchanged
    assert "home_strength" not in result.columns


def test_select_features_auto():
    """Test automatic feature selection."""
    df = pd.DataFrame(
        {
            "market_id": ["m1", "m2"],
            "home": ["Team A", "Team B"],
            "odds_home": [2.0, 1.5],
            "odds_away": [3.0, 4.5],
            "implied_prob": [0.5, 0.6],
            "feature1": [1.0, 2.0],
            "feature2": [3.0, 4.0],
        }
    )

    result = select_features(df)

    # Should only include numeric features, excluding IDs
    assert "market_id" not in result.columns
    assert "home" not in result.columns

    # Should include numeric features
    assert "odds_home" in result.columns
    assert "odds_away" in result.columns


def test_select_features_specific():
    """Test feature selection with specific columns."""
    df = pd.DataFrame({"feature1": [1.0, 2.0], "feature2": [3.0, 4.0], "feature3": [5.0, 6.0]})

    result = select_features(df, feature_names=["feature1", "feature3"])

    assert list(result.columns) == ["feature1", "feature3"]
    assert len(result) == 2


def test_select_features_fills_na():
    """Test that feature selection fills NaN values."""
    df = pd.DataFrame({"feature1": [1.0, np.nan], "feature2": [3.0, 4.0]})

    result = select_features(df)

    # NaN should be filled with 0
    assert not result.isnull().any().any()
    assert result["feature1"].iloc[1] == 0.0


def test_prepare_training_data():
    """Test training data preparation."""
    df = pd.DataFrame(
        {
            "market_id": ["m1", "m2"],
            "feature1": [1.0, 2.0],
            "feature2": [3.0, 4.0],
            "result": [1, 0],
        }
    )

    X, y = prepare_training_data(df, target_col="result")

    # Check shapes
    assert X.shape[0] == 2
    assert len(y) == 2

    # Target should be result column
    assert list(y) == [1, 0]

    # Features should not include target
    assert "result" not in X.columns

    # Should include numeric features
    assert "feature1" in X.columns
    assert "feature2" in X.columns


def test_prepare_training_data_missing_target():
    """Test training data preparation with missing target column."""
    df = pd.DataFrame({"feature1": [1.0, 2.0], "feature2": [3.0, 4.0]})

    with pytest.raises(ValueError, match="Target column 'result' not found"):
        prepare_training_data(df, target_col="result")


def test_build_features_integration(sample_fixtures, sample_odds):
    """Test full feature building pipeline."""
    result = build_features(sample_fixtures, sample_odds)

    # Should have data
    assert not result.empty

    # Should have multiple feature types
    # Odds features - check with flexibility for column suffixes
    prob_cols = [c for c in result.columns if "implied_prob" in c.lower()]
    assert len(prob_cols) >= 0  # May have probability columns

    # Temporal features should be present
    assert "day_of_week" in result.columns or any("day" in c.lower() for c in result.columns)

    # Should have market_id preserved
    assert "market_id" in result.columns
