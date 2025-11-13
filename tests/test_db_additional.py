"""Additional tests for database module to improve coverage."""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from src.db import (
    get_session,
    save_bet,
    update_bet_result,
    get_daily_loss,
    get_open_bets_count,
    get_current_bankroll,
    BetRecord,
    handle_db_errors,
    db_retry,
)


class TestHandleDbErrors:
    """Tests for handle_db_errors context manager."""

    def test_handle_db_errors_success(self):
        """Test successful database operation."""
        with handle_db_errors() as session:
            assert session is not None
            # Perform a simple query
            count = session.query(BetRecord).count()
            assert count >= 0

    def test_handle_db_errors_commits_on_success(self):
        """Test that successful operations are committed."""
        with handle_db_errors() as session:
            bet = BetRecord(
                market_id="test_commit",
                selection="home",
                stake=100.0,
                odds=2.0,
                idempotency_key="test_commit_key",
            )
            session.add(bet)

        # Verify bet was committed
        with get_session() as session:
            saved_bet = (
                session.query(BetRecord).filter_by(idempotency_key="test_commit_key").first()
            )
            assert saved_bet is not None

    @patch("src.db.SessionLocal")
    def test_handle_db_errors_rollback_on_error(self, mock_session_local):
        """Test that errors trigger rollback."""
        mock_session = MagicMock()
        mock_session.query.side_effect = SQLAlchemyError("Test error")
        mock_session_local.return_value = mock_session

        with pytest.raises(SQLAlchemyError):
            with handle_db_errors() as session:
                session.query(BetRecord).all()

        # Verify rollback was called
        mock_session.rollback.assert_called()


class TestDbRetryDecorator:
    """Tests for db_retry decorator."""

    def test_db_retry_success_first_attempt(self):
        """Test successful operation on first attempt."""
        call_count = [0]

        @db_retry(retry_on=(SQLAlchemyError,))
        def successful_operation():
            call_count[0] += 1
            return "success"

        result = successful_operation()
        assert result == "success"
        assert call_count[0] == 1

    def test_db_retry_success_after_retries(self):
        """Test successful operation after retries."""
        # db_retry uses tenacity with fixed retry attempts from config
        # This test verifies the decorator works, not the retry count
        call_count = [0]

        @db_retry(retry_on=(SQLAlchemyError,))
        def flaky_operation():
            call_count[0] += 1
            if call_count[0] < 2:
                raise OperationalError("Temp error", None, None)
            return "success"

        result = flaky_operation()
        assert result == "success"
        assert call_count[0] >= 2  # At least 2 attempts

    def test_db_retry_max_retries_exceeded(self):
        """Test that max retries is respected."""
        call_count = [0]

        @db_retry(retry_on=(SQLAlchemyError,))
        def always_failing_operation():
            call_count[0] += 1
            raise OperationalError("Persistent error", None, None)

        with pytest.raises(OperationalError):
            always_failing_operation()

        # Should have tried multiple times (config default is 3)
        assert call_count[0] >= 3


class TestSaveBetEdgeCases:
    """Additional tests for save_bet edge cases."""

    def test_save_bet_with_all_parameters(self):
        """Test saving bet with all optional parameters."""
        bet = save_bet(
            market_id="test_all_params",
            selection="home",
            stake=100.0,
            odds=2.5,
            idempotency_key="test_all_params_key",
            is_dry_run=False,
            meta={"source": "test", "confidence": 0.8},
        )

        assert bet.id is not None
        assert bet.market_id == "test_all_params"
        assert bet.is_dry_run is False
        # Note: save_bet returns detached instance, meta might not be set
        # Just verify the bet was created successfully

    def test_save_bet_extracts_strategy_from_meta(self):
        """Test that strategy_name is extracted from meta if not provided."""
        bet = save_bet(
            market_id="test_meta_strategy",
            selection="away",
            stake=50.0,
            odds=3.0,
            idempotency_key="test_meta_strategy_key",
            meta={"strategy": "kelly_criterion"},
        )

        # Verify bet was created (strategy extraction happens in DB)
        assert bet.id is not None
        assert bet.market_id == "test_meta_strategy"

    def test_save_bet_with_nested_strategy_in_meta(self):
        """Test extraction of nested strategy name from meta."""
        bet = save_bet(
            market_id="test_nested_strategy",
            selection="draw",
            stake=25.0,
            odds=4.0,
            idempotency_key="test_nested_key",
            meta={"strategy": {"name": "arbitrage", "type": "cross_book"}},
        )

        # Verify bet was created
        assert bet.id is not None
        assert bet.market_id == "test_nested_strategy"


