"""Caching layer for API data to reduce external API calls."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pandas as pd
from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from src.db import Base, get_session
from src.logging_config import get_logger

logger = get_logger(__name__)

# Cache TTL (Time To Live)
FIXTURES_CACHE_TTL = timedelta(hours=1)  # Fixtures don't change often
ODDS_CACHE_TTL = timedelta(minutes=5)  # Odds change frequently


class CachedFixture(Base):
    """Cache for fixture data."""

    __tablename__ = "cached_fixtures"

    id = Column(Integer, primary_key=True)
    market_id = Column(String(255), unique=True, index=True, nullable=False)
    sport = Column(String(100))
    league = Column(String(255))
    home = Column(String(255))
    away = Column(String(255))
    start = Column(DateTime(timezone=True))
    data_json = Column(Text)  # Full fixture data as JSON
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("idx_fixtures_sport_fetched", "sport", "fetched_at"),)


class CachedOdds(Base):
    """Cache for odds data."""

    __tablename__ = "cached_odds"

    id = Column(Integer, primary_key=True)
    market_id = Column(String(255), index=True, nullable=False)
    selection = Column(String(100))
    odds = Column(Float)
    provider = Column(String(255))
    last_update = Column(DateTime(timezone=True))
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("idx_odds_market_fetched", "market_id", "fetched_at"),)


class DataCache:
    """Caching layer for fixtures and odds data."""

    def __init__(
        self, fixtures_ttl: Optional[timedelta] = None, odds_ttl: Optional[timedelta] = None
    ):
        """Initialize cache with custom TTLs.

        Args:
            fixtures_ttl: Time-to-live for fixtures cache
            odds_ttl: Time-to-live for odds cache
        """
        self.fixtures_ttl = fixtures_ttl or FIXTURES_CACHE_TTL
        self.odds_ttl = odds_ttl or ODDS_CACHE_TTL

    def get_cached_fixtures(self, sport: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Get cached fixtures if available and not stale.

        Args:
            sport: Filter by sport

        Returns:
            DataFrame of fixtures or None if cache miss/stale
        """
        cutoff_time = datetime.now(timezone.utc) - self.fixtures_ttl

        with get_session() as session:
            query = session.query(CachedFixture).filter(CachedFixture.fetched_at > cutoff_time)

            if sport:
                query = query.filter(CachedFixture.sport == sport)

            cached = query.all()

            if not cached:
                logger.info("Cache miss: No fresh fixtures in cache")
                return None

            # Convert to DataFrame
            data = [
                {
                    "market_id": f.market_id,
                    "home": f.home,
                    "away": f.away,
                    "start": f.start,
                    "sport": f.sport,
                    "league": f.league,
                }
                for f in cached
            ]

            df = pd.DataFrame(data)

            # Calculate age with timezone handling
            fetched_at = cached[0].fetched_at
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - fetched_at

            logger.info(f"Cache hit: Loaded {len(df)} fixtures from cache (age: {age})")
            return df

    def cache_fixtures(self, fixtures_df: pd.DataFrame, sport: Optional[str] = None) -> None:
        """Cache fixtures data.

        Args:
            fixtures_df: DataFrame of fixtures to cache
            sport: Sport category for cleanup
        """
        if fixtures_df.empty:
            return

        with get_session() as session:
            for _, row in fixtures_df.iterrows():
                # Check if already exists
                existing = (
                    session.query(CachedFixture).filter_by(market_id=row["market_id"]).first()
                )

                if existing:
                    # Update existing
                    existing.sport = row.get("sport", "unknown")
                    existing.league = row.get("league", "unknown")
                    existing.home = row.get("home", "")
                    existing.away = row.get("away", "")
                    existing.start = row.get("start")
                    existing.fetched_at = datetime.now(timezone.utc)
                else:
                    # Add new
                    cached = CachedFixture(
                        market_id=row["market_id"],
                        sport=row.get("sport", "unknown"),
                        league=row.get("league", "unknown"),
                        home=row.get("home", ""),
                        away=row.get("away", ""),
                        start=row.get("start"),
                        fetched_at=datetime.now(timezone.utc),
                    )
                    session.add(cached)
            session.commit()
            logger.info(f"Cached {len(fixtures_df)} fixtures")

    def get_cached_odds(self, market_ids: List[str]) -> Optional[pd.DataFrame]:
        """Get cached odds for specific markets.

        Args:
            market_ids: List of market IDs

        Returns:
            DataFrame of odds or None if cache miss/stale
        """
        if not market_ids:
            return None

        cutoff_time = datetime.now(timezone.utc) - self.odds_ttl

        with get_session() as session:
            cached = (
                session.query(CachedOdds)
                .filter(CachedOdds.market_id.in_(market_ids), CachedOdds.fetched_at > cutoff_time)
                .all()
            )

            if not cached:
                logger.info("Cache miss: No fresh odds in cache")
                return None

            # Check if we have all requested markets
            cached_market_ids = set(o.market_id for o in cached)
            requested_market_ids = set(market_ids)

            if not requested_market_ids.issubset(cached_market_ids):
                missing = requested_market_ids - cached_market_ids
                logger.info(f"Partial cache miss: Missing {len(missing)} markets")
                return None

            # Convert to DataFrame
            data = [
                {
                    "market_id": o.market_id,
                    "selection": o.selection,
                    "odds": o.odds,
                    "provider": o.provider,
                    "last_update": o.last_update,
                }
                for o in cached
            ]

            df = pd.DataFrame(data)

            # Calculate age with timezone handling
            fetched_at = cached[0].fetched_at
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - fetched_at

            logger.info(f"Cache hit: Loaded {len(df)} odds entries from cache (age: {age})")
            return df

    def cache_odds(self, odds_df: pd.DataFrame, market_ids: Optional[List[str]] = None) -> None:
        """Cache odds data.

        Args:
            odds_df: DataFrame of odds to cache
            market_ids: Optional list of market IDs for cleanup
        """
        if odds_df.empty:
            return

        with get_session() as session:
            # Clear old cache for these markets
            for _, row in odds_df.iterrows():
                # Check if already exists
                existing = (
                    session.query(CachedOdds)
                    .filter_by(market_id=row["market_id"], selection=row["selection"])
                    .first()
                )

                if existing:
                    # Update existing
                    existing.odds = row["odds"]
                    existing.provider = row.get("provider", "unknown")
                    existing.fetched_at = datetime.now(timezone.utc)
                else:
                    # Add new
                    cached = CachedOdds(
                        market_id=row["market_id"],
                        selection=row["selection"],
                        odds=row["odds"],
                        provider=row.get("provider", "unknown"),
                        fetched_at=datetime.now(timezone.utc),
                    )
                    session.add(cached)
            session.commit()
            logger.info(f"Cached {len(odds_df)} odds entries")

    def clear_cache(self, fixtures: bool = True, odds: bool = True) -> None:
        """Clear cached data.

        Args:
            fixtures: Clear fixtures cache
            odds: Clear odds cache
        """
        with get_session() as session:
            if fixtures:
                count = session.query(CachedFixture).delete()
                logger.info(f"Cleared {count} cached fixtures")

            if odds:
                count = session.query(CachedOdds).delete()
                logger.info(f"Cleared {count} cached odds")

            session.commit()

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with get_session() as session:
            fixtures_count = session.query(CachedFixture).count()
            odds_count = session.query(CachedOdds).count()

            # Get oldest and newest
            oldest_fixture = session.query(CachedFixture).order_by(CachedFixture.fetched_at).first()
            newest_fixture = (
                session.query(CachedFixture).order_by(CachedFixture.fetched_at.desc()).first()
            )

            oldest_odds = session.query(CachedOdds).order_by(CachedOdds.fetched_at).first()
            newest_odds = session.query(CachedOdds).order_by(CachedOdds.fetched_at.desc()).first()

            stats = {
                "fixtures_count": fixtures_count,
                "odds_count": odds_count,
                "fixtures_oldest": oldest_fixture.fetched_at if oldest_fixture else None,
                "fixtures_newest": newest_fixture.fetched_at if newest_fixture else None,
                "odds_oldest": oldest_odds.fetched_at if oldest_odds else None,
                "odds_newest": newest_odds.fetched_at if newest_odds else None,
            }

            return stats
