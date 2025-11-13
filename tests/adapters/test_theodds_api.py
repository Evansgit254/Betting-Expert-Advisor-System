"""Tests for TheOddsAPI adapter."""
import sys
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
from requests.exceptions import HTTPError
from tenacity import RetryError


# Import the module after patching environment variables
@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("THEODDS_API_KEY", "test-api-key")
    monkeypatch.setenv("THEODDS_API_BASE", "https://api.example.com")
    monkeypatch.setenv("HTTP_TIMEOUT", "10")

    # Clear any existing module cache
    if "src.adapters.theodds_api" in sys.modules:
        del sys.modules["src.adapters.theodds_api"]

    # Import the module after setting up the environment
    from src.adapters import theodds_api

    return theodds_api


def test_get_success(setup_env):
    """Test successful GET request."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    mock_response.headers = {"x-requests-remaining": "100"}

    with patch("src.adapters.theodds_api.requests.get") as mock_get:
        from src.adapters.theodds_api import _get

        response = _get("/test")

        assert response == {"status": "success"}
        mock_get.assert_called_once_with(
            "https://api.example.com/test", params={"apiKey": "test-api-key"}, timeout=10
        )


def test_get_http_error(setup_env):
    """Test GET request with HTTP error."""
    from src.adapters.theodds_api import _get

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = HTTPError("Bad Request")

    with patch("src.adapters.theodds_api.requests.get", return_value=mock_response) as mock_get:
        with pytest.raises(RetryError):
            _get("/test")

        # Should retry 3 times (initial + 2 retries)
        assert mock_get.call_count == 3


def test_adapter_init(setup_env):
    """Test TheOddsAPIAdapter initialization."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    # Test with env vars
    adapter = TheOddsAPIAdapter()
    assert adapter.api_key == "test-api-key"
    assert adapter.base_url == "https://api.example.com"

    # Test with explicit parameters
    adapter = TheOddsAPIAdapter(api_key="custom-key", base_url="https://custom.example.com")
    assert adapter.api_key == "custom-key"
    assert adapter.base_url == "https://custom.example.com"


def test_fetch_fixtures_success(setup_env):
    """Test successful fetch_fixtures call."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    mock_response = [
        {
            "id": "match1",
            "commence_time": "2025-01-01T15:00:00Z",
            "home_team": "Team A",
            "away_team": "Team B",
            "sport_title": "Premier League",
            "bookmakers": [],
        }
    ]

    with patch("src.adapters.theodds_api._get", return_value=mock_response) as mock_get:
        adapter = TheOddsAPIAdapter()
        fixtures = adapter.fetch_fixtures(sport="soccer_epl", region="uk")

        assert len(fixtures) == 1
        assert fixtures[0]["market_id"] == "match1"
        assert fixtures[0]["home"] == "Team A"
        assert fixtures[0]["away"] == "Team B"
        assert fixtures[0]["sport"] == "soccer_epl"
        assert fixtures[0]["league"] == "Premier League"
        assert isinstance(fixtures[0]["start"], datetime)

        mock_get.assert_called_once_with(
            "/sports/soccer_epl/odds",
            params={"regions": "uk", "markets": "h2h", "oddsFormat": "decimal"},
        )


def test_fetch_fixtures_date_filtering(setup_env):
    """Test date filtering in fetch_fixtures."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    mock_response = [
        {
            "id": "match1",
            "commence_time": "2025-01-01T15:00:00Z",
            "home_team": "Team A",
            "away_team": "Team B",
            "sport_title": "Premier League",
            "bookmakers": [],
        },
        {
            "id": "match2",
            "commence_time": "2025-01-02T15:00:00Z",
            "home_team": "Team C",
            "away_team": "Team D",
            "sport_title": "Premier League",
            "bookmakers": [],
        },
    ]

    start_date = datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2025, 1, 2, 14, 0, 0, tzinfo=timezone.utc)

    with patch("src.adapters.theodds_api._get", return_value=mock_response):
        adapter = TheOddsAPIAdapter()

        # Test start date filter
        fixtures = adapter.fetch_fixtures(sport="soccer_epl", region="uk", start_date=start_date)
        assert len(fixtures) == 1
        assert fixtures[0]["market_id"] == "match2"

        # Test end date filter
        fixtures = adapter.fetch_fixtures(sport="soccer_epl", region="uk", end_date=end_date)
        assert len(fixtures) == 1
        assert fixtures[0]["market_id"] == "match1"


