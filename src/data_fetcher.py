"""Data fetching module with adapters for multiple data sources."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from src.logging_config import get_logger

logger = get_logger(__name__)


class DataSourceInterface(ABC):
    """Abstract interface for data sources."""

    @abstractmethod
    def fetch_fixtures(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Fetch fixtures/events within date range.

        Returns DataFrame with columns: market_id, home, away, start
        """

    @abstractmethod
    def fetch_odds(self, market_ids: List[str]) -> pd.DataFrame:
        """Fetch current odds for given market IDs.

        Returns DataFrame with columns: market_id, selection, odds
        """


class MockDataSource(DataSourceInterface):
    """Mock data source for testing and development.

    Returns sample fixtures and synthetic odds for backtesting.
    """

    def fetch_fixtures(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Generate sample fixtures."""
        logger.info("Fetching mock fixtures")

        if start_date is None:
            start_date = datetime.now(timezone.utc)

        data = [
            {
                "market_id": "m1",
                "home": "Team A",
                "away": "Team B",
                "start": datetime(2024, 1, 1, 15, 0, tzinfo=timezone.utc),
                "sport": "soccer",
                "league": "Premier League",
            },
            {
                "market_id": "m2",
                "home": "Team C",
                "away": "Team D",
                "start": datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc),
                "sport": "soccer",
                "league": "Premier League",
            },
            {
                "market_id": "m3",
                "home": "Team E",
                "away": "Team F",
                "start": datetime(2024, 1, 2, 19, 0, tzinfo=timezone.utc),
                "sport": "soccer",
                "league": "Championship",
            },
            {
                "market_id": "m4",
                "home": "Team G",
                "away": "Team H",
                "start": datetime(2024, 1, 2, 20, 0, tzinfo=timezone.utc),
                "sport": "soccer",
                "league": "Championship",
            },
        ]

        df = pd.DataFrame(data)

        # Filter by date range if provided
        if start_date:
            df = df[df["start"] >= start_date]
        if end_date:
            df = df[df["start"] <= end_date]

        logger.info(f"Fetched {len(df)} mock fixtures")
        return df

    def fetch_odds(self, market_ids: List[str]) -> pd.DataFrame:
        """Generate synthetic odds for given markets."""
        logger.info(f"Fetching mock odds for {len(market_ids)} markets")

        rows = []
        for market_id in market_ids:
            # Generate realistic odds with bookmaker margin
            import random

            random.seed(hash(market_id) % 10000)

            # True probability (random between 0.2 and 0.8)
            true_prob_home = 0.2 + random.random() * 0.6
            true_prob_away = 1 - true_prob_home

            # Add bookmaker margin (5%)
            margin = 1.05
            implied_prob_home = true_prob_home * margin
            implied_prob_away = true_prob_away * margin

            # Convert to decimal odds
            odds_home = 1.0 / implied_prob_home if implied_prob_home > 0 else 2.0
            odds_away = 1.0 / implied_prob_away if implied_prob_away > 0 else 2.0

            # Clamp to reasonable range
            odds_home = max(1.01, min(odds_home, 50.0))
            odds_away = max(1.01, min(odds_away, 50.0))

            rows.append(
                {
                    "market_id": market_id,
                    "selection": "home",
                    "odds": round(odds_home, 2),
                    "provider": "MockBookie",
                }
            )
            rows.append(
                {
                    "market_id": market_id,
                    "selection": "away",
                    "odds": round(odds_away, 2),
                    "provider": "MockBookie",
                }
            )

            # Add draw option for some markets
            if random.random() > 0.5:
                rows.append(
                    {
                        "market_id": market_id,
                        "selection": "draw",
                        "odds": round(2.8 + random.random() * 1.5, 2),
                        "provider": "MockBookie",
                    }
                )

        df = pd.DataFrame(rows)
        logger.info(f"Generated {len(df)} mock odds entries")
        return df


class DataFetcher:
    """Main data fetcher with pluggable data sources and caching."""

    def __init__(self, source: Optional[DataSourceInterface] = None, use_cache: bool = True):
        """Initialize with a data source.

        Args:
            source: Data source implementation (defaults to MockDataSource)
            use_cache: Enable caching to reduce API calls (default: True)
        """
        self.source = source or MockDataSource()
        self._custom_source = source is not None
        self.use_cache = False
        self.cache = None

        # Try to enable caching
        if use_cache and not self._custom_source:
            try:
                from src.cache import DataCache

                self.cache = DataCache()
                self.use_cache = True
            except Exception as e:
                logger.warning(f"Caching not available: {e}")
                self.use_cache = False

        logger.info(
            "Initialized DataFetcher with %s (cache: %s)",
            self.source.__class__.__name__,
            self.use_cache,
        )

    def get_fixtures(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Fetch fixtures from the configured source with caching.

        Args:
            start_date: Filter start date
            end_date: Filter end date
            force_refresh: Skip cache and fetch fresh data

        Returns:
            DataFrame of fixtures
        """
        # Try cache first (if enabled and not forcing refresh)
        if self.use_cache and self.cache and not force_refresh:
            cached_fixtures = self.cache.get_cached_fixtures()
            if cached_fixtures is not None:
                if not cached_fixtures.empty and "start" in cached_fixtures.columns:
                    cached_fixtures["start"] = pd.to_datetime(
                        cached_fixtures["start"], utc=True, errors="coerce"
                    )
                # Apply date filtering to cached data
                if start_date:
                    cached_fixtures = cached_fixtures[cached_fixtures["start"] >= start_date]
                if end_date:
                    cached_fixtures = cached_fixtures[cached_fixtures["start"] <= end_date]
                return cached_fixtures

        # Cache miss or disabled - fetch from source
        logger.info("Fetching fresh fixtures from source")
        fixtures = self.source.fetch_fixtures(start_date, end_date)
        if not fixtures.empty and "start" in fixtures.columns:
            fixtures["start"] = pd.to_datetime(fixtures["start"], utc=True, errors="coerce")

        # Cache the results
        if self.use_cache and self.cache and not fixtures.empty:
            self.cache.cache_fixtures(fixtures)

        return fixtures

    def get_odds(self, market_ids: List[str], force_refresh: bool = False) -> pd.DataFrame:
        """Fetch odds from the configured source with caching.

        Args:
            market_ids: List of market IDs to fetch odds for
            force_refresh: Skip cache and fetch fresh data

        Returns:
            DataFrame of odds
        """
        if not market_ids:
            logger.warning("No market IDs provided for odds fetch")
            return pd.DataFrame()

        # Try cache first (if enabled and not forcing refresh)
        if self.use_cache and self.cache and not force_refresh:
            cached_odds = self.cache.get_cached_odds(market_ids)
            if cached_odds is not None:
                return cached_odds

        # Cache miss or disabled - fetch from source
        logger.info(f"Fetching fresh odds for {len(market_ids)} markets from source")
        odds = self.source.fetch_odds(market_ids)

        # Cache the results
        if self.use_cache and self.cache and not odds.empty:
            self.cache.cache_odds(odds, market_ids)

        return odds

    def get_fixtures_with_odds(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Fetch fixtures and their current odds in one call.

        Returns:
            DataFrame with fixtures joined to odds
        """
        fixtures = self.get_fixtures(start_date, end_date)

        if fixtures.empty:
            logger.warning("No fixtures found")
            return pd.DataFrame()

        market_ids = fixtures["market_id"].tolist()
        odds = self.get_odds(market_ids)

        if odds.empty:
            logger.warning("No odds found for fixtures")
            return fixtures

        # Merge fixtures with odds
        result = fixtures.merge(odds, on="market_id", how="left")
        if "start" in result.columns:
            result["start"] = pd.to_datetime(result["start"], utc=True, errors="coerce")
        logger.info(f"Fetched {len(fixtures)} fixtures with {len(odds)} odds entries")

        return result