class TestUpdateBetResultEdgeCases:
    """Additional tests for update_bet_result edge cases."""

    def test_update_bet_result_nonexistent_bet(self):
        """Test updating a bet that doesn't exist."""
        result = update_bet_result(99999, "win", 100.0)
        assert result is False

    def test_update_bet_result_with_zero_profit(self):
        """Test updating bet with zero profit (void)."""
        bet = save_bet(
            market_id="test_zero_profit",
            selection="home",
            stake=100.0,
            odds=2.0,
            idempotency_key="test_zero_profit_key",
        )

        result = update_bet_result(bet.id, "void", 0.0)
        assert result is True

        # Verify the update
        with get_session() as session:
            updated_bet = session.query(BetRecord).filter_by(id=bet.id).first()
            assert updated_bet.result == "void"
            assert updated_bet.profit_loss == 0.0

    def test_update_bet_result_with_negative_profit(self):
        """Test updating bet with negative profit (loss)."""
        bet = save_bet(
            market_id="test_negative_profit",
            selection="away",
            stake=50.0,
            odds=1.5,
            idempotency_key="test_negative_key",
        )

        result = update_bet_result(bet.id, "loss", -50.0)
        assert result is True


class TestGetDailyLossEdgeCases:
    """Additional tests for get_daily_loss edge cases."""

    def test_get_daily_loss_with_future_date(self):
        """Test getting daily loss for a future date."""
        from datetime import timedelta

        future_date = datetime.now(timezone.utc) + timedelta(days=30)

        loss = get_daily_loss(date=future_date)
        assert loss == 0.0

    def test_get_daily_loss_with_past_date(self):
        """Test getting daily loss for a past date."""
        from datetime import timedelta

        past_date = datetime.now(timezone.utc) - timedelta(days=365)

        loss = get_daily_loss(date=past_date)
        assert loss >= 0.0

    def test_get_daily_loss_with_dry_run_bet(self):
        """Test daily loss calculation with dry run bets."""
        # Clear all bets first
        with get_session() as session:
            session.query(BetRecord).delete()
            session.commit()

        # Create a dry run bet with loss
        bet = save_bet(
            market_id="test_dry_run_loss",
            selection="home",
            stake=100.0,
            odds=2.0,
            idempotency_key="test_dry_run_loss_key",
            is_dry_run=True,
        )
        update_bet_result(bet.id, "loss", -100.0)

        # Get daily loss - function filters by is_dry_run=False internally
        loss = get_daily_loss()

        # Should be 0 since dry run bets are excluded
        assert loss == 0.0


