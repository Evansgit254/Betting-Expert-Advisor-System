"""Test edge cases for database operations."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from src.db import db_retry, get_daily_loss, handle_db_errors, save_bet, update_bet_result


def test_save_bet_invalid_input():
    """Test save_bet with invalid input parameters."""
    # Test invalid market_id
    with pytest.raises(ValueError):
        save_bet("", "home", 100.0, 2.0)

    # Test invalid selection
    with pytest.raises(ValueError):
        save_bet("market1", "", 100.0, 2.0)

    # Test invalid stake
    with pytest.raises(ValueError):
        save_bet("market1", "home", -100.0, 2.0)

    # Test invalid odds
    with pytest.raises(ValueError):
        save_bet("market1", "home", 100.0, 0.5)  # Odds < 1.0


def test_update_bet_result_edge_cases():
    """Test edge cases for update_bet_result."""
    # Test non-existent bet
    assert update_bet_result(999999, "win", 100.0) is False

    # Test invalid bet_id
    with pytest.raises(ValueError):
        update_bet_result(0, "win", 100.0)

    # Test invalid result
    with pytest.raises(ValueError):
        update_bet_result(1, "invalid_result", 100.0)


def test_get_daily_loss_edge_cases():
    """Test edge cases for get_daily_loss."""
    # Test with very old date (no bets expected)
    old_date = datetime(2000, 1, 1)
    assert get_daily_loss(old_date) == 0.0

    # Test with future date (no bets expected)
    future_date = datetime.now(timezone.utc) + timedelta(days=365)
    assert get_daily_loss(future_date) == 0.0


def test_handle_db_errors():
    """Test the handle_db_errors context manager."""
    # Test successful operation
    with handle_db_errors() as session:
        assert session is not None

    # Test error handling
    with pytest.raises(SQLAlchemyError):
        with handle_db_errors():
            raise OperationalError("Test error", {}, None)


def test_db_retry_decorator():
    """Test the db_retry decorator."""
    # Create a mock function that fails twice then succeeds
    mock_func = MagicMock()
    mock_func.side_effect = [
        OperationalError("Test", {}, None),
        OperationalError("Test", {}, None),
        "success",
    ]

    # Apply the decorator
    retry_func = db_retry(retry_on=(OperationalError,))(mock_func)

    # Call the function
    result = retry_func()

    # Verify it retried and eventually succeeded
    assert result == "success"
    assert mock_func.call_count == 3


def test_concurrent_bet_updates():
    """Test that concurrent bet updates are handled correctly."""
    import random
    from concurrent.futures import ThreadPoolExecutor

    # Create a test bet
    bet = save_bet(
        market_id="concurrent_test",
        selection="home",
        stake=100.0,
        odds=2.0,
        idempotency_key=f"concurrent_test_{random.randint(1, 1000000)}",
        is_dry_run=True,
    )

    def update_bet():
        # Random delay to increase chance of race condition
        import time

        time.sleep(random.uniform(0.01, 0.1))
        return update_bet_result(bet.id, "win", 100.0)

    # Try to update the same bet from multiple threads
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(update_bet) for _ in range(5)]
        results = [f.result() for f in futures]

    # At least one update should succeed (SQLite allows multiple in this case)
    assert sum(1 for r in results if r is True) >= 1
