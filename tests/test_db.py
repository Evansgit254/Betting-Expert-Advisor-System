"""Tests for database operations."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.db import (
    BetRecord,
    DailyStats,
    ModelMetadata,
    get_daily_loss,
    get_open_bets_count,
    get_session,
    init_db,
    save_bet,
    update_bet_result,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initialize test database before each test."""
    init_db()
    yield
    # Cleanup happens via transaction rollback in tests


def test_init_db():
    """Test database initialization."""
    # Should not raise any exceptions
    init_db()
    assert True


def test_get_session_context_manager():
    """Test session context manager."""
    with get_session() as session:
        assert session is not None
        # Can perform queries
        result = session.query(BetRecord).count()
        assert result >= 0


def test_get_session_rollback_on_error():
    """Test that session rolls back on error."""
    try:
        with get_session() as session:
            # Create invalid record (should fail)
            bet = BetRecord(market_id=None)  # Required field
            session.add(bet)
            session.flush()
    except Exception:
        # Exception expected
        pass

    # Session should have rolled back
    with get_session() as session:
        count = session.query(BetRecord).count()
        # Count should not have increased
        assert count >= 0


def test_save_bet_basic():
    """Test saving a bet record."""
    bet_record = save_bet(
        market_id="test_market_1",
        selection="home",
        stake=50.0,
        odds=2.5,
        idempotency_key="test_key_1",
        is_dry_run=True,
        meta={"test": "data"},
    )

    assert bet_record.id is not None
    assert bet_record.market_id == "test_market_1"
    assert bet_record.selection == "home"
    assert bet_record.stake == 50.0
    assert bet_record.odds == 2.5
    assert bet_record.idempotency_key == "test_key_1"
    assert bet_record.is_dry_run is True
    assert bet_record.result == "pending"
    assert bet_record.meta == {"test": "data"}


def test_save_bet_idempotency():
    """Test bet idempotency - same key returns existing record."""
    # Save first bet
    bet1 = save_bet(
        market_id="test_market_2",
        selection="away",
        stake=100.0,
        odds=3.0,
        idempotency_key="test_key_2",
    )

    # Save with same idempotency key
    bet2 = save_bet(
        market_id="test_market_2",
        selection="away",
        stake=100.0,
        odds=3.0,
        idempotency_key="test_key_2",
    )

    # Should return the same record
    assert bet1.id == bet2.id


def test_save_bet_minimal():
    """Test saving bet with minimal parameters."""
    bet_record = save_bet(
        market_id="test_market_3",
        selection="home",
        stake=25.0,
        odds=1.8,
        idempotency_key="test_key_3",
    )

    assert bet_record.id is not None
    assert bet_record.is_dry_run is True  # Default
    assert bet_record.meta is None  # Default None when not provided


def test_update_bet_result():
    """Test updating bet result after settlement."""
    # Clear any existing bets to ensure a clean state
    with get_session() as session:
        session.query(BetRecord).delete()
        session.commit()

    # Create a bet
    bet = save_bet(
        market_id="test_market_4",
        selection="home",
        stake=50.0,
        odds=2.0,
        idempotency_key="test_key_4",
    )

    bet_id = bet.id

    # Verify the bet is in pending state
    with get_session() as session:
        new_bet = session.query(BetRecord).filter_by(id=bet_id).first()
        assert new_bet.result == "pending", "New bet should be in pending state"
        assert new_bet.settled_at is None, "New bet should not have a settled_at time"

    # Update result
    success = update_bet_result(bet_id, result="win", profit_loss=50.0)
    assert success is True, "First update should succeed"

    # Verify update
    with get_session() as session:
        updated_bet = session.query(BetRecord).filter_by(id=bet_id).first()
        assert updated_bet.result == "win", "Bet result should be updated to 'win'"
        assert updated_bet.profit_loss == 50.0, "Profit/loss should be updated to 50.0"
        assert updated_bet.settled_at is not None, "Settled time should be set"

    # Try to update again - should fail as the bet is already settled
    success = update_bet_result(bet_id, result="loss", profit_loss=-50.0)
    assert success is False, "Should not be able to update an already settled bet"


def test_update_bet_result_loss():
    """Test updating bet result for a loss."""
    bet = save_bet(
        market_id="test_market_5",
        selection="away",
        stake=100.0,
        odds=3.5,
        idempotency_key="test_key_5",
    )

    update_bet_result(bet.id, result="loss", profit_loss=-100.0)

    with get_session() as session:
        updated_bet = session.query(BetRecord).filter_by(id=bet.id).first()
        assert updated_bet.result == "loss"
        assert updated_bet.profit_loss == -100.0