def test_fetch_odds_success(setup_env):
    """Test successful fetch_odds call."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    mock_response = [
        {
            "id": "match1",
            "commence_time": "2025-01-01T15:00:00Z",
            "home_team": "Team A",
            "away_team": "Team B",
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "title": "Pinnacle",
                    "last_update": "2025-01-01T14:00:00Z",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Team A", "price": 2.0},
                                {"name": "Team B", "price": 3.5},
                                {"name": "Draw", "price": 3.2},
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    with patch("src.adapters.theodds_api._get", return_value=mock_response) as mock_get:
        adapter = TheOddsAPIAdapter()
        odds = adapter.fetch_odds(sport="soccer_epl", region="uk")

        assert len(odds) == 3  # 3 outcomes
        assert odds[0] == {
            "market_id": "match1",
            "selection": "team a",
            "odds": 2.0,
            "provider": "Pinnacle",
            "last_update": "2025-01-01T14:00:00Z",
        }

        mock_get.assert_called_once_with(
            "/sports/soccer_epl/odds",
            params={"regions": "uk", "markets": "h2h", "oddsFormat": "decimal"},
        )


def test_fetch_odds_market_filtering(setup_env):
    """Test market ID filtering in fetch_odds."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    mock_response = [
        {
            "id": "match1",
            "commence_time": "2025-01-01T15:00:00Z",
            "home_team": "Team A",
            "away_team": "Team B",
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "title": "Pinnacle",
                    "last_update": "2025-01-01T14:00:00Z",
                    "markets": [{"key": "h2h", "outcomes": [{"name": "Team A", "price": 2.0}]}],
                }
            ],
        },
        {
            "id": "match2",
            "commence_time": "2025-01-01T15:00:00Z",
            "home_team": "Team C",
            "away_team": "Team D",
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "title": "Pinnacle",
                    "last_update": "2025-01-01T14:00:00Z",
                    "markets": [{"key": "h2h", "outcomes": [{"name": "Team C", "price": 1.8}]}],
                }
            ],
        },
    ]

    with patch("src.adapters.theodds_api._get", return_value=mock_response):
        adapter = TheOddsAPIAdapter()

        # Filter for match1 only
        odds = adapter.fetch_odds(sport="soccer_epl", region="uk", market_ids=["match1"])

        assert len(odds) == 1
        assert odds[0]["market_id"] == "match1"
        assert odds[0]["selection"] == "team a"


def test_get_available_sports_success(setup_env):
    """Test successful get_available_sports call."""
    mock_response = [
        {"key": "soccer_epl", "title": "Premier League"},
        {"key": "basketball_nba", "title": "NBA"},
    ]

    with patch("src.adapters.theodds_api._get", return_value=mock_response) as mock_get:
        from src.adapters.theodds_api import get_available_sports

        sports = get_available_sports()

        assert len(sports) == 2
        assert sports[0]["key"] == "soccer_epl"
        assert sports[1]["title"] == "NBA"

        mock_get.assert_called_once_with("/sports")


def test_fetch_fixtures_error_handling(setup_env, caplog):
    """Test error handling in fetch_fixtures."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    with patch("src.adapters.theodds_api._get", side_effect=Exception("API Error")):
        adapter = TheOddsAPIAdapter()
        fixtures = adapter.fetch_fixtures(sport="soccer_epl")

        assert fixtures == []
        assert "Failed to fetch fixtures" in caplog.text


def test_fetch_odds_error_handling(setup_env, caplog):
    """Test error handling in fetch_odds."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    with patch("src.adapters.theodds_api._get", side_effect=Exception("API Error")):
        adapter = TheOddsAPIAdapter()
        odds = adapter.fetch_odds(sport="soccer_epl")

        assert odds == []
        assert "Failed to fetch odds" in caplog.text


def test_get_available_sports_error_handling(setup_env, caplog):
    """Test error handling in get_available_sports."""
    with patch("src.adapters.theodds_api._get", side_effect=Exception("API Error")) as _:
        from src.adapters.theodds_api import get_available_sports

        with caplog.at_level("ERROR"):
            sports = get_available_sports()

        assert sports == []
        assert "Failed to fetch sports: API Error" in caplog.text


