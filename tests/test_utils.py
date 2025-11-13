"""Tests for utility functions."""
import pytest
import logging
import json
from unittest.mock import patch
from datetime import datetime, timezone
from src.utils import (
    setup_logging,
    get_logger,
    utc_now,
    validate_odds,
    validate_stake,
    log_structured,
    calculate_ev,
    format_currency,
)


def test_setup_logging():
    """Test logging configuration."""
    # Save original log level and handlers
    original_handlers = logging.root.handlers.copy()
    original_level = logging.root.level

    try:
        # Test with different log levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            # Reset logging
            logging.root.handlers = []

            # Setup logging with current level
            with patch("src.utils.settings.LOG_LEVEL", level):
                setup_logging()

                # Verify the root logger has the correct level
                assert logging.root.level == getattr(logging, level)

                # Verify we have at least one handler
                assert len(logging.root.handlers) > 0
    finally:
        # Restore original logging configuration
        logging.root.handlers = original_handlers
        logging.root.setLevel(original_level)


def test_get_logger():
    """Test logger creation with different names and properties."""
    # Test basic logger creation
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"

    # Test logger hierarchy
    child_logger = get_logger("test_module.submodule")
    assert child_logger.name == "test_module.submodule"

    # Test with different names
    test_names = [
        ("", "root"),  # Empty string becomes 'root'
        ("test", "test"),
        ("test.module", "test.module"),
        ("test.module.Class", "test.module.Class"),
    ]

    for name, expected_name in test_names:
        logger = get_logger(name)
        assert logger.name == expected_name
        # Root logger may have been configured by other tests
        # Just verify non-root loggers have NOTSET or inherit from root
        if name != "":
            assert logger.level in [logging.NOTSET, logging.root.level]


def test_utc_now():
    """Test UTC datetime generation with different scenarios."""
    # Test basic properties
    now = utc_now()
    assert isinstance(now, datetime)
    assert now.tzinfo == timezone.utc

    # Test that it's close to actual time
    diff = (datetime.now(timezone.utc) - now).total_seconds()
    assert abs(diff) < 1  # Within 1 second

    # Test that it's not the same object each time
    now2 = utc_now()
    assert now != now2  # Should be different objects
    assert now2 > now  # Should be later


def test_validate_odds():
    """Test odds validation with edge cases."""
    # Valid odds
    assert validate_odds(1.5) is True
    assert validate_odds(2.0) is True
    assert validate_odds(10.0) is True
    assert validate_odds(100.0) is True

    # Boundary cases
    assert validate_odds(1.01) is True
    assert validate_odds(1000.0) is True

    # Test just outside boundaries
    assert validate_odds(1.009) is False  # Just below min
    assert validate_odds(1000.1) is False  # Just above max

    # Invalid odds
    assert validate_odds(0.5) is False
    assert validate_odds(1.0) is False
    assert validate_odds(1001.0) is False
    assert validate_odds(-5.0) is False

    # Test non-numeric inputs
    with pytest.raises(TypeError):
        validate_odds("2.0")  # type: ignore

    with pytest.raises(TypeError):
        validate_odds(None)  # type: ignore


@patch("src.utils.settings")
def test_validate_stake(mock_settings):
    """Test stake validation with different settings."""
    # Set up mock settings
    mock_settings.MAX_STAKE_FRAC = 0.05  # 5%
    bankroll = 1000.0

    # Test valid stakes
    assert validate_stake(10.0, bankroll) is True
    assert validate_stake(50.0, bankroll) is True  # Exactly 5%

    # Test invalid stakes
    assert validate_stake(0.0, bankroll) is False
    assert validate_stake(-10.0, bankroll) is False
    assert validate_stake(100.0, bankroll) is False  # Over 5%

    # Test edge cases
    assert validate_stake(0.01, bankroll) is True  # Minimum valid stake
    assert validate_stake(50.01, bankroll) is False  # Just over 5%

    # Test with different MAX_STAKE_FRAC
    mock_settings.MAX_STAKE_FRAC = 0.1  # 10%
    assert validate_stake(100.0, bankroll) is True  # Now valid with 10% limit


