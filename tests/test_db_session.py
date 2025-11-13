"""Tests for database session management."""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from src.db import BetRecord, handle_db_errors


def test_get_session_success():
    """Test that get_session works correctly in the happy path."""
    with handle_db_errors() as session:
        assert session is not None
        # Verify we can perform a simple query
        result = session.query(BetRecord).first()
        assert result is None or isinstance(result, BetRecord)


def test_get_session_rollback_on_error():
    """Test that session rolls back on error."""
    # Create a test bet
    with handle_db_errors() as session:
        bet = BetRecord(
            market_id="test_market", selection="home", stake=100.0, odds=2.0, is_dry_run=True
        )
        session.add(bet)
        session.commit()
        bet_id = bet.id

    # Now try to update in a session that will fail
    try:
        with handle_db_errors() as session:
            bet = session.query(BetRecord).filter_by(id=bet_id).first()
            bet.stake = 200.0
            # Force an error
            raise ValueError("Test error")
    except ValueError:
        pass

    # Verify the change was rolled back
    with handle_db_errors() as session:
        bet = session.query(BetRecord).filter_by(id=bet_id).first()
        assert bet.stake == 100.0  # Should still be the original value


def test_get_session_database_error():
    """Test that database errors are properly propagated."""
    with patch("src.db.SessionLocal") as mock_session_local:
        # Setup mock to raise an error on commit
        mock_session = MagicMock()
        mock_session.commit.side_effect = OperationalError("Test error", {}, None)
        mock_session_local.return_value = mock_session

        with pytest.raises(SQLAlchemyError):
            with handle_db_errors() as session:
                session.query(BetRecord).first()

        # Verify rollback was called
        assert mock_session.rollback.called
        # Verify session was closed
        assert mock_session.close.called


def test_get_session_close_on_exception():
    """Test that session is properly closed even if an exception occurs."""
    with patch("src.db.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        try:
            with handle_db_errors():
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify session was closed even though an exception was raised
        assert mock_session.close.called


def test_get_session_nested_transactions():
    """Test that nested sessions work correctly."""
    # Create a bet in the first session
    with handle_db_errors() as session1:
        bet = BetRecord(
            market_id="nested_test", selection="home", stake=100.0, odds=2.0, is_dry_run=True
        )
        session1.add(bet)
        session1.commit()
        bet_id = bet.id

    # Verify the bet exists in a new session
    with handle_db_errors() as session2:
        bet = session2.query(BetRecord).filter_by(id=bet_id).first()
        assert bet is not None
        assert bet.market_id == "nested_test"

        # Update the bet in this session
        bet.stake = 200.0
        session2.commit()

    # Verify the update was saved
    with handle_db_errors() as session3:
        bet = session3.query(BetRecord).filter_by(id=bet_id).first()
        assert bet.stake == 200.0


# Clean up after tests
@pytest.fixture(autouse=True)
def cleanup_after_tests():
    """Clean up any test data after each test."""
    yield
    with handle_db_errors() as session:
        session.query(BetRecord).filter(
            (BetRecord.market_id == "test_market") | (BetRecord.market_id == "nested_test")
        ).delete(synchronize_session=False)
        session.commit()
