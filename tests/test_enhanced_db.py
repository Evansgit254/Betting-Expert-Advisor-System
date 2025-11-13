"""Tests for enhanced database operations with error handling and retries."""
import pytest
import random
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError
import time

from src.db import (
    save_bet,
    update_bet_result,
    get_daily_loss,
    get_session,
    get_open_bets_count,
    get_current_bankroll,
    BetRecord,
)
from src.utils import utc_now


def test_save_bet_concurrent_idempotency():
    """Test that concurrent saves with same idempotency key don't create duplicates."""
    from concurrent.futures import ThreadPoolExecutor

    idempotency_key = f"concurrent_test_{int(time.time())}"
    results = []

    def create_bet():
        try:
            bet = save_bet(
                market_id="concurrent_market",
                selection="home",
                stake=100.0,
                odds=2.0,
                idempotency_key=idempotency_key,
            )
            results.append(bet.id)
            return bet
        except Exception as e:
            results.append(str(e))
            raise

    # Run multiple threads trying to create the same bet
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_bet) for _ in range(5)]
        for future in futures:
            future.result()  # Wait for all to complete

    # Only one bet should be created, others should return the same instance
    assert len(set(results)) == 1
    assert len(results) == 5


def test_update_bet_result_concurrent():
    """Test that concurrent updates to the same bet are handled correctly."""
    # Clear any existing bets first
    with get_session() as session:
        session.query(BetRecord).delete()
        session.commit()

    # Create a test bet
    bet = save_bet(
        market_id="concurrent_update_test",
        selection="home",
        stake=100.0,
        odds=2.0,
        idempotency_key=f"concurrent_update_{int(time.time())}",
        is_dry_run=True,  # Use dry run to avoid affecting real bankroll
    )

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def update_bet(result, profit_loss):
        # Add a small random delay to increase chance of race condition
        time.sleep(random.uniform(0.01, 0.1))
        try:
            return update_bet_result(bet.id, result, profit_loss)
        except Exception as e:
            return str(e)

    # Try to update the same bet from multiple threads
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(update_bet, "win", 100.0),
            executor.submit(update_bet, "loss", -100.0),
            executor.submit(update_bet, "void", 0.0),
        ]

        # Get results as they complete
        success_count = 0
        for future in as_completed(futures):
            result = future.result()
            if result is True:
                success_count += 1

    # Verify at least one update succeeded (SQLite allows multiple concurrent updates)
    assert success_count >= 1, f"Expected at least one successful update, got {success_count}"

    # Verify the bet was updated with one of the results
    with get_session() as session:
        updated_bet = session.query(BetRecord).filter_by(id=bet.id).first()
        assert updated_bet.result in (
            "win",
            "loss",
            "void",
        ), "Bet should have been updated with a result"
        assert updated_bet.result != "pending", "Bet should no longer be in pending state"
        # Verify the final state - since it's a dry run, it shouldn't affect daily loss
        with patch("src.db.utc_now") as mock_utc_now:
            mock_utc_now.return_value = utc_now()
            loss = get_daily_loss()
            assert loss == 0.0, f"Expected 0.0 loss for dry run bet, got {loss}"


def test_retry_on_transient_failure():
    """Test that database operations are retried on transient failures."""
    # Create a bet first
    bet = save_bet(
        market_id="test_market_retry",
        selection="home",
        stake=100.0,
        odds=2.0,
        idempotency_key="test_retry_key",
    )

    # Create a mock session that fails twice then succeeds
    with patch("src.db.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Mock the query to fail twice then succeed
        mock_bet = MagicMock()
        mock_bet.id = bet.id
        mock_bet.result = "pending"

        mock_query = MagicMock()
        mock_query.filter_by.return_value.with_for_update.return_value.first.side_effect = [
            OperationalError("Temporary database issue", {}, {}),
            OperationalError("Still having issues", {}, {}),
            mock_bet,
        ]
        mock_session.query.return_value = mock_query

        # This should not raise an exception due to retry
        result = update_bet_result(bet.id, "win", 100.0)
        assert result is True

        # Verify the query was retried 3 times (2 failures + 1 success)
        assert mock_query.filter_by.return_value.with_for_update.return_value.first.call_count == 3


def test_error_handling_logging(caplog):
    """Test that errors are properly logged and handled."""
    with patch("src.db.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        mock_session.query.side_effect = OperationalError("Database error", {}, {})

        with pytest.raises(OperationalError):
            get_open_bets_count()

        # Verify error was logged
        assert "Database error" in caplog.text


def test_get_current_bankroll():
    """Test bankroll calculation with various bet outcomes."""
    # Clear existing bets
    with get_session() as session:
        session.query(BetRecord).delete()
        session.commit()

    # Create test bets with various outcomes
    bet1 = save_bet(
        market_id="bankroll_test_1",
        selection="home",
        stake=50.0,
        odds=3.0,
        is_dry_run=False,
        idempotency_key="bankroll_1",
    )
    update_bet_result(bet1.id, "win", 100.0)  # Won $100

    bet2 = save_bet(
        market_id="bankroll_test_2",
        selection="away",
        stake=50.0,
        odds=2.0,
        is_dry_run=False,
        idempotency_key="bankroll_2",
    )
    update_bet_result(bet2.id, "loss", -50.0)  # Lost $50

    bet3 = save_bet(
        market_id="bankroll_test_3",
        selection="home",
        stake=25.0,
        odds=4.0,
        is_dry_run=False,
        idempotency_key="bankroll_3",
    )
    update_bet_result(bet3.id, "win", 75.0)  # Won $75

    bet4 = save_bet(
        market_id="bankroll_test_4",
        selection="draw",
        stake=25.0,
        odds=2.0,
        is_dry_run=False,
        idempotency_key="bankroll_4",
    )
    update_bet_result(bet4.id, "loss", -25.0)  # Lost $25

    bankroll = get_current_bankroll()
    assert bankroll == 100.0  # 100 - 50 + 75 - 25 = 100


def test_get_daily_loss_with_timezone():
    """Test that daily loss calculation handles timezones correctly."""
    # Clear any existing bets
    with get_session() as session:
        session.query(BetRecord).delete()
        session.commit()

    # Create a test date in local timezone
    test_date = datetime(2023, 1, 1)  # No timezone specified

    # Create a bet with a known loss on the test date
    bet = save_bet(
        market_id="test_timezone_market",
        selection="home",
        stake=100.0,
        odds=2.0,
        idempotency_key="test_timezone_key",
        is_dry_run=False,
    )

    # Set the settled_at time to the test date (will be treated as UTC)
    with get_session() as session:
        bet = session.query(BetRecord).filter_by(id=bet.id).first()
        bet.result = "loss"
        bet.profit_loss = 100.0  # Positive value for loss
        bet.settled_at = datetime(
            2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc
        )  # Noon UTC on test date
        session.commit()

    # Test with naive datetime (should be treated as local time)
    loss = get_daily_loss(test_date)

    # The result should be 100.0 because the bet was placed on the test date in UTC
    # and we're querying for the same date in local time
    assert loss == 100.0, f"Expected 100.0 loss, got {loss}"