def test_fetch_fixtures_missing_commence_time(setup_env):
    """Test fetch_fixtures with missing commence_time."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    mock_response = [
        {
            "id": "match1",
            "home_team": "Team A",  # Missing commence_time
            "away_team": "Team B",
            "sport_title": "Premier League",
            "bookmakers": [],
        }
    ]

    with patch("src.adapters.theodds_api._get", return_value=mock_response):
        adapter = TheOddsAPIAdapter()
        fixtures = adapter.fetch_fixtures(sport="soccer_epl")

        assert len(fixtures) == 1
        assert fixtures[0]["start"] is None


def test_fetch_fixtures_missing_sport_title(setup_env):
    """Test fetch_fixtures with missing sport_title."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    mock_response = [
        {
            "id": "match1",
            "commence_time": "2025-01-01T15:00:00Z",
            "home_team": "Team A",
            "away_team": "Team B",
            # Missing sport_title
            "bookmakers": [],
        }
    ]

    with patch("src.adapters.theodds_api._get", return_value=mock_response):
        adapter = TheOddsAPIAdapter()
        fixtures = adapter.fetch_fixtures(sport="soccer_epl")

        assert len(fixtures) == 1
        assert fixtures[0]["league"] == "soccer_epl"  # Should fall back to sport parameter


def test_fetch_odds_empty_response(setup_env):
    """Test fetch_odds with empty response."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    with patch("src.adapters.theodds_api._get", return_value=[]):
        adapter = TheOddsAPIAdapter()
        odds = adapter.fetch_odds(sport="soccer_epl")

        assert odds == []


def test_fetch_odds_missing_market_key(setup_env):
    """Test fetch_odds with missing market key."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    mock_response = [
        {
            "id": "match1",
            "commence_time": "2025-01-01T15:00:00Z",
            "home_team": "Team A",
            "away_team": "Team B",
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "title": "Pinnacle",
                    "last_update": "2025-01-01T14:00:00Z",
                    "markets": [
                        {
                            # Missing 'key' field
                            "outcomes": [{"name": "Team A", "price": 2.0}]
                        }
                    ],
                }
            ],
        }
    ]

    with patch("src.adapters.theodds_api._get", return_value=mock_response):
        adapter = TheOddsAPIAdapter()
        odds = adapter.fetch_odds(sport="soccer_epl")

        # Should skip markets without a key
        assert odds == []


def test_adapter_init_without_api_key(setup_env, caplog):
    """Test TheOddsAPIAdapter initialization without API key."""
    with patch.dict("os.environ", {}, clear=True):
        from src.adapters.theodds_api import TheOddsAPIAdapter

        with caplog.at_level("WARNING"):
            adapter = TheOddsAPIAdapter()

        assert "TheOddsAPI key not configured" in caplog.text
        assert adapter.api_key is None


def test_fetch_fixtures_without_timezone(setup_env):
    """Test fetch_fixtures with datetime without timezone."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    mock_response = [
        {
            "id": "match1",
            "commence_time": "2025-01-01T15:00:00",  # No timezone
            "home_team": "Team A",
            "away_team": "Team B",
            "sport_title": "Premier League",
            "bookmakers": [],
        }
    ]

    with patch("src.adapters.theodds_api._get", return_value=mock_response):
        adapter = TheOddsAPIAdapter()
        fixtures = adapter.fetch_fixtures(sport="soccer_epl")

        assert len(fixtures) == 1
        assert fixtures[0]["start"].tzinfo is not None  # Should have timezone


def test_fetch_fixtures_parse_error(setup_env, caplog):
    """Test error handling when parsing event data."""
    from src.adapters.theodds_api import TheOddsAPIAdapter

    mock_response = [
        {
            "id": "match1",
            "commence_time": "invalid-date",  # Invalid date format
            "home_team": "Team A",
            "away_team": "Team B",
            "sport_title": "Premier League",
            "bookmakers": [],
        }
    ]

    with patch("src.adapters.theodds_api._get", return_value=mock_response):
        adapter = TheOddsAPIAdapter()

        with caplog.at_level("WARNING"):
            fixtures = adapter.fetch_fixtures(sport="soccer_epl")

        assert len(fixtures) == 0
        assert "Failed to parse event" in caplog.text
