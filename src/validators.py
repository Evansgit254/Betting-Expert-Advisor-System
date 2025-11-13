"""Data validation utilities for the betting system.

This module provides validation functions for bet data, odds, stakes,
and other critical inputs to ensure data integrity.
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


class ValidationError(Exception):
    """Custom exception for validation errors."""


def validate_odds(odds: float, min_odds: float = 1.01, max_odds: float = 1000.0) -> None:
    """Validate betting odds.

    Args:
        odds: Decimal odds to validate
        min_odds: Minimum acceptable odds
        max_odds: Maximum acceptable odds

    Raises:
        ValidationError: If odds are invalid
    """
    if not isinstance(odds, (int, float)):
        raise ValidationError(f"Odds must be a number, got {type(odds).__name__}")

    if odds < min_odds:
        raise ValidationError(f"Odds {odds} below minimum {min_odds}")

    if odds > max_odds:
        raise ValidationError(f"Odds {odds} exceed maximum {max_odds}")


def validate_stake(
    stake: float, bankroll: float, min_stake: float = 1.0, max_stake_fraction: float = 0.1
) -> None:
    """Validate bet stake amount.

    Args:
        stake: Stake amount to validate
        bankroll: Current bankroll
        min_stake: Minimum stake amount
        max_stake_fraction: Maximum stake as fraction of bankroll

    Raises:
        ValidationError: If stake is invalid
    """
    if not isinstance(stake, (int, float)):
        raise ValidationError(f"Stake must be a number, got {type(stake).__name__}")

    if stake < min_stake:
        raise ValidationError(f"Stake {stake} below minimum {min_stake}")

    max_stake = bankroll * max_stake_fraction
    if stake > max_stake:
        raise ValidationError(
            f"Stake {stake} exceeds maximum {max_stake:.2f} "
            f"({max_stake_fraction*100}% of bankroll)"
        )

    if stake > bankroll:
        raise ValidationError(f"Stake {stake} exceeds bankroll {bankroll}")


def validate_probability(probability: float) -> None:
    """Validate probability value.

    Args:
        probability: Probability to validate (0-1)

    Raises:
        ValidationError: If probability is invalid
    """
    if not isinstance(probability, (int, float)):
        raise ValidationError(f"Probability must be a number, got {type(probability).__name__}")

    if not 0 <= probability <= 1:
        raise ValidationError(f"Probability {probability} must be between 0 and 1")


def validate_market_id(market_id: str) -> None:
    """Validate market ID format.

    Args:
        market_id: Market ID to validate

    Raises:
        ValidationError: If market ID is invalid
    """
    if not isinstance(market_id, str):
        raise ValidationError(f"Market ID must be a string, got {type(market_id).__name__}")

    if not market_id or not market_id.strip():
        raise ValidationError("Market ID cannot be empty")

    # Check for reasonable length
    if len(market_id) > 100:
        raise ValidationError(f"Market ID too long: {len(market_id)} characters")


def validate_selection(selection: str, valid_selections: Optional[List[str]] = None) -> None:
    """Validate bet selection.

    Args:
        selection: Selection to validate (e.g., 'home', 'away', 'draw')
        valid_selections: Optional list of valid selections

    Raises:
        ValidationError: If selection is invalid
    """
    if not isinstance(selection, str):
        raise ValidationError(f"Selection must be a string, got {type(selection).__name__}")

    if not selection or not selection.strip():
        raise ValidationError("Selection cannot be empty")

    if valid_selections and selection not in valid_selections:
        raise ValidationError(
            f"Invalid selection '{selection}'. Must be one of: {', '.join(valid_selections)}"
        )


def validate_bet_data(bet_data: Dict[str, Any]) -> None:
    """Validate complete bet data dictionary.

    Args:
        bet_data: Dictionary containing bet information

    Raises:
        ValidationError: If any bet data is invalid
    """
    required_fields = ["market_id", "selection", "stake", "odds"]

    # Check required fields
    for field in required_fields:
        if field not in bet_data:
            raise ValidationError(f"Missing required field: {field}")

    # Validate each field
    validate_market_id(bet_data["market_id"])
    validate_selection(bet_data["selection"])
    validate_odds(bet_data["odds"])

    # Validate stake if bankroll is provided
    if "bankroll" in bet_data:
        validate_stake(bet_data["stake"], bet_data["bankroll"])
    elif bet_data["stake"] <= 0:
        raise ValidationError(f"Stake must be positive, got {bet_data['stake']}")


def validate_date_range(
    start_date: datetime, end_date: datetime, max_days: Optional[int] = None
) -> None:
    """Validate date range.

    Args:
        start_date: Start date
        end_date: End date
        max_days: Maximum allowed days in range

    Raises:
        ValidationError: If date range is invalid
    """
    if not isinstance(start_date, datetime):
        raise ValidationError(f"Start date must be datetime, got {type(start_date).__name__}")

    if not isinstance(end_date, datetime):
        raise ValidationError(f"End date must be datetime, got {type(end_date).__name__}")

    if start_date > end_date:
        raise ValidationError(f"Start date {start_date} is after end date {end_date}")

    if max_days:
        delta = (end_date - start_date).days
        if delta > max_days:
            raise ValidationError(f"Date range {delta} days exceeds maximum {max_days} days")


def validate_email(email: str) -> None:
    """Validate email address format.

    Args:
        email: Email address to validate

    Raises:
        ValidationError: If email format is invalid
    """
    if not isinstance(email, str):
        raise ValidationError(f"Email must be a string, got {type(email).__name__}")

    # Simple email regex
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email format: {email}")


def validate_api_key(api_key: str, min_length: int = 10) -> None:
    """Validate API key format.

    Args:
        api_key: API key to validate
        min_length: Minimum length for API key

    Raises:
        ValidationError: If API key is invalid
    """
    if not isinstance(api_key, str):
        raise ValidationError(f"API key must be a string, got {type(api_key).__name__}")

    if not api_key or not api_key.strip():
        raise ValidationError("API key cannot be empty")

    if len(api_key) < min_length:
        raise ValidationError(
            f"API key too short: {len(api_key)} characters (minimum: {min_length})"
        )


def sanitize_string(value: str, max_length: int = 255) -> str:
    """Sanitize string input by removing dangerous characters.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        value = str(value)

    # Remove null bytes and control characters
    value = "".join(char for char in value if ord(char) >= 32 or char in "\n\r\t")

    # Trim to max length
    if len(value) > max_length:
        value = value[:max_length]

    return value.strip()
