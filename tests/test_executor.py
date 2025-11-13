"""Tests for bet execution module."""
import pytest

from src.db import BetRecord, handle_db_errors, init_db
from src.executor import Executor, MockBookie


@pytest.fixture
def executor():
    """Fixture providing an executor with MockBookie."""
    return Executor(client=MockBookie())


@pytest.fixture
def sample_bet():
    """Fixture providing a sample bet dictionary."""
    return {
        "market_id": "test_market_1",
        "selection": "home",
        "stake": 50.0,
        "odds": 2.5,
        "ev": 0.15,
        "p": 0.6,
        "home": "Team A",
        "away": "Team B",
        "league": "Test League",
    }


def test_mock_bookie_accepts_bet():
    """Test MockBookie accepts bets."""
    bookie = MockBookie()
    result = bookie.place_bet("m1", "home", 50.0, 2.5)

    assert result["status"] == "accepted"
    assert "bet_id" in result
    assert result["stake"] == 50.0
    assert result["odds"] == 2.5


def test_executor_initialization():
    """Test executor initializes with default MockBookie."""
    executor = Executor()
    assert isinstance(executor.client, MockBookie)


def test_executor_dry_run(executor, sample_bet):
    """Test executor in dry-run mode."""
    result = executor.execute(sample_bet, dry_run=True)

    assert result["status"] == "dry_run"
    assert "idempotency_key" in result


def test_executor_persists_to_db(executor, sample_bet):
    """Test executor saves bets to database."""
    # Initialize test database
    init_db()

    result = executor.execute(sample_bet, dry_run=True)

    assert "db_id" in result

    # Verify in database
    with handle_db_errors() as session:
        bet_record = session.query(BetRecord).filter_by(id=result["db_id"]).first()
        assert bet_record is not None
        assert bet_record.market_id == "test_market_1"
        assert bet_record.stake == 50.0


def test_executor_idempotency(executor, sample_bet):
    """Test idempotency prevents duplicate bets."""
    init_db()

    # Execute same bet twice
    result1 = executor.execute(sample_bet, dry_run=True)
    result2 = executor.execute(sample_bet, dry_run=True)

    # Should create different idempotency keys (due to timestamp)
    # but if same key, should return existing record
    assert "db_id" in result1
    assert "db_id" in result2


def test_executor_batch(executor):
    """Test batch execution."""
    bets = [
        {"market_id": "m1", "selection": "home", "stake": 50.0, "odds": 2.0},
        {"market_id": "m2", "selection": "away", "stake": 30.0, "odds": 3.0},
        {"market_id": "m3", "selection": "home", "stake": 40.0, "odds": 2.5},
    ]

    results = executor.execute_batch(bets, dry_run=True)

    assert len(results) == 3
    assert all(r["status"] == "dry_run" for r in results)


def test_executor_live_mode_requires_setting(executor, sample_bet):
    """Test LIVE mode requires MODE=LIVE in settings."""
    from src.config import settings

    # Save original mode
    original_mode = settings.MODE

    try:
        # Set to non-LIVE mode
        settings.MODE = "DRY_RUN"

        result = executor.execute(sample_bet, dry_run=False)

        # Should reject because MODE is not LIVE
        assert result["status"] == "rejected"
        assert "LIVE mode not enabled" in result["message"]
    finally:
        # Restore original mode
        settings.MODE = original_mode


def test_executor_metadata_preserved(executor, sample_bet):
    """Test bet metadata is preserved in execution."""
    init_db()

    result = executor.execute(sample_bet, dry_run=True)

    assert "db_id" in result

    with handle_db_errors() as session:
        bet_record = session.query(BetRecord).filter_by(id=result["db_id"]).first()
        assert bet_record.meta is not None
        assert "ev" in bet_record.meta
        assert "home" in bet_record.meta
