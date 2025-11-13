"""Tests for data fetching module."""
import pytest
import pandas as pd
from datetime import datetime, timezone
from src.data_fetcher import DataSourceInterface, MockDataSource, DataFetcher


def test_mock_data_source_fetch_fixtures():
    """Test MockDataSource fixture fetching."""
    source = MockDataSource()
    fixtures = source.fetch_fixtures()

    assert isinstance(fixtures, pd.DataFrame)
    # May be empty if start_date filters all fixtures
    if not fixtures.empty:
        assert "market_id" in fixtures.columns
        assert "home" in fixtures.columns
        assert "away" in fixtures.columns
        assert "start" in fixtures.columns


def test_mock_data_source_fetch_fixtures_with_date_filter():
    """Test fixture fetching with date filtering."""
    source = MockDataSource()

    start_date = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 1, 23, 59, tzinfo=timezone.utc)

    fixtures = source.fetch_fixtures(start_date=start_date, end_date=end_date)

    assert isinstance(fixtures, pd.DataFrame)
    assert not fixtures.empty
    assert len(fixtures) == 2  # Only fixtures on Jan 1


def test_mock_data_source_fetch_odds():
    """Test MockDataSource odds fetching."""
    source = MockDataSource()
    market_ids = ["m1", "m2"]

    odds = source.fetch_odds(market_ids)

    assert isinstance(odds, pd.DataFrame)
    assert not odds.empty
    assert "market_id" in odds.columns
    assert "selection" in odds.columns
    assert "odds" in odds.columns

    # Should have at least home and away for each market
    assert len(odds) >= len(market_ids) * 2

    # Check odds are in valid range
    assert (odds["odds"] >= 1.01).all()
    assert (odds["odds"] <= 50.0).all()


def test_mock_data_source_odds_consistency():
    """Test that odds for same market are consistent across calls."""
    source = MockDataSource()

    odds1 = source.fetch_odds(["m1"])
    odds2 = source.fetch_odds(["m1"])

    # Should generate same odds for same market (deterministic seeding)
    assert odds1.equals(odds2)


def test_data_fetcher_initialization():
    """Test DataFetcher initialization."""
    # Default initialization (MockDataSource)
    fetcher = DataFetcher()
    assert isinstance(fetcher.source, MockDataSource)

    # Custom source
    custom_source = MockDataSource()
    fetcher = DataFetcher(source=custom_source)
    assert fetcher.source is custom_source


def test_data_fetcher_get_fixtures():
    """Test DataFetcher fixture retrieval."""
    fetcher = DataFetcher()
    # Use a past date to ensure we get fixtures
    from datetime import datetime, timezone

    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    fixtures = fetcher.get_fixtures(start_date=start_date)

    assert isinstance(fixtures, pd.DataFrame)
    if not fixtures.empty:
        assert "market_id" in fixtures.columns


def test_data_fetcher_get_odds():
    """Test DataFetcher odds retrieval."""
    fetcher = DataFetcher()
    odds = fetcher.get_odds(["m1", "m2"])

    assert isinstance(odds, pd.DataFrame)
    assert not odds.empty
    assert "market_id" in odds.columns
    assert "odds" in odds.columns


def test_data_fetcher_get_odds_empty_list():
    """Test DataFetcher with empty market ID list."""
    fetcher = DataFetcher()
    odds = fetcher.get_odds([])

    assert isinstance(odds, pd.DataFrame)
    assert odds.empty


def test_data_fetcher_get_fixtures_with_odds():
    """Test combined fixture and odds retrieval."""
    fetcher = DataFetcher()
    from datetime import datetime, timezone

    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    result = fetcher.get_fixtures_with_odds(start_date=start_date)

    assert isinstance(result, pd.DataFrame)

    # Should have fixture columns at minimum
    if not result.empty:
        assert "market_id" in result.columns
        assert "home" in result.columns or "home_x" in result.columns


def test_data_fetcher_get_fixtures_with_odds_date_filter():
    """Test combined retrieval with date filtering."""
    fetcher = DataFetcher()

    start_date = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 1, 23, 59, tzinfo=timezone.utc)

    result = fetcher.get_fixtures_with_odds(start_date=start_date, end_date=end_date)

    assert isinstance(result, pd.DataFrame)
    assert not result.empty

    # All fixtures should be within date range
    assert (result["start"] >= start_date).all()
    assert (result["start"] <= end_date).all()


