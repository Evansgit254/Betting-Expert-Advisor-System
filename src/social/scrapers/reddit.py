"""Reddit scraper using official API."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)


class RedditScraper:
    """Reddit API scraper with sandbox mode."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Initialize Reddit scraper.

        Args:
            client_id: Reddit client ID
            client_secret: Reddit client secret
            user_agent: User agent string
        """
        self.client_id = client_id or settings.REDDIT_CLIENT_ID
        self.client_secret = client_secret or settings.REDDIT_CLIENT_SECRET
        self.user_agent = user_agent or settings.REDDIT_USER_AGENT
        self.enabled = bool(self.client_id and self.client_secret)

        if not self.enabled:
            logger.warning("Reddit scraper disabled: No credentials configured")

    def search_posts(
        self,
        query: str,
        subreddits: Optional[List[str]] = None,
        max_results: int = 100,
        hours_back: int = 24,
    ) -> List[Dict]:
        """Search Reddit posts matching query.

        Args:
            query: Search query
            subreddits: List of subreddits to search (None = all)
            max_results: Maximum posts to return
            hours_back: Hours back to search

        Returns:
            List of post dicts with keys: id, text, author, created_at, url, score
        """
        if not self.enabled:
            logger.info("Reddit scraper disabled, using sandbox data")
            return self._get_sandbox_data(query, max_results)

        try:
            import praw

            # Initialize Reddit client
            reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )

            # Determine search scope
            if subreddits:
                search_scope = "+".join(subreddits)
                subreddit = reddit.subreddit(search_scope)
            else:
                subreddit = reddit.subreddit("all")

            # Calculate time threshold
            time_threshold = datetime.utcnow() - timedelta(hours=hours_back)

            # Search posts
            posts = []
            for submission in subreddit.search(query, limit=max_results, sort="new"):
                created_time = datetime.utcfromtimestamp(submission.created_utc)

                # Filter by time
                if created_time < time_threshold:
                    continue

                # Combine title and selftext
                text = submission.title
                if submission.selftext:
                    text += f"\n{submission.selftext}"

                posts.append({
                    "id": submission.id,
                    "text": text,
                    "author": str(submission.author) if submission.author else "deleted",
                    "created_at": created_time.isoformat() + "Z",
                    "url": f"https://reddit.com{submission.permalink}",
                    "score": submission.score,
                    "subreddit": submission.subreddit.display_name,
                })

            logger.info(f"Fetched {len(posts)} Reddit posts for query: {query}")
            return posts

        except ImportError:
            logger.error("praw not installed. Install with: pip install praw")
            return self._get_sandbox_data(query, max_results)
        except Exception as e:
            logger.error(f"Reddit API error: {e}")
            return []

    def _get_sandbox_data(self, query: str, max_results: int) -> List[Dict]:
        """Return mock data for testing.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of mock post dicts
        """
        mock_posts = [
            {
                "id": f"mock_post_{i}",
                "text": f"Discussion about {query}\n\nI think they have a good chance in the upcoming match. The team looks strong.",
                "author": f"redditor_{i}",
                "created_at": (datetime.utcnow() - timedelta(hours=i * 2)).isoformat() + "Z",
                "url": f"https://reddit.com/r/soccer/comments/mock_{i}",
                "score": 50 + i * 5,
                "subreddit": "soccer",
            }
            for i in range(min(max_results, 10))
        ]

        logger.info(f"Generated {len(mock_posts)} sandbox Reddit posts for: {query}")
        return mock_posts


def search_football_posts(
    team_name: str, max_results: int = 100, hours_back: int = 24
) -> List[Dict]:
    """Convenience function to search football-related Reddit posts.

    Args:
        team_name: Team name to search for
        max_results: Maximum posts to return
        hours_back: Hours back to search

    Returns:
        List of post dicts
    """
    scraper = RedditScraper()
    subreddits = ["soccer", "football", "PremierLeague", "championship"]
    return scraper.search_posts(team_name, subreddits, max_results, hours_back)
