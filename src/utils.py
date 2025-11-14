"""Utility functions for validation and common operations."""
from datetime import datetime, timezone

from src.config import settings


def utc_now() -> datetime:
    """Return current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


def validate_odds(odds: float) -> bool:
    """Validate that odds are in reasonable range."""
    return 1.01 <= odds <= 1000.0


def validate_stake(stake: float, bankroll: float) -> bool:
    """Validate that stake is positive and within bankroll limits."""
    if stake <= 0:
        return False
    if stake > bankroll * settings.MAX_STAKE_FRAC:
        return False
    return True


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency string."""
    return f"{currency} {amount:.2f}"


class BettingExpertError(Exception):
    """Top-level application exception."""


class APICircuitBreakerError(BettingExpertError):
    """Raised when external API circuit breaker halts operation."""


class DBUnavailableError(BettingExpertError):
    """Raised for persistent DB/connectivity failures."""


class ModelDriftError(BettingExpertError):
    """Raised when model/feature drift detected, requiring retrain."""


class DataCorruptionError(BettingExpertError):
    """Raised when corrupt, missing, or malformed critical data files are encountered."""


class ConfigurationError(BettingExpertError):
    """Critical misconfiguration or missing setting."""


class ExternalServiceUnavailable(BettingExpertError):
    """Raised when an external service is unavailable due to circuit breaker or persistent failures."""


# Optionally, utility for error logging


def log_exception(e: Exception, context: str = ""):
    from src.logging_config import get_logger

    logger = get_logger("BettingExpert")
    logger.error(f"[{context}] {type(e).__name__}: {e}")
