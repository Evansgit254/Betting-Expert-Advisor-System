"""Reddit scraper using official PRAW API."""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from src.config import settings

logger = logging.getLogger(__name__)


class RedditScraper:
    """Reddit scraper using official PRAW API."""
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Initialize Reddit scraper."""
        self.client_id = client_id or settings.REDDIT_CLIENT_ID
        self.client_secret = client_secret or settings.REDDIT_CLIENT_SECRET
        self.user_agent = user_agent or settings.REDDIT_USER_AGENT
        self._reddit = None
        
        if self.client_id and self.client_secret:
            try:
                import praw
                self._reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    user_agent=self.user_agent
                )
                logger.info("Reddit scraper initialized")
            except ImportError:
                logger.warning("praw not installed")
            except Exception as e:
                logger.error(f"Failed to initialize Reddit: {e}")
    
    def is_available(self) -> bool:
        """Check if Reddit scraper is available."""
        return self._reddit is not None
    
    def scrape(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Scrape Reddit posts."""
        if not self.is_available():
            return []
        
        results = []
        subreddits = ['soccer', 'football']
        
        try:
            for sub_name in subreddits:
                subreddit = self._reddit.subreddit(sub_name)
                for submission in subreddit.search(query, limit=limit//2, time_filter='week'):
                    results.append({
                        'external_id': submission.id,
                        'author': str(submission.author) if submission.author else 'deleted',
                        'text': f"{submission.title}\n\n{submission.selftext}",
                        'created_at': datetime.fromtimestamp(submission.created_utc),
                        'url': f"https://reddit.com{submission.permalink}",
                        'metadata': {'subreddit': sub_name, 'score': submission.score}
                    })
            return results
        except Exception as e:
            logger.error(f"Error scraping Reddit: {e}")
            return []
    
    def scrape_sandbox(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return mock data."""
        return [
            {
                'external_id': f'reddit_mock_{i}',
                'author': f'user{i}',
                'text': f'Mock Reddit post about {query}',
                'created_at': datetime.utcnow() - timedelta(hours=i*2),
                'url': f'https://reddit.com/mock{i}',
                'metadata': {'subreddit': 'soccer', 'score': i*100}
            }
            for i in range(min(limit, 10))
        ]