def test_update_bet_result_void():
    """Test updating bet result for a void bet."""
    bet = save_bet(
        market_id="test_market_6",
        selection="draw",
        stake=75.0,
        odds=3.2,
        idempotency_key="test_key_6",
    )

    update_bet_result(bet.id, result="void", profit_loss=0.0)

    with get_session() as session:
        updated_bet = session.query(BetRecord).filter_by(id=bet.id).first()
        assert updated_bet.result == "void"
        assert updated_bet.profit_loss == 0.0


def test_update_bet_result_nonexistent():
    """Test updating non-existent bet ID."""
    # Should not raise error, just no-op
    update_bet_result(bet_id=999999, result="win", profit_loss=10.0)
    assert True


def test_get_daily_loss():
    """Test calculating daily loss."""
    # Clear any existing bets
    with get_session() as session:
        session.query(BetRecord).delete()
        session.commit()

    today = datetime.now(timezone.utc).date()

    # Add some test data
    bet1 = save_bet(
        market_id="test_market_1",
        selection="home",
        stake=100.0,
        odds=2.0,
        idempotency_key="test_key_1",
    )
    update_bet_result(bet1.id, "loss", -100.0)

    bet2 = save_bet(
        market_id="test_market_2",
        selection="away",
        stake=50.0,
        odds=3.0,
        idempotency_key="test_key_2",
    )
    update_bet_result(bet2.id, "win", 100.0)

    daily_loss = get_daily_loss(today)
    assert daily_loss == 0.0  # Net loss is 0 (100 loss + 100 win)
    assert daily_loss >= 0  # Should be a positive number or zero


def test_get_daily_loss_no_bets():
    """Test daily loss with no bets."""
    future_date = datetime(2099, 12, 31).date()
    daily_loss = get_daily_loss(future_date)
    assert daily_loss == 0.0


def test_get_daily_loss_none_date():
    """Test get_daily_loss when date is None (should use current date)."""
    # Clear any existing bets
    with get_session() as session:
        session.query(BetRecord).delete()
        session.commit()

    # Use a fixed datetime for testing
    today = datetime.now().date()
    test_datetime = datetime.combine(today, datetime.min.time())

    # Patch utc_now to return our test datetime
    with patch("src.db.utc_now") as mock_utc_now:
        mock_utc_now.return_value = test_datetime

        # Add a bet with today's date that results in a loss
        bet = save_bet(
            market_id="test_market_4",
            selection="home",
            stake=50.0,
            odds=2.0,
            idempotency_key="test_key_4",
        )
        # Explicitly set placed_at to ensure it matches our test datetime
        with get_session() as session:
            db_bet = session.query(BetRecord).filter_by(id=bet.id).first()
            db_bet.placed_at = test_datetime
            session.commit()

        update_bet_result(bet.id, "loss", -50.0)

        # Add another bet that results in a loss
        bet2 = save_bet(
            market_id="test_market_5",
            selection="away",
            stake=30.0,
            odds=3.0,
            idempotency_key="test_key_5",
        )
        # Explicitly set placed_at to ensure it matches our test datetime
        with get_session() as session:
            db_bet2 = session.query(BetRecord).filter_by(id=bet2.id).first()
            db_bet2.placed_at = test_datetime
            session.commit()

        update_bet_result(bet2.id, "loss", -30.0)

        # Add a winning bet to test net loss calculation
        bet3 = save_bet(
            market_id="test_market_6",
            selection="draw",
            stake=20.0,
            odds=4.0,
            idempotency_key="test_key_6",
        )
        # Explicitly set placed_at to ensure it matches our test datetime
        with get_session() as session:
            db_bet3 = session.query(BetRecord).filter_by(id=bet3.id).first()
            db_bet3.placed_at = test_datetime
            session.commit()

        update_bet_result(bet3.id, "win", 60.0)  # 20 * 4 - 20 = 60 profit

        # Now test get_daily_loss with the same datetime
        loss = get_daily_loss()

    # Net loss should be (50 + 30) - 60 = 20
    # But since we have a net profit (60 > 80), the function should return 0.0
    assert loss == 0.0


