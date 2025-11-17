"""Twitter/X scraper using official API."""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from src.config import settings

logger = logging.getLogger(__name__)


class TwitterScraper:
    """Twitter scraper using official API (requires bearer token)."""
    
    def __init__(self, bearer_token: Optional[str] = None):
        """Initialize Twitter scraper.
        
        Args:
            bearer_token: Twitter API bearer token
        """
        self.bearer_token = bearer_token or settings.TWITTER_BEARER_TOKEN
        self._client = None
        
        if self.bearer_token:
            try:
                import tweepy
                self._client = tweepy.Client(bearer_token=self.bearer_token)
                logger.info("Twitter scraper initialized with API access")
            except ImportError:
                logger.warning("tweepy not installed. Install with: pip install tweepy")
            except Exception as e:
                logger.error(f"Failed to initialize Twitter client: {e}")
    
    def is_available(self) -> bool:
        """Check if Twitter scraper is available."""
        return self._client is not None
    
    def scrape(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Scrape tweets matching query.
        
        Args:
            query: Search query
            limit: Maximum tweets to return
        
        Returns:
            List of tweet dictionaries
        """
        if not self.is_available():
            logger.warning("Twitter scraper not available (no API credentials)")
            return []
        
        try:
            # Search recent tweets (last 7 days)
            tweets = self._client.search_recent_tweets(
                query=query,
                max_results=min(limit, 100),  # API limit
                tweet_fields=['created_at', 'author_id', 'public_metrics'],
                expansions=['author_id'],
                user_fields=['username']
            )
            
            if not tweets.data:
                return []
            
            # Build user lookup
            users = {user.id: user.username for user in tweets.includes.get('users', [])}
            
            results = []
            for tweet in tweets.data:
                results.append({
                    'external_id': str(tweet.id),
                    'author': users.get(tweet.author_id, 'unknown'),
                    'text': tweet.text,
                    'created_at': tweet.created_at,
                    'url': f"https://twitter.com/i/web/status/{tweet.id}",
                    'metadata': {
                        'retweet_count': tweet.public_metrics.get('retweet_count', 0),
                        'like_count': tweet.public_metrics.get('like_count', 0),
                        'reply_count': tweet.public_metrics.get('reply_count', 0),
                    }
                })
            
            logger.info(f"Scraped {len(results)} tweets for query: {query}")
            return results
        
        except Exception as e:
            logger.error(f"Error scraping Twitter: {e}")
            return []
    
    def scrape_sandbox(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return mock data for testing without API access.
        
        Args:
            query: Search query
            limit: Maximum tweets to return
        
        Returns:
            List of mock tweet dictionaries
        """
        logger.info(f"Using Twitter sandbox mode for query: {query}")
        
        # Generate mock tweets
        mock_tweets = [
            {
                'external_id': f'twitter_mock_{i}',
                'author': f'user{i}',
                'text': f'Mock tweet about {query}. This is a test post #{i}',
                'created_at': datetime.utcnow() - timedelta(hours=i),
                'url': f'https://twitter.com/mock/status/{i}',
                'metadata': {
                    'retweet_count': i * 10,
                    'like_count': i * 50,
                    'reply_count': i * 5,
                }
            }
            for i in range(min(limit, 10))
        ]
        
        return mock_tweets
