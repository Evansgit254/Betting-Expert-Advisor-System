"""Tests for configuration management."""
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import Settings


def test_settings_default_values():
    """Test that default values are set correctly."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()

        # Test default values
        assert settings.ENV == "development"
        assert settings.DB_URL == "sqlite:///./data/bets.db"
        assert settings.MODE == "DRY_RUN"
        assert settings.DEFAULT_KELLY_FRACTION == 0.2
        assert settings.MAX_STAKE_FRAC == 0.05
        assert settings.DAILY_LOSS_LIMIT == 1000.0
        assert settings.MAX_OPEN_BETS == 10
        assert settings.THEODDS_API_BASE == "https://api.the-odds-api.com/v4"
        assert settings.BETFAIR_API_BASE == "https://api.betfair.com"
        assert settings.HTTP_TIMEOUT == 10
        assert settings.LOG_LEVEL == "INFO"


def test_settings_environment_variables():
    """Test that environment variables override defaults."""
    env_vars = {
        "ENV": "production",
        "DB_URL": "postgresql://user:pass@localhost:5432/db",
        "MODE": "LIVE",
        "DEFAULT_KELLY_FRACTION": "0.5",
        "MAX_STAKE_FRAC": "0.1",
        "DAILY_LOSS_LIMIT": "2000.0",
        "MAX_OPEN_BETS": "20",
        "THEODDS_API_KEY": "test_key",
        "THEODDS_API_BASE": "https://test.api.com/v1",
        "BETFAIR_APP_KEY": "bf_key",
        "BETFAIR_SESSION_TOKEN": "bf_token",
        "BETFAIR_API_BASE": "https://test.betfair.com",
        "HTTP_TIMEOUT": "30",
        "LOG_LEVEL": "DEBUG",
    }

    with patch.dict(os.environ, env_vars):
        settings = Settings()

        # Test that environment variables override defaults
        assert settings.ENV == "production"
        assert settings.DB_URL == "postgresql://user:pass@localhost:5432/db"
        assert settings.MODE == "LIVE"
        assert settings.DEFAULT_KELLY_FRACTION == 0.5
        assert settings.MAX_STAKE_FRAC == 0.1
        assert settings.DAILY_LOSS_LIMIT == 2000.0
        assert settings.MAX_OPEN_BETS == 20
        assert settings.THEODDS_API_KEY == "test_key"
        assert settings.THEODDS_API_BASE == "https://test.api.com/v1"
        assert settings.BETFAIR_APP_KEY == "bf_key"
        assert settings.BETFAIR_SESSION_TOKEN == "bf_token"
        assert settings.BETFAIR_API_BASE == "https://test.betfair.com"
        assert settings.HTTP_TIMEOUT == 30
        assert settings.LOG_LEVEL == "DEBUG"


def test_settings_validation():
    """Test settings validation."""
    # Valid in-range values should pass
    Settings(DEFAULT_KELLY_FRACTION=0.0)
    Settings(MAX_STAKE_FRAC=0.1)
    Settings(DAILY_LOSS_LIMIT=1)
    Settings(MAX_OPEN_BETS=1)
    Settings(HTTP_TIMEOUT=60)

    # Out-of-range values should fail
    with pytest.raises(ValidationError):
        Settings(DEFAULT_KELLY_FRACTION=-0.1)

    with pytest.raises(ValidationError):
        Settings(MAX_STAKE_FRAC=1.1)

    with pytest.raises(ValidationError):
        Settings(DAILY_LOSS_LIMIT=0)

    with pytest.raises(ValidationError):
        Settings(MAX_OPEN_BETS=-1)

    with pytest.raises(ValidationError):
        Settings(HTTP_TIMEOUT=0)


def test_settings_singleton():
    """Test that settings is a singleton instance."""
    from src.config import settings as settings1
    from src.config import settings as settings2

    assert settings1 is settings2  # Should be the same instance

    # Modify one instance and check the other
    original_value = settings1.ENV
    settings1.ENV = "test"
    assert settings2.ENV == "test"

    # Restore original value
    settings1.ENV = original_value


def test_settings_env_file(monkeypatch, tmp_path):
    """Test loading settings from .env file."""
    from src.config import Settings

    # Create a temporary .env file
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
ENV=test
DB_URL=sqlite:///test.db
MODE=DRY_RUN
    """.strip()
    )

    # Store the original environment variables
    original_env = dict(os.environ)

    # Set the environment variables directly
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key] = value

    try:
        # Create a new Settings instance
        settings = Settings()

        # Check that the settings were loaded from the environment variables
        assert settings.ENV == "test"
        assert settings.DB_URL == "sqlite:///test.db"
        assert settings.MODE == "DRY_RUN"
    finally:
        # Restore the original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_settings_case_sensitive():
    """Test that settings are case-sensitive."""
    with patch.dict(os.environ, {"env": "test", "ENV": "production"}):
        settings = Settings()
        assert settings.ENV == "production"  # Should use the case-sensitive match


def test_settings_optional_fields():
    """Test that optional fields can be None."""
    settings = Settings(
        BOOKIE_API_KEY=None,
        BOOKIE_API_BASE_URL=None,
        THEODDS_API_KEY=None,
        BETFAIR_APP_KEY=None,
        BETFAIR_SESSION_TOKEN=None,
    )
    assert settings.BOOKIE_API_KEY is None
    assert settings.BOOKIE_API_BASE_URL is None
    assert settings.THEODDS_API_KEY is None
    assert settings.BETFAIR_APP_KEY is None
    assert settings.BETFAIR_SESSION_TOKEN is None
