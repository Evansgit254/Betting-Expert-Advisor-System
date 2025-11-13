"""Tests for data validation utilities."""
from datetime import datetime

import pytest

from src.validators import (
    ValidationError,
    sanitize_string,
    validate_api_key,
    validate_bet_data,
    validate_date_range,
    validate_email,
    validate_market_id,
    validate_odds,
    validate_probability,
    validate_selection,
    validate_stake,
)


class TestValidateOdds:
    """Tests for odds validation."""

    def test_valid_odds(self):
        """Test validation of valid odds."""
        validate_odds(1.5)
        validate_odds(2.0)
        validate_odds(10.5)
        validate_odds(100.0)

    def test_odds_below_minimum(self):
        """Test that odds below minimum raise error."""
        with pytest.raises(ValidationError, match="below minimum"):
            validate_odds(0.5)

    def test_odds_above_maximum(self):
        """Test that odds above maximum raise error."""
        with pytest.raises(ValidationError, match="exceed maximum"):
            validate_odds(1001.0)

    def test_odds_not_number(self):
        """Test that non-numeric odds raise error."""
        with pytest.raises(ValidationError, match="must be a number"):
            validate_odds("2.0")

    def test_odds_custom_range(self):
        """Test validation with custom min/max."""
        validate_odds(1.5, min_odds=1.5, max_odds=5.0)

        with pytest.raises(ValidationError):
            validate_odds(1.4, min_odds=1.5)


class TestValidateStake:
    """Tests for stake validation."""

    def test_valid_stake(self):
        """Test validation of valid stake."""
        validate_stake(100.0, bankroll=1000.0)
        validate_stake(50.0, bankroll=1000.0)

    def test_stake_below_minimum(self):
        """Test that stake below minimum raises error."""
        with pytest.raises(ValidationError, match="below minimum"):
            validate_stake(0.5, bankroll=1000.0, min_stake=1.0)

    def test_stake_exceeds_max_fraction(self):
        """Test that stake exceeding max fraction raises error."""
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_stake(200.0, bankroll=1000.0, max_stake_fraction=0.1)

    def test_stake_exceeds_bankroll(self):
        """Test that stake exceeding bankroll raises error."""
        with pytest.raises(ValidationError, match="exceeds"):
            validate_stake(1500.0, bankroll=1000.0, max_stake_fraction=1.0)

    def test_stake_not_number(self):
        """Test that non-numeric stake raises error."""
        with pytest.raises(ValidationError, match="must be a number"):
            validate_stake("100", bankroll=1000.0)


class TestValidateProbability:
    """Tests for probability validation."""

    def test_valid_probability(self):
        """Test validation of valid probabilities."""
        validate_probability(0.0)
        validate_probability(0.5)
        validate_probability(1.0)

    def test_probability_below_zero(self):
        """Test that probability below 0 raises error."""
        with pytest.raises(ValidationError, match="must be between 0 and 1"):
            validate_probability(-0.1)

    def test_probability_above_one(self):
        """Test that probability above 1 raises error."""
        with pytest.raises(ValidationError, match="must be between 0 and 1"):
            validate_probability(1.1)

    def test_probability_not_number(self):
        """Test that non-numeric probability raises error."""
        with pytest.raises(ValidationError, match="must be a number"):
            validate_probability("0.5")


class TestValidateMarketId:
    """Tests for market ID validation."""

    def test_valid_market_id(self):
        """Test validation of valid market IDs."""
        validate_market_id("1.23456789")
        validate_market_id("market_123")
        validate_market_id("abc-def-ghi")

    def test_empty_market_id(self):
        """Test that empty market ID raises error."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_market_id("")

        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_market_id("   ")

    def test_market_id_not_string(self):
        """Test that non-string market ID raises error."""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_market_id(123)

    def test_market_id_too_long(self):
        """Test that overly long market ID raises error."""
        with pytest.raises(ValidationError, match="too long"):
            validate_market_id("a" * 101)


class TestValidateSelection:
    """Tests for selection validation."""

    def test_valid_selection(self):
        """Test validation of valid selections."""
        validate_selection("home")
        validate_selection("away")
        validate_selection("draw")

    def test_empty_selection(self):
        """Test that empty selection raises error."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_selection("")

    def test_selection_not_string(self):
        """Test that non-string selection raises error."""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_selection(123)

    def test_selection_with_valid_list(self):
        """Test validation with list of valid selections."""
        validate_selection("home", valid_selections=["home", "away", "draw"])

        with pytest.raises(ValidationError, match="Invalid selection"):
            validate_selection("invalid", valid_selections=["home", "away", "draw"])


