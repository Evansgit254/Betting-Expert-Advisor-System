"""Tests for database validation and error handling."""
import pytest

from src.db import get_daily_loss, get_open_bets_count, save_bet, update_bet_result


class TestSaveBetValidation:
    """Tests for save_bet input validation."""

    def test_save_bet_empty_market_id(self):
        """Test that empty market_id raises ValueError."""
        with pytest.raises(ValueError, match="market_id"):
            save_bet(market_id="", selection="home", stake=100.0, odds=2.0)

    def test_save_bet_whitespace_market_id(self):
        """Test that whitespace-only market_id raises ValueError."""
        with pytest.raises(ValueError, match="market_id"):
            save_bet(market_id="   ", selection="home", stake=100.0, odds=2.0)

    def test_save_bet_empty_selection(self):
        """Test that empty selection raises ValueError."""
        with pytest.raises(ValueError, match="selection"):
            save_bet(market_id="test_market", selection="", stake=100.0, odds=2.0)

    def test_save_bet_whitespace_selection(self):
        """Test that whitespace-only selection raises ValueError."""
        with pytest.raises(ValueError, match="selection"):
            save_bet(market_id="test_market", selection="   ", stake=100.0, odds=2.0)

    def test_save_bet_zero_stake(self):
        """Test that zero stake raises ValueError."""
        with pytest.raises(ValueError, match="stake must be a positive number"):
            save_bet(market_id="test_market", selection="home", stake=0.0, odds=2.0)

    def test_save_bet_negative_stake(self):
        """Test that negative stake raises ValueError."""
        with pytest.raises(ValueError, match="stake must be a positive number"):
            save_bet(market_id="test_market", selection="home", stake=-100.0, odds=2.0)

    def test_save_bet_string_stake(self):
        """Test that string stake raises ValueError."""
        with pytest.raises(ValueError, match="stake must be a positive number"):
            save_bet(market_id="test_market", selection="home", stake="100", odds=2.0)

    def test_save_bet_odds_below_one(self):
        """Test that odds below 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="odds must be"):
            save_bet(market_id="test_market", selection="home", stake=100.0, odds=0.5)

    def test_save_bet_odds_exactly_one(self):
        """Test that odds of exactly 1.0 is accepted."""
        bet = save_bet(
            market_id="test_odds_one",
            selection="home",
            stake=100.0,
            odds=1.0,
            idempotency_key="test_odds_one_key",
        )
        assert bet.odds == 1.0

    def test_save_bet_string_odds(self):
        """Test that string odds raises ValueError."""
        with pytest.raises(ValueError, match="odds must be a number"):
            save_bet(market_id="test_market", selection="home", stake=100.0, odds="2.0")

    def test_save_bet_non_string_idempotency_key(self):
        """Test that non-string idempotency_key raises ValueError."""
        with pytest.raises(ValueError, match="idempotency_key must be a string"):
            save_bet(
                market_id="test_market",
                selection="home",
                stake=100.0,
                odds=2.0,
                idempotency_key=12345,
            )

    def test_save_bet_none_idempotency_key(self):
        """Test that None idempotency_key is accepted."""
        bet = save_bet(
            market_id="test_none_key", selection="home", stake=100.0, odds=2.0, idempotency_key=None
        )
        assert bet.idempotency_key is None


class TestUpdateBetResultValidation:
    """Tests for update_bet_result validation."""

    def test_update_bet_result_with_valid_data(self):
        """Test updating bet with valid data."""
        bet = save_bet(
            market_id="test_valid_update",
            selection="home",
            stake=100.0,
            odds=2.0,
            idempotency_key="test_valid_update_key",
        )

        # Update with valid data
        result = update_bet_result(bet.id, "win", 100.0)
        assert result is True


class TestGetDailyLossValidation:
    """Tests for get_daily_loss validation."""

    def test_get_daily_loss_returns_float(self):
        """Test that get_daily_loss returns a float."""
        loss = get_daily_loss()
        assert isinstance(loss, float)
        assert loss >= 0.0


class TestGetOpenBetsCountValidation:
    """Tests for get_open_bets_count validation."""

    def test_get_open_bets_count_no_parameters(self):
        """Test get_open_bets_count with no parameters."""
        count = get_open_bets_count()
        assert isinstance(count, int)
        assert count >= 0

    def test_get_open_bets_count_returns_integer(self):
        """Test that get_open_bets_count always returns an integer."""
        count = get_open_bets_count()
        assert isinstance(count, int)
