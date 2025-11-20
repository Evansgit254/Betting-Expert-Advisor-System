"""Application configuration using Pydantic settings.

This module centralizes environment configuration with validation and
runtime safety checks introduced as part of the critical fixes rollout.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Module-level logger for validators (cannot use get_logger due to circular import)
_logger = logging.getLogger(__name__)


LIVE_MODE_REQUIRED_FIELDS = (
    "BOOKIE_API_KEY",
    "BOOKIE_API_BASE_URL",
    "BETFAIR_APP_KEY",
    "BETFAIR_SESSION_TOKEN",
)


class Settings(BaseSettings):
    """Application settings loaded from environment with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        validate_assignment=True,
        extra="ignore",
    )

    # Core environment configuration
    ENV: str = Field(default="development")
    DB_URL: str = Field(default="sqlite:///./data/bets.db")
    MODE: str = Field(default="DRY_RUN")
    LOG_LEVEL: str = Field(default="INFO")
    HTTP_TIMEOUT: int = Field(default=10, ge=1, le=120)

    # Risk management defaults
    DEFAULT_KELLY_FRACTION: float = Field(default=0.2, ge=0.0, le=1.0)
    MAX_STAKE_FRAC: float = Field(default=0.05, ge=0.0, le=0.2)
    DAILY_LOSS_LIMIT: float = Field(default=1000.0, gt=0)
    MAX_OPEN_BETS: int = Field(default=10, ge=0, le=500)
    CONSECUTIVE_LOSS_LIMIT: int = Field(default=5, ge=1, le=20)
    CONSECUTIVE_LOSS_WARN: int = Field(default=3, ge=1, le=10)
    MAX_DRAWDOWN_FRACTION: float = Field(default=0.20, ge=0.0, le=0.9)
    DRAWDOWN_WARN_FRACTION: float = Field(default=0.15, ge=0.0, le=0.5)
    RATE_LIMIT_PER_MINUTE: int = Field(default=10, ge=1, le=120)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=10, le=300)
    MAX_RECENT_LOSSES_CHECK: int = Field(default=10, ge=5, le=50)
    PEAK_BANKROLL_DAYS: int = Field(default=30, ge=7, le=365)
    
    # Betting configuration
    MIN_ODDS: float = Field(default=1.2, ge=1.01)
    MAX_ODDS: float = Field(default=10.0, le=100.0)
    MIN_EV: float = Field(default=0.05, ge=0.0)
    MIN_SHARPE: float = Field(default=0.1, ge=0.0)
    MIN_CONFIDENCE: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Active sports/leagues to track
    ACTIVE_SPORTS: List[str] = Field(
        default=[
            "soccer_epl",
            "soccer_spain_la_liga",
            "soccer_germany_bundesliga",
            "soccer_italy_serie_a",
            "soccer_france_ligue_one",
            "soccer_uefa_champs_league"
        ]
    )
    
    # Alternative Markets
    ACTIVE_MARKETS: List[str] = Field(
        default=["h2h", "totals", "btts"],  # h2h=match result, totals=over/under, btts=both teams score
        description="Active betting markets to analyze"
    )
    
    # Live Betting Settings
    LIVE_BETTING_ENABLED: bool = Field(default=False, description="Enable live in-play betting")
    LIVE_MAX_STAKE_PCT: float = Field(default=0.05, ge=0.01, le=0.10, description="Max 5% per live bet")
    LIVE_EXECUTION_TIMEOUT: int = Field(default=3, ge=1, le=10, description="Live bet timeout (seconds)")
    LIVE_ODDS_CHANGE_TOLERANCE: float = Field(default=0.10, description="Accept 10% odds change")
    LIVE_MIN_TIME_REMAINING: int = Field(default=10, description="Min 10 minutes remaining")

    # Circuit Breaker configuration
    CIRCUIT_BREAKER_MAX_FAILURES: int = Field(default=5, ge=1, le=20)
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = Field(default=60, ge=10, le=600)
    
    # Cache TTLs
    FIXTURES_CACHE_TTL_MINUTES: int = Field(default=60, ge=1, le=1440)
    ODDS_CACHE_TTL_SECONDS: int = Field(default=300, ge=10, le=3600)

    # Backtest defaults
    BACKTEST_DEFAULT_DAYS: int = Field(default=90, ge=7, le=365)
    BACKTEST_INITIAL_BANKROLL: float = Field(default=10000.0, ge=100.0)
    BACKTEST_GAMES_PER_DAY: int = Field(default=5, ge=1, le=50)

    # API configuration
    BOOKIE_API_KEY: Optional[str] = Field(default=None)
    BOOKIE_API_BASE_URL: Optional[str] = Field(default=None)
    THEODDS_API_KEY: Optional[str] = Field(default=None)
    THEODDS_API_BASE: str = Field(default="https://api.the-odds-api.com/v4")
    BETFAIR_APP_KEY: Optional[str] = Field(default=None)
    BETFAIR_SESSION_TOKEN: Optional[str] = Field(default=None)
    BETFAIR_API_BASE: str = Field(default="https://api.betfair.com")

    # Alerting / telemetry
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None)
    TELEGRAM_CHAT_ID: Optional[str] = Field(default=None)

    PAPER_TRADING_DAYS_REQUIRED: int = Field(default=30, ge=0, le=365)
    
    # Social Signals & Sentiment Analysis
    ENABLE_SOCIAL_SIGNALS: bool = Field(default=False, description="Enable social sentiment analysis feature")
    SOCIAL_SCRAPE_SOURCES: str = Field(default="twitter,reddit,blogs", description="Comma-separated list of sources")
    SOCIAL_SCRAPE_INTERVAL_MINUTES: int = Field(default=10, ge=1, le=1440)
    SOCIAL_DATA_RETENTION_DAYS: int = Field(default=30, ge=1, le=365)
    SENTIMENT_MODEL: str = Field(default="vader", description="Sentiment model: vader or hf-distilbert")
    MIN_MATCH_CONFIDENCE: float = Field(default=0.6, ge=0.0, le=1.0)
    ARBITRAGE_COMMISSION_RATE: float = Field(default=0.02, ge=0.0, le=0.1)
    MAX_POSTS_PER_MATCH: int = Field(default=200, ge=10, le=1000)
    
    # Social API credentials (optional)
    TWITTER_BEARER_TOKEN: Optional[str] = Field(default=None)
    REDDIT_CLIENT_ID: Optional[str] = Field(default=None)
    REDDIT_CLIENT_SECRET: Optional[str] = Field(default=None)
    REDDIT_USER_AGENT: str = Field(default="BettingAdvisorBot/0.1")
    
    # Sentiment Analysis Configuration
    SENTIMENT_ENABLED: bool = Field(default=True, description="Enable sentiment analysis")
    SENTIMENT_TWITTER_ENABLED: bool = Field(default=True)
    SENTIMENT_REDDIT_ENABLED: bool = Field(default=True)
    SENTIMENT_BLOG_ENABLED: bool = Field(default=True)
    SENTIMENT_RATE_LIMIT_CALLS: int = Field(default=10, ge=1, le=100)
    SENTIMENT_RATE_LIMIT_WINDOW: int = Field(default=60, ge=10, le=300)
    
    # Arbitrage Detection Configuration
    ARBITRAGE_ENABLED: bool = Field(default=True, description="Enable arbitrage detection")
    ARBITRAGE_MIN_PROFIT_MARGIN: float = Field(default=0.01, ge=0.001, le=0.1, description="Minimum 1% profit")
    ARBITRAGE_MAX_STAKE: float = Field(default=10000.0, ge=100.0)
    ARBITRAGE_EXECUTION_TIMEOUT: int = Field(default=5, ge=1, le=60, description="Seconds for simultaneous execution")
    
    # Portfolio Optimization Settings
    PORTFOLIO_OPTIMIZATION_ENABLED: bool = Field(default=True, description="Enable portfolio optimization")
    PORTFOLIO_MAX_POSITION_SIZE: float = Field(default=0.15, ge=0.01, le=0.5, description="Max 15% per bet")
    PORTFOLIO_MIN_DIVERSIFICATION: int = Field(default=1, ge=1, le=10, description="Min number of bets")
    
    # Database retry and connection pooling configuration
    DB_RETRY_ATTEMPTS: int = Field(default=3, ge=1, le=10, description="Number of retry attempts for DB operations")
    DB_RETRY_WAIT_MIN: int = Field(default=1, ge=1, le=10, description="Minimum wait time between retries (seconds)")
    DB_RETRY_WAIT_MAX: int = Field(default=5, ge=1, le=60, description="Maximum wait time between retries (seconds)")
    DB_POOL_SIZE: int = Field(default=10, ge=1, le=100, description="Maximum persistent database connections")
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0, le=100, description="Additional connections during burst")
    DB_POOL_TIMEOUT: int = Field(default=30, ge=5, le=300, description="Timeout waiting for connection (seconds)")
    DB_POOL_RECYCLE: int = Field(default=3600, ge=300, le=86400, description="Recycle connections after this many seconds")
    DB_CONNECT_TIMEOUT: int = Field(default=15, ge=5, le=60, description="SQLite-specific connection timeout")

    @field_validator("ENV")
    @classmethod
    def normalize_env(cls, value: str) -> str:
        """Ensure ENV is stored in lowercase for consistency."""
        return value.strip().lower() if value else value

    @field_validator("MODE")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        """Constrain MODE to supported values and emit cautionary logs."""
        normalized = value.strip().upper()
        if normalized not in {"DRY_RUN", "LIVE"}:
            raise ValueError("MODE must be DRY_RUN or LIVE")
        if normalized == "LIVE":
            # Use module-level logger to avoid circular import during Settings initialization
            _logger.warning("LIVE MODE ENABLED - ensure production safeguards are satisfied")
        return normalized

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Validate and normalize logging level strings."""
        level = value.strip().upper()
        valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if level not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(valid_levels)}")
        return level

    def validate_live_mode_requirements(self) -> List[str]:
        """Return missing configuration keys required before enabling LIVE mode."""
        missing: List[str] = []
        for field_name in LIVE_MODE_REQUIRED_FIELDS:
            if not getattr(self, field_name, None):
                missing.append(field_name)
        return missing

    def assert_live_mode_ready(self) -> None:
        """Raise ValueError if LIVE mode requirements are not satisfied."""
        missing = self.validate_live_mode_requirements()
        if missing:
            missing_list = ", ".join(missing)
            raise ValueError("Cannot enable LIVE mode without configuration: " + missing_list)


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    """Internal helper to memoize settings instantiation."""
    return Settings()


settings = _load_settings()


__all__ = ["Settings", "settings", "LIVE_MODE_REQUIRED_FIELDS"]
