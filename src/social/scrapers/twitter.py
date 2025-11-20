"""Twitter/X scraper using official API."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)


class TwitterScraper:
    """Twitter/X API scraper with sandbox mode."""

    def __init__(self, bearer_token: Optional[str] = None):
        """Initialize Twitter scraper.

        Args:
            bearer_token: Twitter API bearer token (optional, uses config if not provided)
        """
        self.bearer_token = bearer_token or settings.TWITTER_BEARER_TOKEN
        self.base_url = "https://api.twitter.com/2"
        self.enabled = bool(self.bearer_token)

        if not self.enabled:
            logger.warning("Twitter scraper disabled: No bearer token configured")

    def search_tweets(
        self, query: str, max_results: int = 100, hours_back: int = 24
    ) -> List[Dict]:
        """Search tweets matching query.

        Args:
            query: Search query (e.g., "Manchester United")
            max_results: Maximum tweets to return
            hours_back: How many hours back to search

        Returns:
            List of tweet dicts with keys: id, text, author, created_at, url
        """
        if not self.enabled:
            logger.info("Twitter scraper disabled, using sandbox data")
            return self._get_sandbox_data(query, max_results)

        try:
            import requests

            # Calculate start time
            start_time = datetime.utcnow() - timedelta(hours=hours_back)
            start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Build request
            url = f"{self.base_url}/tweets/search/recent"
            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            params = {
                "query": query,
                "max_results": min(max_results, 100),  # API limit
                "start_time": start_time_str,
                "tweet.fields": "created_at,author_id,public_metrics",
                "expansions": "author_id",
                "user.fields": "username",
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Parse response
            tweets = []
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            for tweet in data.get("data", []):
                author_id = tweet.get("author_id")
                author = users.get(author_id, {}).get("username", "unknown")

                tweets.append({
                    "id": tweet["id"],
                    "text": tweet["text"],
                    "author": author,
                    "created_at": tweet["created_at"],
                    "url": f"https://twitter.com/{author}/status/{tweet['id']}",
                    "metrics": tweet.get("public_metrics", {}),
                })

            logger.info(f"Fetched {len(tweets)} tweets for query: {query}")
            return tweets

        except Exception as e:
            logger.error(f"Twitter API error: {e}")
            return []

    def _get_sandbox_data(self, query: str, max_results: int) -> List[Dict]:
        """Return mock data for testing without API credentials.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of mock tweet dicts
        """
        # Generate realistic mock data
        mock_tweets = [
            {
                "id": f"mock_tweet_{i}",
                "text": f"Great performance by {query}! Looking forward to the next match. #football",
                "author": f"fan_{i}",
                "created_at": (datetime.utcnow() - timedelta(hours=i)).isoformat() + "Z",
                "url": f"https://twitter.com/fan_{i}/status/mock_{i}",
                "metrics": {"like_count": 10 + i, "retweet_count": 2 + i},
            }
            for i in range(min(max_results, 10))
        ]

        logger.info(f"Generated {len(mock_tweets)} sandbox tweets for: {query}")
        return mock_tweets


def search_football_tweets(
    team_name: str, max_results: int = 100, hours_back: int = 24
) -> List[Dict]:
    """Convenience function to search football-related tweets.

    Args:
        team_name: Team name to search for
        max_results: Maximum tweets to return
        hours_back: Hours back to search

    Returns:
        List of tweet dicts
    """
    scraper = TwitterScraper()
    query = f"{team_name} (football OR soccer OR match OR game) -is:retweet lang:en"
    return scraper.search_tweets(query, max_results, hours_back)