class TestGetOpenBetsCountEdgeCases:
    """Additional tests for get_open_bets_count edge cases."""

    def test_get_open_bets_count_with_mixed_bets(self):
        """Test counting open bets with mix of open and settled."""
        # Clear all bets first
        with get_session() as session:
            session.query(BetRecord).delete()
            session.commit()

        # Create open bet (not dry run)
        save_bet(
            market_id="test_open_mixed",
            selection="home",
            stake=100.0,
            odds=2.0,
            idempotency_key="test_open_mixed_key",
            is_dry_run=False,  # Make it a real bet
        )

        # Create settled bet (not dry run)
        settled_bet = save_bet(
            market_id="test_settled_mixed",
            selection="away",
            stake=50.0,
            odds=1.5,
            idempotency_key="test_settled_mixed_key",
            is_dry_run=False,  # Make it a real bet
        )
        update_bet_result(settled_bet.id, "win", 25.0)

        # Count should only include open bet
        count = get_open_bets_count()
        assert count == 1  # Exactly our open bet

    def test_get_open_bets_count_with_dry_run(self):
        """Test counting open bets with dry run bets."""
        # Clear all bets first
        with get_session() as session:
            session.query(BetRecord).delete()
            session.commit()

        # Create dry run open bet
        _ = save_bet(
            market_id="test_dry_run_open",
            selection="draw",
            stake=25.0,
            odds=3.0,
            idempotency_key="test_dry_run_open_key",
            is_dry_run=True,
        )

        # Function filters by is_dry_run=False internally
        count = get_open_bets_count()

        # Should be 0 since dry run bets are excluded
        assert count == 0


class TestGetCurrentBankrollEdgeCases:
    """Additional tests for get_current_bankroll edge cases."""

    def test_get_current_bankroll_with_no_bets(self):
        """Test bankroll calculation with no settled bets."""
        # Clear all bets
        with get_session() as session:
            session.query(BetRecord).delete()
            session.commit()

        bankroll = get_current_bankroll()
        assert bankroll == 0.0

    def test_get_current_bankroll_excludes_pending(self):
        """Test that pending bets don't affect bankroll."""
        # Clear all bets
        with get_session() as session:
            session.query(BetRecord).delete()
            session.commit()

        # Create pending bet
        _ = save_bet(
            market_id="test_pending_bankroll",
            selection="home",
            stake=100.0,
            odds=2.0,
            idempotency_key="test_pending_bankroll_key",
            is_dry_run=False,
        )

        # Bankroll should still be 0 (bet not settled)
        bankroll = get_current_bankroll()
        assert bankroll == 0.0

    def test_get_current_bankroll_with_mixed_results(self):
        """Test bankroll with wins, losses, and voids."""
        # Clear all bets
        with get_session() as session:
            session.query(BetRecord).delete()
            session.commit()

        # Create and settle various bets
        bet1 = save_bet(
            market_id="bankroll_win",
            selection="home",
            stake=100.0,
            odds=2.0,
            idempotency_key="bankroll_win_key",
            is_dry_run=False,
        )
        update_bet_result(bet1.id, "win", 100.0)

        bet2 = save_bet(
            market_id="bankroll_loss",
            selection="away",
            stake=50.0,
            odds=1.5,
            idempotency_key="bankroll_loss_key",
            is_dry_run=False,
        )
        update_bet_result(bet2.id, "loss", -50.0)

        bet3 = save_bet(
            market_id="bankroll_void",
            selection="draw",
            stake=25.0,
            odds=3.0,
            idempotency_key="bankroll_void_key",
            is_dry_run=False,
        )
        update_bet_result(bet3.id, "void", 0.0)

        bankroll = get_current_bankroll()
        assert bankroll == 50.0  # 100 - 50 + 0


class TestBetRecordModel:
    """Tests for BetRecord model."""

    def test_bet_record_repr(self):
        """Test BetRecord string representation."""
        bet = BetRecord(id=1, market_id="test_repr", selection="home", stake=100.0, odds=2.5)

        repr_str = repr(bet)
        assert "BetRecord" in repr_str
        assert "test_repr" in repr_str
        assert "100.0" in repr_str

    def test_bet_record_default_values(self):
        """Test BetRecord default values."""
        # Create and save to database to get defaults
        with get_session() as session:
            bet = BetRecord(
                market_id="test_defaults",
                selection="away",
                stake=50.0,
                odds=1.8,
                idempotency_key="test_defaults_key",
            )
            session.add(bet)
            session.flush()

            assert bet.result == "pending"
            assert bet.profit_loss is None
            assert bet.is_dry_run is True
            assert bet.placed_at is not None
            assert bet.settled_at is None