class CustomMockSource(DataSourceInterface):
    """Custom mock source for testing."""

    def fetch_fixtures(self, start_date=None, end_date=None):
        return pd.DataFrame({"market_id": ["custom1"]})

    def fetch_odds(self, market_ids):
        return pd.DataFrame(
            {
                "market_id": market_ids,
                "selection": ["home"] * len(market_ids),
                "odds": [2.0] * len(market_ids),
            }
        )


def test_data_fetcher_custom_source():
    """Test DataFetcher with custom data source."""
    custom_source = CustomMockSource()
    fetcher = DataFetcher(source=custom_source)

    fixtures = fetcher.get_fixtures()
    assert "market_id" in fixtures.columns
    assert fixtures["market_id"].iloc[0] == "custom1"

    odds = fetcher.get_odds(["test1"])
    assert odds["odds"].iloc[0] == 2.0


def test_data_fetcher_no_fixtures():
    """Test handling when no fixtures are available."""

    class EmptyFixturesSource(DataSourceInterface):
        def fetch_fixtures(self, start_date=None, end_date=None):
            return pd.DataFrame()

        def fetch_odds(self, market_ids):
            return pd.DataFrame([{"market_id": "m1", "selection": "home", "odds": 2.0}])

    fetcher = DataFetcher(source=EmptyFixturesSource())

    # Test with no fixtures
    fixtures = fetcher.get_fixtures()
    assert fixtures.empty

    # Test get_fixtures_with_odds with no fixtures
    result = fetcher.get_fixtures_with_odds()
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_data_source_interface_methods():
    """Test that DataSourceInterface has the expected abstract methods."""
    # Get the abstract methods from the interface
    methods = DataSourceInterface.__abstractmethods__

    # Check that both required methods are present
    assert "fetch_fixtures" in methods
    assert "fetch_odds" in methods

    # Check the method signatures
    import inspect

    # Check fetch_fixtures signature
    fetch_fixtures_sig = inspect.signature(DataSourceInterface.fetch_fixtures)
    assert "start_date" in fetch_fixtures_sig.parameters
    assert "end_date" in fetch_fixtures_sig.parameters
    assert fetch_fixtures_sig.parameters["start_date"].default is None
    assert fetch_fixtures_sig.parameters["end_date"].default is None

    # Check fetch_odds signature
    fetch_odds_sig = inspect.signature(DataSourceInterface.fetch_odds)
    assert "market_ids" in fetch_odds_sig.parameters


def test_mock_data_source_draw_odds():
    """Test that draw odds are included in mock data based on random chance."""
    source = MockDataSource()

    # Test with a specific random seed to ensure consistent results
    import random

    random.seed(42)  # Fixed seed for reproducibility

    # Test with the same market ID to get consistent results
    odds = source.fetch_odds(["test_market"])

    # Verify we have at least home and away
    assert len(odds) >= 2
    assert set(odds["selection"].values) >= {"home", "away"}

    # The mock implementation has a 50% chance of including draw odds
    # With a fixed seed, we can check the exact behavior
    has_draw = "draw" in odds["selection"].values

    # For this specific test, we'll just verify the structure
    # rather than testing the random behavior
    if has_draw:
        assert len(odds) == 3  # home, away, draw
    else:
        assert len(odds) == 2  # just home and away


def test_get_fixtures_with_odds_no_odds(caplog):
    """Test get_fixtures_with_odds when no odds are available."""

    class NoOddsSource(DataSourceInterface):
        def fetch_fixtures(self, start_date=None, end_date=None):
            return pd.DataFrame(
                [
                    {
                        "market_id": "m1",
                        "home": "Team A",
                        "away": "Team B",
                        "start": datetime.now(timezone.utc),
                        "sport": "soccer",
                    }
                ]
            )

        def fetch_odds(self, market_ids):
            return pd.DataFrame()  # Empty DataFrame for odds

    fetcher = DataFetcher(source=NoOddsSource())

    # Clear any existing log captures
    caplog.clear()

    # This should log a warning but still return the fixtures
    result = fetcher.get_fixtures_with_odds()

    # Verify the warning was logged
    assert any("No odds found for fixtures" in message for message in caplog.messages)

    # Verify the result contains just the original fixture columns
    assert not result.empty
    expected_columns = {"market_id", "home", "away", "start", "sport"}
    assert set(result.columns) == expected_columns


def test_data_source_interface_abstract_methods():
    """Test that DataSourceInterface is abstract."""
    # Cannot instantiate abstract class
    with pytest.raises(TypeError):
        DataSourceInterface()


def test_mock_data_source_with_empty_market_ids():
    """Test MockDataSource with empty market IDs list."""
    source = MockDataSource()
    odds = source.fetch_odds([])

    assert isinstance(odds, pd.DataFrame)
    assert odds.empty
