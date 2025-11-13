"""Tests for Pinnacle client."""
import sys
from unittest.mock import patch, MagicMock
import pytest
from requests.exceptions import HTTPError
from tenacity import RetryError


# Import the module after patching environment variables
@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("BOOKIE_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("BOOKIE_API_KEY", "test-api-key")
    monkeypatch.setenv("HTTP_TIMEOUT", "10")

    # Clear any existing module cache
    if "src.adapters.pinnacle_client" in sys.modules:
        del sys.modules["src.adapters.pinnacle_client"]

    # Import the module after setting up the environment
    from src.adapters import pinnacle_client

    return pinnacle_client


# Remove this fixture as we're using autouse fixture now


def test_post_success(setup_env):
    """Test successful POST request."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}

    with patch(
        "src.adapters.pinnacle_client.requests.post", return_value=mock_response
    ) as mock_post:
        from src.adapters.pinnacle_client import _post

        response = _post("/test")

        assert response == {"status": "success"}
        mock_post.assert_called_once_with(
            "https://api.example.com/test",
            json=None,
            headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
            timeout=10,
        )


def test_post_http_error(setup_env):
    """Test POST request with HTTP error."""
    from src.adapters.pinnacle_client import _post

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = HTTPError("Bad Request")

    with patch(
        "src.adapters.pinnacle_client.requests.post", return_value=mock_response
    ) as mock_post:
        with pytest.raises(RetryError):
            _post("/test")

        # Should retry 3 times (initial + 2 retries)
        assert mock_post.call_count == 3


def test_pinnacle_client_init(setup_env):
    """Test Pinnacle client initialization."""
    # Test with env vars
    from src.adapters.pinnacle_client import PinnacleClient

    client = PinnacleClient()
    assert client.base_url == "https://api.example.com"
    assert client.api_key == "test-api-key"

    # Test with explicit parameters
    client = PinnacleClient(base_url="https://custom.example.com", api_key="custom-key")
    assert client.base_url == "https://custom.example.com"
    assert client.api_key == "custom-key"


def test_pinnacle_client_place_bet_success(setup_env):
    """Test successful bet placement."""
    mock_response = {"status": "ACCEPTED", "bet_id": "12345", "stake": 100.0, "odds": 2.0}

    with patch("src.adapters.pinnacle_client._post", return_value=mock_response) as mock_post:
        from src.adapters.pinnacle_client import PinnacleClient

        client = PinnacleClient()
        response = client.place_bet(
            market_id="1.23456789",
            selection="Team A",
            stake=100.0,
            odds=2.0,
            idempotency_key="abc123",
        )

        assert response == mock_response
        mock_post.assert_called_once_with(
            "/bets",
            json={
                "market_id": "1.23456789",
                "selection": "Team A",
                "stake": 100.0,
                "odds": 2.0,
                "client_ref": "abc123",
            },
            headers={"Idempotency-Key": "abc123"},
        )


def test_pinnacle_client_place_bet_http_error(setup_env, caplog):
    """Test bet placement with HTTP error that triggers retry."""
    from src.adapters.pinnacle_client import PinnacleClient
    from tenacity import RetryError

    # Create a mock response with status code 400 and error text
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"error": "Invalid request"}'
    mock_response.json.return_value = {"error": "Invalid request"}

    # Create a side effect that raises HTTPError when raise_for_status is called
    def raise_http_error():
        raise HTTPError(
            "400 Client Error: Bad Request for url: https://api.example.com/bets",
            response=mock_response,
        )

    mock_response.raise_for_status.side_effect = raise_http_error

    # Patch requests.post to return our mock response
    with patch(
        "src.adapters.pinnacle_client.requests.post", return_value=mock_response
    ) as mock_post:
        client = PinnacleClient()

        # Clear any existing logs
        caplog.clear()

        with caplog.at_level("ERROR"):
            with pytest.raises(RetryError):
                client.place_bet(
                    market_id="1.23456789",
                    selection="Team A",
                    stake=100.0,
                    odds=2.0,
                    idempotency_key="test-idempotency-key",
                )

        # Verify the error was logged
        assert any("Error placing bet: RetryError" in record.message for record in caplog.records)

        # Verify the request was made with the correct parameters
        assert mock_post.call_count == 3  # 1 initial + 2 retries

        # Check the first call
        args, kwargs = mock_post.call_args_list[0]
        assert args[0] == "https://api.example.com/bets"
        assert kwargs["json"] == {
            "market_id": "1.23456789",
            "selection": "Team A",
            "stake": 100.0,
            "odds": 2.0,
            "client_ref": "test-idempotency-key",
        }
        assert kwargs["headers"] == {
            "Authorization": "Bearer test-api-key",
            "Content-Type": "application/json",
            "Idempotency-Key": "test-idempotency-key",
        }

    # Create a mock response with status code 400 and error text
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"error": "Invalid request"}'
    mock_response.json.return_value = {"error": "Invalid request"}

    # Create a side effect that raises HTTPError when raise_for_status is called
    def raise_http_error():
        raise HTTPError(
            "400 Client Error: Bad Request for url: https://api.example.com/bets",
            response=mock_response,
        )

    mock_response.raise_for_status.side_effect = raise_http_error

    # Patch requests.post to return our mock response
    with patch(
        "src.adapters.pinnacle_client.requests.post", return_value=mock_response
    ) as mock_post:
        client = PinnacleClient()

        # Clear any existing logs
        caplog.clear()

        with caplog.at_level("ERROR"):
            with pytest.raises(RetryError):
                client.place_bet(
                    market_id="1.23456789",
                    selection="Team A",
                    stake=100.0,
                    odds=2.0,
                    idempotency_key="test-idempotency-key",
                )

        # Verify the error was logged with the expected message
        assert any("Error placing bet: RetryError" in record.message for record in caplog.records)

        # Verify the request was made with the correct parameters
        assert mock_post.call_count == 3  # 1 initial + 2 retries

        # Check the first call
        args, kwargs = mock_post.call_args_list[0]
        assert args[0] == "https://api.example.com/bets"
        assert kwargs["json"] == {
            "market_id": "1.23456789",
            "selection": "Team A",
            "stake": 100.0,
            "odds": 2.0,
            "client_ref": "test-idempotency-key",
        }
        assert kwargs["headers"] == {
            "Authorization": "Bearer test-api-key",
            "Content-Type": "application/json",
            "Idempotency-Key": "test-idempotency-key",
        }


def test_pinnacle_client_place_bet_http_error_direct(setup_env, caplog):
    """Test direct HTTP error handling in place_bet method."""
    from src.adapters.pinnacle_client import PinnacleClient
    from requests.exceptions import HTTPError

    # Create a mock response with status code 400 and error text
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"error": "Invalid request"}'
    mock_response.json.return_value = {"error": "Invalid request"}

    # Create a mock _post function that raises HTTPError
    def mock_post_http_error(*args, **kwargs):
        raise HTTPError("400 Client Error: Bad Request", response=mock_response)

    # Patch the _post function in the module
    with patch("src.adapters.pinnacle_client._post", side_effect=mock_post_http_error):
        client = PinnacleClient()

        # Clear any existing logs
        caplog.clear()

        with caplog.at_level("ERROR"):
            with pytest.raises(HTTPError):
                client.place_bet(
                    market_id="1.23456789",
                    selection="Team A",
                    stake=100.0,
                    odds=2.0,
                    idempotency_key="test-idempotency-key",
                )

        # Verify the error was logged with the expected message
        assert any(
            "HTTP error placing bet: 400 - {" in record.message
            and "Invalid request" in record.message
            for record in caplog.records
        )


def test_pinnacle_client_not_implemented_methods(setup_env):
    """Test that not implemented methods raise NotImplementedError."""
    from src.adapters.pinnacle_client import PinnacleClient

    client = PinnacleClient()

    with pytest.raises(NotImplementedError):
        client.get_bet_status("12345")

    with pytest.raises(NotImplementedError):
        client.cancel_bet("12345")


def test_pinnacle_client_missing_config(caplog, monkeypatch):
    """Test client initialization with missing config."""
    # Clear any existing module cache
    if "src.adapters.pinnacle_client" in sys.modules:
        del sys.modules["src.adapters.pinnacle_client"]

    # Ensure environment variables are not set
    monkeypatch.delenv("BOOKIE_API_BASE_URL", raising=False)
    monkeypatch.delenv("BOOKIE_API_KEY", raising=False)

    # Import after clearing environment
    from src.adapters.pinnacle_client import PinnacleClient

    with caplog.at_level("WARNING"):
        client = PinnacleClient()
        assert any(
            "Pinnacle client not fully configured" in record.message for record in caplog.records
        )

    # Verify the client was still created
    assert isinstance(client, PinnacleClient)