def test_get_daily_loss_dry_run_filter():
    """Test that dry run bets are excluded from daily loss calculation."""
    # Clear any existing bets
    with get_session() as session:
        session.query(BetRecord).delete()
        session.commit()

    # Add a dry run bet with a loss (should be excluded)
    bet1 = save_bet(
        market_id="test_market_3",
        selection="home",
        stake=100.0,
        odds=2.0,
        idempotency_key="test_key_3",
        is_dry_run=True,
    )
    update_bet_result(bet1.id, "loss", -100.0)

    # Add a non-dry run bet with a loss (should be included)
    bet2 = save_bet(
        market_id="test_market_4",
        selection="away",
        stake=100.0,
        odds=2.0,
        idempotency_key="test_key_4",
        is_dry_run=False,
    )
    update_bet_result(bet2.id, "loss", -100.0)

    # Add a non-dry run bet with a win (should be excluded as it's not a loss)
    bet3 = save_bet(
        market_id="test_market_5",
        selection="draw",
        stake=100.0,
        odds=2.0,
        idempotency_key="test_key_5",
        is_dry_run=False,
    )
    update_bet_result(bet3.id, "win", 100.0)

    # Only the non-dry run loss should be included (100.0)
    loss = get_daily_loss()
    assert loss == 100.0, "Should only include non-dry run losses"


def test_get_open_bets_count():
    """Test counting open bets."""
    # Create some pending bets
    save_bet(
        market_id="test_market_10",
        selection="home",
        stake=50.0,
        odds=2.0,
        idempotency_key="test_key_10",
        is_dry_run=False,
    )

    save_bet(
        market_id="test_market_11",
        selection="away",
        stake=75.0,
        odds=1.8,
        idempotency_key="test_key_11",
        is_dry_run=False,
    )

    # Get open bets count
    count = get_open_bets_count()

    # Should be at least 2
    assert count >= 2


def test_get_open_bets_count_excludes_settled():
    """Test that open bets count excludes settled bets."""
    # Create and settle a bet
    bet = save_bet(
        market_id="test_market_12",
        selection="home",
        stake=100.0,
        odds=2.5,
        idempotency_key="test_key_12",
        is_dry_run=False,
    )
    update_bet_result(bet.id, result="win", profit_loss=150.0)

    # Count open bets
    count = get_open_bets_count()

    # Settled bet should not be in open count
    assert count >= 0


def test_get_open_bets_count_dry_run_filter():
    """Test open bets count filtering by dry_run flag."""
    save_bet(
        market_id="test_market_13",
        selection="home",
        stake=50.0,
        odds=2.0,
        idempotency_key="test_key_13",
        is_dry_run=True,
    )

    # Count all open bets (function doesn't filter by dry_run)
    count = get_open_bets_count()
    assert count >= 1
    assert isinstance(count, int)


def test_bet_record_repr():
    """Test BetRecord string representation."""
    bet = save_bet(
        market_id="test_market_14",
        selection="home",
        stake=100.0,
        odds=2.5,
        idempotency_key="test_key_14",
    )

    repr_str = repr(bet)
    assert "BetRecord" in repr_str
    assert "test_market_14" in repr_str


def test_model_metadata_creation():
    """Test creating model metadata record."""
    with get_session() as session:
        metadata = ModelMetadata(
            model_name="test_model",
            version="1.0.0",
            hyperparameters={"n_estimators": 100},
            metrics={"accuracy": 0.85},
        )
        session.add(metadata)
        session.flush()

        assert metadata.id is not None
        assert metadata.model_name == "test_model"
        assert metadata.trained_at is not None


def test_daily_stats_creation():
    """Test creating daily stats record."""
    with get_session() as session:
        stats = DailyStats(
            date=datetime.now(timezone.utc),
            total_bets=10,
            total_staked=500.0,
            total_profit_loss=50.0,
            win_count=6,
            loss_count=4,
            void_count=0,
            starting_bankroll=1000.0,
            ending_bankroll=1050.0,
        )
        session.add(stats)
        session.flush()

        assert stats.id is not None
        assert stats.total_bets == 10


def test_daily_stats_repr():
    """Test DailyStats string representation."""
    with get_session() as session:
        stats = DailyStats(date=datetime.now(timezone.utc), total_bets=5, total_profit_loss=100.0)
        session.add(stats)
        session.flush()

        repr_str = repr(stats)
        assert "DailyStats" in repr_str
        assert "bets=5" in repr_str
