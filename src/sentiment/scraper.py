"""Social media scraper for sentiment analysis."""
import asyncio
import re
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import deque
import time

import aiohttp
from bs4 import BeautifulSoup

from src.logging_config import get_logger
from src.config import settings
from src.db import handle_db_errors
from src.sentiment.models import SentimentAnalysis, SentimentSource
from src.sentiment.analyzer import SentimentAnalyzer

logger = get_logger(__name__)


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_calls: int = 10, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls = deque(maxlen=max_calls)
    
    async def acquire(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()
        
        # Remove old calls
        while self.calls and now - self.calls[0] > self.window_seconds:
            self.calls.popleft()
        
        if len(self.calls) >= self.max_calls:
            wait_time = self.window_seconds - (now - self.calls[0])
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time + 0.1)
                self.calls.clear()
        
        self.calls.append(now)


class SentimentScraperService:
    """Service for scraping social media sentiment."""
    
    def __init__(self):
        self.analyzer = SentimentAnalyzer()
        self.rate_limiter = RateLimiter(
            max_calls=settings.SENTIMENT_RATE_LIMIT_CALLS,
            window_seconds=settings.SENTIMENT_RATE_LIMIT_WINDOW
        )
        self.enabled = settings.SENTIMENT_ENABLED
        
        logger.info(f"SentimentScraperService initialized (enabled={self.enabled})")
    
    async def scrape_all_sources(self, market_id: str, home_team: str, away_team: str) -> List[Dict]:
        """Scrape all configured sources for a match."""
        if not self.enabled:
            logger.debug("Sentiment scraping disabled")
            return []
        
        results = []
        
        try:
            # Scrape each source
            if settings.SENTIMENT_TWITTER_ENABLED:
                twitter_results = await self._scrape_twitter(market_id, home_team, away_team)
                results.extend(twitter_results)
            
            if settings.SENTIMENT_REDDIT_ENABLED:
                reddit_results = await self._scrape_reddit(market_id, home_team, away_team)
                results.extend(reddit_results)
            
            if settings.SENTIMENT_BLOG_ENABLED:
                blog_results = await self._scrape_blogs(market_id, home_team, away_team)
                results.extend(blog_results)
            
            logger.info(f"Scraped {len(results)} sentiment items for {market_id}")
            
            # Save to database
            if results:
                self._save_sentiment_results(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error scraping sentiment for {market_id}: {e}", exc_info=True)
            return []
    
    async def _scrape_twitter(self, market_id: str, home_team: str, away_team: str) -> List[Dict]:
        """Scrape Twitter/X for match sentiment."""
        results = []
        
        try:
            await self.rate_limiter.acquire()
            
            # Mock implementation - replace with actual Twitter API or scraper
            # For production, use tweepy or nitter scraper
            logger.debug(f"Scraping Twitter for {home_team} vs {away_team}")
            
            # Simulate Twitter data
            mock_tweets = [
                f"{home_team} looking strong ahead of the match! #football",
                f"Worried about {away_team}'s injury list...",
                f"Big game today! {home_team} vs {away_team}",
            ]
            
            for tweet in mock_tweets:
                sentiment = self.analyzer.analyze_text(tweet)
                
                # Determine which team the sentiment is about
                team = home_team if home_team.lower() in tweet.lower() else away_team
                
                results.append({
                    'market_id': market_id,
                    'team': team,
                    'text': tweet,
                    'sentiment_score': sentiment['score'],
                    'sentiment_label': sentiment['label'],
                    'keywords': sentiment['keywords'],
                    'source': 'twitter',
                })
            
        except Exception as e:
            logger.error(f"Twitter scraping error: {e}")
        
        return results
    
    async def _scrape_reddit(self, market_id: str, home_team: str, away_team: str) -> List[Dict]:
        """Scrape Reddit for match sentiment."""
        results = []
        
        try:
            await self.rate_limiter.acquire()
            
            # Mock implementation - replace with praw or pushshift
            logger.debug(f"Scraping Reddit for {home_team} vs {away_team}")
            
            # Simulate Reddit comments
            mock_comments = [
                f"{home_team} defense has been solid lately",
                f"{away_team} attack is on fire this season",
                f"This match could go either way",
            ]
            
            for comment in mock_comments:
                sentiment = self.analyzer.analyze_text(comment)
                
                team = home_team if home_team.lower() in comment.lower() else away_team
                
                results.append({
                    'market_id': market_id,
                    'team': team,
                    'text': comment,
                    'sentiment_score': sentiment['score'],
                    'sentiment_label': sentiment['label'],
                    'keywords': sentiment['keywords'],
                    'source': 'reddit',
                })
            
        except Exception as e:
            logger.error(f"Reddit scraping error: {e}")
        
        return results
    
    async def _scrape_blogs(self, market_id: str, home_team: str, away_team: str) -> List[Dict]:
        """Scrape football blogs and news sites."""
        results = []
        
        try:
            await self.rate_limiter.acquire()
            
            # Mock implementation - replace with actual RSS/HTML scraping
            logger.debug(f"Scraping blogs for {home_team} vs {away_team}")
            
            # Simulate blog posts
            mock_posts = [
                f"Match preview: {home_team} expected to dominate possession",
                f"{away_team} injury concerns ahead of big match",
            ]
            
            for post in mock_posts:
                sentiment = self.analyzer.analyze_text(post)
                
                team = home_team if home_team.lower() in post.lower() else away_team
                
                results.append({
                    'market_id': market_id,
                    'team': team,
                    'text': post,
                    'sentiment_score': sentiment['score'],
                    'sentiment_label': sentiment['label'],
                    'keywords': sentiment['keywords'],
                    'source': 'blog',
                })
            
        except Exception as e:
            logger.error(f"Blog scraping error: {e}")
        
        return results
    
    def _save_sentiment_results(self, results: List[Dict]):
        """Save sentiment results to database."""
        try:
            with handle_db_errors() as session:
                for result in results:
                    sentiment = SentimentAnalysis(
                        id=str(uuid.uuid4()),
                        market_id=result['market_id'],
                        team=result['team'],
                        sentiment_score=result['sentiment_score'],
                        sentiment_label=result['sentiment_label'],
                        keywords=result['keywords'],
                        source=result['source'],
                    )
                    session.add(sentiment)
                
                logger.info(f"Saved {len(results)} sentiment records to database")
                
        except Exception as e:
            logger.error(f"Error saving sentiment results: {e}", exc_info=True)
    
    def get_sentiment_for_match(self, market_id: str) -> Dict:
        """Get aggregated sentiment for a match."""
        try:
            with handle_db_errors() as session:
                sentiments = session.query(SentimentAnalysis).filter(
                    SentimentAnalysis.market_id == market_id
                ).all()
                
                if not sentiments:
                    return {'home': None, 'away': None}
                
                # Aggregate by team
                team_sentiments = {}
                for s in sentiments:
                    if s.team not in team_sentiments:
                        team_sentiments[s.team] = []
                    team_sentiments[s.team].append(s.sentiment_score)
                
                # Calculate average sentiment per team
                result = {}
                for team, scores in team_sentiments.items():
                    avg_score = sum(scores) / len(scores)
                    result[team] = {
                        'score': avg_score,
                        'label': 'positive' if avg_score > 0.1 else 'negative' if avg_score < -0.1 else 'neutral',
                        'sample_count': len(scores),
                    }
                
                return result
                
        except Exception as e:
            logger.error(f"Error getting sentiment for {market_id}: {e}")
            return {'home': None, 'away': None}