def test_log_structured(caplog):
    """Test structured logging with various scenarios."""
    logger = get_logger("test_structured")

    # Test with different log levels
    test_levels = ["debug", "info", "warning", "error", "critical"]
    for level in test_levels:
        with caplog.at_level(logging.DEBUG):  # Set to DEBUG to capture all levels
            log_structured(
                logger,
                level,
                f"Test {level} message",
                user="test_user",
                value=42,
                nested={"key": "value"},
                list_data=[1, 2, 3],
            )

    # Test with non-string message (should be converted to string)
    with caplog.at_level(logging.INFO):
        log_structured(logger, "info", 12345, numeric_value=12345)

    # Test with None message
    with caplog.at_level(logging.INFO):
        log_structured(logger, "info", None, none_value=None)

    # Test with complex objects that need JSON serialization
    with caplog.at_level(logging.INFO):
        log_structured(
            logger,
            "info",
            "complex object",
            complex_data={"nested": {"key": "value"}, "list": [1, 2, 3]},
        )

    # Verify the number of log records matches our expectations
    # We have 5 test levels + 3 additional test cases (non-string, None, complex)
    assert len(caplog.records) == len(test_levels) + 3

    # Verify JSON structure and content for each log record
    for record in caplog.records:
        log_data = json.loads(record.message)
        assert "timestamp" in log_data
        assert "message" in log_data

        # Get message as string for comparison
        message = str(log_data["message"])

        # Verify the log level was set correctly
        if "Test debug message" in message:
            assert record.levelno == logging.DEBUG
        elif "Test info message" in message:
            assert record.levelno == logging.INFO
        # ... and so on for other levels

    # Verify the non-string message was converted to string
    assert any(str(json.loads(rec.message).get("message")) == "12345" for rec in caplog.records)

    # Verify the None message was handled
    assert any(
        "message" in json.loads(rec.message) and json.loads(rec.message)["message"] is None
        for rec in caplog.records
    )

    # Test with invalid log level
    with caplog.at_level(logging.ERROR):
        with pytest.raises(AttributeError):
            log_structured(logger, "invalid_level", "This should fail")


def test_calculate_ev():
    """Test expected value calculation."""
    # Profitable bet (positive EV)
    ev = calculate_ev(win_prob=0.6, odds=2.0)
    assert ev > 0
    assert pytest.approx(ev, rel=0.01) == 0.2  # 0.6 * 1.0 - 0.4 = 0.2

    # Breakeven bet (zero EV)
    ev = calculate_ev(win_prob=0.5, odds=2.0)
    assert pytest.approx(ev, abs=0.01) == 0.0

    # Losing bet (negative EV)
    ev = calculate_ev(win_prob=0.3, odds=2.0)
    assert ev < 0
    assert pytest.approx(ev, rel=0.01) == -0.4  # 0.3 * 1.0 - 0.7 = -0.4

    # Edge cases
    ev = calculate_ev(win_prob=0.1, odds=5.0)  # High odds, low probability
    assert pytest.approx(ev, rel=0.01) == -0.5  # 0.1 * 4.0 - 0.9 = -0.5

    # Boundary probabilities
    assert calculate_ev(win_prob=0.0, odds=2.0) == -1.0  # Certain loss
    assert calculate_ev(win_prob=1.0, odds=2.0) == 1.0  # Certain win

    # Very high odds - using pytest.approx for floating point comparison
    assert calculate_ev(win_prob=0.01, odds=1000.0) == pytest.approx(
        9.0
    )  # (0.01 * 999) - 0.99 = 9.0


def test_format_currency():
    """Test currency formatting with various inputs and edge cases."""
    # Test different amounts and currencies
    assert format_currency(100.0) == "USD 100.00"
    assert format_currency(100.0, "EUR") == "EUR 100.00"

    # Test with different decimal places
    assert format_currency(100.0, "JPY") == "JPY 100.00"  # Even JPY should show 2 decimal places
    assert format_currency(100.0, "BTC") == "BTC 100.00"  # Cryptocurrency

    # Test with very large numbers
    assert format_currency(1000000.0) == "USD 1000000.00"

    # Test with very small numbers
    assert format_currency(0.001, "BTC") == "BTC 0.00"  # Rounds down
    assert format_currency(0.005, "BTC") == "BTC 0.01"  # Rounds up

    # Test with negative numbers
    assert format_currency(-100.0) == "USD -100.00"
    assert format_currency(-0.01) == "USD -0.01"

    # Test with zero
    assert format_currency(0.0) == "USD 0.00"

    # Test with custom currency symbols and codes
    assert format_currency(100.0, "¥") == "¥ 100.00"
    assert format_currency(100.0, "₿") == "₿ 100.00"

    # Test with different decimal separators (shouldn't be affected by locale)
    # This assumes the system locale doesn't change during test execution
    assert "." in format_currency(100.5)  # Should use dot as decimal separator

    # Test with very long currency codes
    assert format_currency(100.0, "LONGCODE") == "LONGCODE 100.00"
    assert format_currency(1234.56) == "USD 1234.56"
    assert format_currency(0.99) == "USD 0.99"
    assert format_currency(-50.0) == "USD -50.00"

    # Test edge cases
    assert format_currency(0.0) == "USD 0.00"
    assert format_currency(1e9) == "USD 1000000000.00"  # Large number
    assert format_currency(1.23456789) == "USD 1.23"  # Rounding
    assert format_currency(1.235) == "USD 1.24"  # Rounding up
