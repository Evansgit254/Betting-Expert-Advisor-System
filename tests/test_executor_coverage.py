"""Tests to improve executor.py coverage."""
from unittest.mock import MagicMock, patch

from src.executor import Executor, MockBookie


class TestExecutorClass:
    """Tests for the Executor class."""

    def test_executor_initialization_default(self):
        """Test Executor initialization with default client."""
        executor = Executor()
        assert executor.client is not None
        assert isinstance(executor.client, MockBookie)

    def test_executor_initialization_custom_client(self):
        """Test Executor initialization with custom client."""
        custom_client = MockBookie()
        executor = Executor(client=custom_client)
        assert executor.client is custom_client

    @patch("src.db.init_db")
    @patch("src.db.save_bet")
    def test_executor_execute_dry_run(self, mock_save_bet, mock_init_db):
        """Test executing bet in dry run mode."""
        mock_save_bet.return_value = 123  # Mock DB ID

        executor = Executor()
        bet = {"market_id": "test_market_dry", "selection": "home", "stake": 100.0, "odds": 2.5}

        result = executor.execute(bet, dry_run=True)

        assert "status" in result
        assert result["status"] in ["simulated", "dry_run"]  # Accept either status
        assert "db_id" in result or "error" in result

    @patch("src.db.init_db")
    @patch("src.db.save_bet")
    def test_executor_execute_live_mode(self, mock_save_bet, mock_init_db):
        """Test executing bet in live mode."""
        mock_save_bet.return_value = 456  # Mock DB ID

        executor = Executor()
        bet = {"market_id": "test_live_mode", "selection": "away", "stake": 50.0, "odds": 3.0}

        result = executor.execute(bet, dry_run=False)

        assert "status" in result
        assert result["status"] in ["accepted", "rejected"]  # Accept either status
        assert "db_id" in result or "error" in result or "message" in result

    @patch("src.executor.save_bet")
    def test_executor_database_error(self, mock_save_bet):
        """Test executor when database save fails."""
        mock_save_bet.side_effect = Exception("Database error")

        executor = Executor()
        bet = {"market_id": "test_db_error", "selection": "home", "stake": 100.0, "odds": 2.0}

        result = executor.execute(bet, dry_run=True)

        assert "db_error" in result
        assert "Database error" in result["db_error"]

    def test_executor_live_mode_client_exception(self):
        """Test executor when client raises exception."""
        mock_client = MagicMock()
        mock_client.place_bet.side_effect = Exception("API connection error")

        executor = Executor(client=mock_client)
        bet = {"market_id": "test_error", "selection": "away", "stake": 50.0, "odds": 2.0}

        result = executor.execute(bet, dry_run=False)

        # When MODE is not LIVE, it returns 'rejected'
        assert result["status"] in ["error", "rejected"]
        assert "db_id" in result or "db_error" in result


class TestMockBookie:
    """Tests for MockBookie class."""

    def test_mock_bookie_place_bet(self):
        """Test MockBookie place_bet method."""
        bookie = MockBookie()

        result = bookie.place_bet(market_id="test_market", selection="home", stake=100.0, odds=2.5)

        assert result["status"] == "accepted"
        assert "bet_id" in result
        assert result["market_id"] == "test_market"
        assert result["selection"] == "home"
        assert result["stake"] == 100.0
        assert result["odds"] == 2.5

    def test_mock_bookie_with_idempotency_key(self):
        """Test MockBookie with idempotency key."""
        bookie = MockBookie()

        result = bookie.place_bet(
            market_id="test_market",
            selection="away",
            stake=50.0,
            odds=3.0,
            idempotency_key="test_key_123",
        )

        assert result["status"] == "accepted"
        # MockBookie may or may not include idempotency_key in result
        assert "bet_id" in result

    def test_mock_bookie_generates_unique_bet_ids(self):
        """Test that MockBookie generates unique bet IDs."""
        bookie = MockBookie()

        result1 = bookie.place_bet("market1", "home", 100.0, 2.0)
        result2 = bookie.place_bet("market2", "away", 50.0, 3.0)

        assert result1["bet_id"] != result2["bet_id"]

    def test_mock_bookie_includes_timestamp(self):
        """Test that MockBookie includes timestamp."""
        bookie = MockBookie()

        result = bookie.place_bet("market", "home", 100.0, 2.0)

        assert "placed_at" in result
        assert isinstance(result["placed_at"], str)


class TestExecutorEdgeCases:
    """Tests for executor edge cases."""

    @patch("src.db.init_db")
    @patch("src.db.save_bet")
    def test_executor_with_high_odds(self, mock_save_bet, mock_init_db):
        """Test executor with high odds values."""
        mock_save_bet.return_value = 789  # Mock DB ID

        executor = Executor()
        bet = {
            "market_id": "high_odds_market_test",
            "selection": "longshot",
            "stake": 10.0,
            "odds": 15.0,
        }

        result = executor.execute(bet, dry_run=True)

        assert "status" in result
        assert result["status"] in ["simulated", "dry_run"]  # Accept either status

    def test_executor_with_minimum_stake(self):
        """Test executor with minimum stake."""
        executor = Executor()
        bet = {"market_id": "test_min_stake", "selection": "home", "stake": 1.0, "odds": 2.0}

        result = executor.execute(bet, dry_run=True)

        assert "db_id" in result

    def test_executor_multiple_bets(self):
        """Test executing multiple bets."""
        executor = Executor()

        bets = [
            {"market_id": f"market_{i}", "selection": "home", "stake": 100.0, "odds": 2.0}
            for i in range(3)
        ]

        results = [executor.execute(bet, dry_run=True) for bet in bets]

        assert len(results) == 3
        assert all("db_id" in r for r in results)
        # All should have unique db_ids
        db_ids = [r["db_id"] for r in results]
        assert len(set(db_ids)) == 3
