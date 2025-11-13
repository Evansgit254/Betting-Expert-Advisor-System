"""Tests for Betfair Exchange API client."""
import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import HTTPError
from tenacity import RetryError

from src.adapters.betfair_exchange import BetfairExchangeClient, _post

# Test data
SAMPLE_MARKET_CATALOGUE = [
    {
        "marketId": "1.234567890",
        "marketName": "Match Odds",
        "event": {"name": "Team A vs Team B"},
        "runners": [
            {"selectionId": 1, "runnerName": "Team A"},
            {"selectionId": 2, "runnerName": "Team B"},
            {"selectionId": 3, "runnerName": "Draw"},
        ],
    }
]

SAMPLE_MARKET_BOOK = [
    {
        "marketId": "1.234567890",
        "runners": [{"selectionId": 1, "ex": {"availableToBack": [{"price": 2.0, "size": 100.0}]}}],
    }
]

SAMPLE_ORDER_RESPONSE = {
    "status": "SUCCESS",
    "instructionReports": [{"status": "SUCCESS", "betId": "1234567890"}],
}


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    # Clear any existing environment variables
    monkeypatch.delenv("BETFAIR_API_BASE", raising=False)
    monkeypatch.delenv("BETFAIR_APP_KEY", raising=False)
    monkeypatch.delenv("BETFAIR_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("HTTP_TIMEOUT", raising=False)

    # Set test values
    monkeypatch.setenv("BETFAIR_API_BASE", "https://api.betfair.com")
    monkeypatch.setenv("BETFAIR_APP_KEY", "test_app_key")
    monkeypatch.setenv("BETFAIR_SESSION_TOKEN", "test_session_token")
    monkeypatch.setenv("HTTP_TIMEOUT", "10")

    # Also set the module-level variables directly for tests that import them
    import src.adapters.betfair_exchange as bf

    bf.BASE = "https://api.betfair.com"
    bf.APP_KEY = "test_app_key"
    bf.SESSION_TOKEN = "test_session_token"
    bf.TIMEOUT = 10


@pytest.fixture
def betfair_client():
    """Create a BetfairExchangeClient instance for testing."""
    return BetfairExchangeClient()


def test_betfair_client_initialization():
    """Test Betfair client initialization."""
    client = BetfairExchangeClient(
        base_url="https://api.betfair.com",
        app_key="test_app_key",
        session_token="test_session_token",
    )
    assert client.base_url == "https://api.betfair.com"
    assert client.app_key == "test_app_key"
    assert client.session_token == "test_session_token"


def test_betfair_client_partial_initialization(caplog):
    """Test client initialization with partial config."""
    # Clear any existing environment variables
    with patch.dict("os.environ", {}, clear=True):
        # Clear the module-level variables
        import src.adapters.betfair_exchange as bf

        original_vars = {k: getattr(bf, k) for k in ["BASE", "APP_KEY", "SESSION_TOKEN"]}

        try:
            # Reset module variables
            bf.BASE = None
            bf.APP_KEY = None
            bf.SESSION_TOKEN = None

            # Test with no config - should log a warning
            with caplog.at_level("WARNING"):
                caplog.clear()
                client = BetfairExchangeClient()
                # Check that the warning was logged
                assert any(
                    "Betfair client not fully configured" in record.message
                    for record in caplog.records
                )

            # Test with partial config - should still log a warning
            with caplog.at_level("WARNING"):
                caplog.clear()
                client = BetfairExchangeClient(
                    base_url="https://api.betfair.com",
                    # Missing app_key and session_token
                )
                assert any(
                    "Betfair client not fully configured" in record.message
                    for record in caplog.records
                )

            # Test with full config - should not log a warning
            with caplog.at_level("WARNING"):
                caplog.clear()
                client = BetfairExchangeClient(
                    base_url="https://api.betfair.com",
                    app_key="test_key",
                    session_token="test_token",
                )
                assert not any(
                    "Betfair client not fully configured" in record.message
                    for record in caplog.records
                )

            # Verify the client was properly initialized
            assert client.base_url == "https://api.betfair.com"
            assert client.app_key == "test_key"
            assert client.session_token == "test_token"

        finally:
            # Restore original module variables
            for k, v in original_vars.items():
                setattr(bf, k, v)

    # Test with explicit parameters (outside the patch context)
    client = BetfairExchangeClient(
        base_url="https://api.betfair.com", app_key="custom_key", session_token="custom_token"
    )
    assert client.base_url == "https://api.betfair.com"
    assert client.app_key == "custom_key"
    assert client.session_token == "custom_token"


@patch("src.adapters.betfair_exchange.requests")
def test_post_success(mock_requests, mock_env_vars):
    """Test successful POST request."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "success"}
    mock_requests.post.return_value = mock_response

    # Make request
    response = _post("/test", json={"key": "value"})

    # Verify request
    mock_requests.post.assert_called_once()
    args, kwargs = mock_requests.post.call_args
    assert args[0] == "https://api.betfair.com/test"  # First positional arg is URL
    assert kwargs["json"] == {"key": "value"}
    assert kwargs["headers"]["X-Application"] == "test_app_key"
    assert kwargs["headers"]["X-Authentication"] == "test_session_token"
    assert response == {"result": "success"}


@patch("src.adapters.betfair_exchange.requests")
def test_post_http_error(mock_requests, mock_env_vars):
    """Test POST request with HTTP error."""
    # Setup mock to raise HTTPError
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = HTTPError("Bad Request")
    mock_requests.post.return_value = mock_response

    # Test that RetryError is raised after all retries are exhausted
    with pytest.raises(RetryError):
        _post("/test")


@patch("src.adapters.betfair_exchange._post")
def test_place_limit_order_success(mock_post, betfair_client):
    """Test successful limit order placement."""
    # Setup mock
    mock_post.return_value = SAMPLE_ORDER_RESPONSE

    # Place order
    response = betfair_client.place_limit_order(
        market_id="1.234567890",
        selection_id=1,
        size=100.0,
        price=2.0,
        side="BACK",
        persistence_type="LAPSE",
    )

    # Verify request
    expected_payload = {
        "marketId": "1.234567890",
        "instructions": [
            {
                "selectionId": 1,
                "handicap": 0,
                "side": "BACK",
                "orderType": "LIMIT",
                "limitOrder": {"size": 100.0, "price": 2.0, "persistenceType": "LAPSE"},
            }
        ],
    }
    mock_post.assert_called_once_with(
        "/exchange/betting/rest/v1.0/placeOrders/", json=expected_payload
    )
    assert response == SAMPLE_ORDER_RESPONSE


@patch("src.adapters.betfair_exchange._post")
def test_place_limit_order_failure(mock_post, betfair_client, caplog):
    """Test order placement with API error."""
    # Setup mock to return error response
    error_response = {"status": "FAILURE", "errorCode": "INSUFFICIENT_FUNDS"}
    mock_post.return_value = error_response

    # Test that exception is raised
    with pytest.raises(Exception, match="Betfair error: INSUFFICIENT_FUNDS"):
        betfair_client.place_limit_order(
            market_id="1.234567890", selection_id=1, size=100.0, price=2.0
        )

    # Verify error was logged
    assert "Betfair order failed: INSUFFICIENT_FUNDS" in caplog.text


@patch("src.adapters.betfair_exchange._post")
def test_list_market_catalogue_success(mock_post, betfair_client):
    """Test successful market catalogue query."""
    # Setup mock
    mock_post.return_value = SAMPLE_MARKET_CATALOGUE

    # Query market catalogue
    result = betfair_client.list_market_catalogue(
        event_type_ids=["1"], market_countries=["GB"], max_results=10
    )

    # Verify request
    expected_payload = {
        "filter": {"eventTypeIds": ["1"], "marketCountries": ["GB"]},
        "maxResults": 10,
        "marketProjection": [
            "COMPETITION",
            "EVENT",
            "EVENT_TYPE",
            "MARKET_START_TIME",
            "RUNNER_DESCRIPTION",
        ],
    }
    mock_post.assert_called_once_with(
        "/exchange/betting/rest/v1.0/listMarketCatalogue/", json=expected_payload
    )
    assert result == SAMPLE_MARKET_CATALOGUE


@patch("src.adapters.betfair_exchange._post")
def test_list_market_catalogue_error(mock_post, betfair_client, caplog):
    """Test market catalogue query with error."""
    # Setup mock to raise exception
    mock_post.side_effect = Exception("API Error")

    # Query market catalogue
    result = betfair_client.list_market_catalogue(event_type_ids=["1"])

    # Verify error was logged and empty list returned
    assert "Error fetching market catalogue: API Error" in caplog.text
    assert result == []


@patch("src.adapters.betfair_exchange._post")
def test_get_market_book_success(mock_post, betfair_client):
    """Test successful market book query."""
    # Setup mock
    mock_post.return_value = SAMPLE_MARKET_BOOK

    # Get market book
    market_ids = ["1.234567890"]
    result = betfair_client.get_market_book(market_ids)

    # Verify request
    expected_payload = {
        "marketIds": market_ids,
        "priceProjection": {"priceData": ["EX_BEST_OFFERS"], "virtualise": False},
    }
    mock_post.assert_called_once_with(
        "/exchange/betting/rest/v1.0/listMarketBook/", json=expected_payload
    )
    assert result == SAMPLE_MARKET_BOOK


@patch("src.adapters.betfair_exchange._post")
def test_get_market_book_error(mock_post, betfair_client, caplog):
    """Test market book query with error."""
    # Setup mock to raise exception
    mock_post.side_effect = Exception("API Error")

    # Get market book
    result = betfair_client.get_market_book(["1.234567890"])

    # Verify error was logged and empty list returned
    assert "Error fetching market book: API Error" in caplog.text
    assert result == []


@patch("src.adapters.betfair_exchange.requests")
def test_retry_on_failure(mock_requests):
    """Test that _post retries on failure."""
    # First two attempts fail, third succeeds
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"result": "success"}

    # Configure the mock to raise an exception first, then return a successful response
    mock_requests.post.side_effect = [
        HTTPError("First failure"),
        HTTPError("Second failure"),
        mock_response_success,
    ]

    # This should succeed after retries
    response = _post("/test")
    assert response == {"result": "success"}
    assert mock_requests.post.call_count == 3


@patch("src.adapters.betfair_exchange.requests")
def test_retry_gives_up_after_attempts(mock_requests, mock_env_vars):
    """Test that _post gives up after max retries."""
    # All attempts fail
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = HTTPError("Failed")
    mock_requests.post.return_value = mock_response

    # Should raise RetryError after 3 attempts
    with pytest.raises(RetryError) as exc_info:
        _post("/test")

    # Verify it was called 3 times (initial + 2 retries)
    assert mock_requests.post.call_count == 3

    # Verify the exception contains the original HTTPError
    assert isinstance(exc_info.value.last_attempt.exception(), HTTPError)