class TestValidateBetData:
    """Tests for complete bet data validation."""

    def test_valid_bet_data(self):
        """Test validation of valid bet data."""
        bet_data = {
            "market_id": "1.23456",
            "selection": "home",
            "stake": 100.0,
            "odds": 2.5,
            "bankroll": 1000.0,
        }
        validate_bet_data(bet_data)

    def test_missing_required_field(self):
        """Test that missing required field raises error."""
        bet_data = {
            "market_id": "1.23456",
            "selection": "home",
            "stake": 100.0
            # Missing 'odds'
        }
        with pytest.raises(ValidationError, match="Missing required field"):
            validate_bet_data(bet_data)

    def test_invalid_odds_in_bet_data(self):
        """Test that invalid odds in bet data raises error."""
        bet_data = {
            "market_id": "1.23456",
            "selection": "home",
            "stake": 100.0,
            "odds": 0.5,  # Invalid
        }
        with pytest.raises(ValidationError):
            validate_bet_data(bet_data)

    def test_invalid_stake_in_bet_data(self):
        """Test that invalid stake in bet data raises error."""
        bet_data = {
            "market_id": "1.23456",
            "selection": "home",
            "stake": -10.0,  # Invalid
            "odds": 2.5,
        }
        with pytest.raises(ValidationError):
            validate_bet_data(bet_data)


class TestValidateDateRange:
    """Tests for date range validation."""

    def test_valid_date_range(self):
        """Test validation of valid date range."""
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 31)
        validate_date_range(start, end)

    def test_start_after_end(self):
        """Test that start date after end date raises error."""
        start = datetime(2025, 1, 31)
        end = datetime(2025, 1, 1)
        with pytest.raises(ValidationError, match="is after end date"):
            validate_date_range(start, end)

    def test_date_range_exceeds_max_days(self):
        """Test that date range exceeding max days raises error."""
        start = datetime(2025, 1, 1)
        end = datetime(2025, 12, 31)
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_date_range(start, end, max_days=30)

    def test_invalid_start_date_type(self):
        """Test that invalid start date type raises error."""
        with pytest.raises(ValidationError, match="must be datetime"):
            validate_date_range("2025-01-01", datetime(2025, 1, 31))

    def test_invalid_end_date_type(self):
        """Test that invalid end date type raises error."""
        with pytest.raises(ValidationError, match="must be datetime"):
            validate_date_range(datetime(2025, 1, 1), "2025-01-31")


class TestValidateEmail:
    """Tests for email validation."""

    def test_valid_email(self):
        """Test validation of valid emails."""
        validate_email("user@example.com")
        validate_email("test.user@domain.co.uk")
        validate_email("name+tag@example.org")

    def test_invalid_email_format(self):
        """Test that invalid email format raises error."""
        with pytest.raises(ValidationError, match="Invalid email format"):
            validate_email("invalid.email")

        with pytest.raises(ValidationError, match="Invalid email format"):
            validate_email("@example.com")

        with pytest.raises(ValidationError, match="Invalid email format"):
            validate_email("user@")

    def test_email_not_string(self):
        """Test that non-string email raises error."""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_email(123)


class TestValidateApiKey:
    """Tests for API key validation."""

    def test_valid_api_key(self):
        """Test validation of valid API keys."""
        validate_api_key("abcdef1234567890")
        validate_api_key("a" * 20)

    def test_empty_api_key(self):
        """Test that empty API key raises error."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_api_key("")

    def test_api_key_too_short(self):
        """Test that short API key raises error."""
        with pytest.raises(ValidationError, match="too short"):
            validate_api_key("abc", min_length=10)

    def test_api_key_not_string(self):
        """Test that non-string API key raises error."""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_api_key(123456)


class TestSanitizeString:
    """Tests for string sanitization."""

    def test_sanitize_normal_string(self):
        """Test sanitization of normal string."""
        result = sanitize_string("Hello World")
        assert result == "Hello World"

    def test_sanitize_with_null_bytes(self):
        """Test removal of null bytes."""
        result = sanitize_string("Hello\x00World")
        assert result == "HelloWorld"

    def test_sanitize_with_control_characters(self):
        """Test removal of control characters."""
        result = sanitize_string("Hello\x01\x02World")
        assert result == "HelloWorld"

    def test_sanitize_preserves_newlines(self):
        """Test that newlines are preserved."""
        result = sanitize_string("Hello\nWorld")
        assert result == "Hello\nWorld"

    def test_sanitize_trims_whitespace(self):
        """Test that leading/trailing whitespace is trimmed."""
        result = sanitize_string("  Hello World  ")
        assert result == "Hello World"

    def test_sanitize_truncates_long_string(self):
        """Test that long strings are truncated."""
        long_string = "a" * 300
        result = sanitize_string(long_string, max_length=255)
        assert len(result) == 255

    def test_sanitize_non_string(self):
        """Test sanitization of non-string input."""
        result = sanitize_string(123)
        assert result == "123"
