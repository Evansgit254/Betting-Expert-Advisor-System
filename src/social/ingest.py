"""Social signals ingestion orchestrator."""
import argparse
from datetime import datetime
from typing import Dict, List, Optional

from src.config import settings
from src.logging_config import get_logger
from src.social.aggregator import aggregate_all_matches
from src.social.matcher import batch_link_posts
from src.social.models import SocialPost, SocialSentiment
from src.social.scrapers.blogs import scrape_football_blogs
from src.social.scrapers.reddit import search_football_posts
from src.social.scrapers.twitter import search_football_tweets
from src.social.sentiment import analyze_text
from src.db import handle_db_errors
from src.data_fetcher import DataFetcher

logger = get_logger(__name__)


class SocialIngestor:
    """Orchestrates social media scraping and processing."""

    def __init__(self, sandbox_mode: bool = False):
        """Initialize ingestor."""
        self.sandbox_mode = sandbox_mode
        self.data_fetcher = DataFetcher()

    def scrape_all_sources(self, team_names: List[str], max_per_source: int = 50) -> List[Dict]:
        """Scrape all configured sources."""
        all_posts = []
        sources = settings.SOCIAL_SCRAPE_SOURCES.split(",")

        for source in sources:
            source = source.strip().lower()

            if source == "twitter":
                all_posts.extend(self._scrape_twitter(team_names, max_per_source))
            elif source == "reddit":
                all_posts.extend(self._scrape_reddit(team_names, max_per_source))
            elif source == "blogs":
                all_posts.extend(self._scrape_blogs(max_per_source))
            else:
                logger.warning(f"Unknown source: {source}")

        logger.info(f"Scraped {len(all_posts)} total posts from {len(sources)} sources")
        return all_posts

    def _scrape_twitter(self, team_names: List[str], max_per_team: int) -> List[Dict]:
        """Scrape Twitter for team mentions."""
        posts = []
        for team in team_names:
            try:
                team_posts = search_football_tweets(team, max_per_team)
                for post in team_posts:
                    post["source"] = "twitter"
                    post["external_post_id"] = post["id"]
                posts.extend(team_posts)
            except Exception as e:
                logger.error(f"Error scraping Twitter for {team}: {e}")
        return posts

    def _scrape_reddit(self, team_names: List[str], max_per_team: int) -> List[Dict]:
        """Scrape Reddit for team mentions."""
        posts = []
        for team in team_names:
            try:
                team_posts = search_football_posts(team, max_per_team)
                for post in team_posts:
                    post["source"] = "reddit"
                    post["external_post_id"] = post["id"]
                posts.extend(team_posts)
            except Exception as e:
                logger.error(f"Error scraping Reddit for {team}: {e}")
        return posts

    def _scrape_blogs(self, max_entries: int) -> List[Dict]:
        """Scrape blog RSS feeds."""
        try:
            posts = scrape_football_blogs(max_entries)
            for post in posts:
                post["source"] = "blog"
                post["external_post_id"] = post["id"]
            return posts
        except Exception as e:
            logger.error(f"Error scraping blogs: {e}")
            return []

    def get_active_fixtures(self) -> List[Dict]:
        """Get active fixtures for matching."""
        try:
            fixtures_df = self.data_fetcher.get_fixtures()
            
            fixtures = []
            for _, row in fixtures_df.iterrows():
                fixtures.append({
                    "id": row.get("fixture_id", row.get("id")),
                    "home_team": row.get("home_team"),
                    "away_team": row.get("away_team"),
                    "commence_time": row.get("commence_time"),
                })
            
            logger.info(f"Retrieved {len(fixtures)} active fixtures")
            return fixtures
            
        except Exception as e:
            logger.error(f"Error getting fixtures: {e}")
            return []

    def extract_team_names_from_fixtures(self, fixtures: List[Dict]) -> List[str]:
        """Extract unique team names from fixtures."""
        teams = set()
        for fixture in fixtures:
            if fixture.get("home_team"):
                teams.add(fixture["home_team"])
            if fixture.get("away_team"):
                teams.add(fixture["away_team"])
        
        return list(teams)

    def save_posts_to_db(self, posts: List[Dict]) -> int:
        """Save posts to database."""
        saved_count = 0

        try:
            with handle_db_errors() as session:
                for post in posts:
                    # Check if post already exists
                    existing = (
                        session.query(SocialPost)
                        .filter(
                            SocialPost.source == post["source"],
                            SocialPost.external_post_id == post["external_post_id"],
                        )
                        .first()
                    )

                    if existing:
                        continue

                    # Parse created_at
                    try:
                        created_at = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))
                    except Exception:
                        created_at = datetime.utcnow()

                    # Create post record
                    social_post = SocialPost(
                        source=post["source"],
                        external_post_id=post["external_post_id"],
                        author=post.get("author", "unknown"),
                        text=post["text"],
                        created_at=created_at,
                        match_id=post.get("match_id"),
                        match_confidence=post.get("match_confidence", 0.0),
                        url=post.get("url"),
                        post_metadata={
                            "metrics": post.get("metrics"),
                            "subreddit": post.get("subreddit"),
                            "score": post.get("score"),
                        },
                    )

                    session.add(social_post)
                    session.flush()

                    # Analyze sentiment
                    sentiment_result = analyze_text(post["text"])

                    # Create sentiment record
                    sentiment = SocialSentiment(
                        post_id=social_post.id,
                        sentiment_score=sentiment_result["score"],
                        sentiment_label=sentiment_result["label"],
                        model=sentiment_result["model"],
                        confidence=sentiment_result.get("confidence", 0.0),
                    )

                    session.add(sentiment)
                    saved_count += 1

                session.commit()
                logger.info(f"Saved {saved_count} new posts to database")

        except Exception as e:
            logger.error(f"Error saving posts to database: {e}")

        return saved_count

    def run_ingestion(self, limit: Optional[int] = None) -> Dict[str, any]:
        """Run complete ingestion pipeline."""
        if not settings.ENABLE_SOCIAL_SIGNALS:
            logger.info("Social signals disabled, skipping ingestion")
            return {"status": "disabled"}

        logger.info("Starting social signals ingestion pipeline")
        start_time = datetime.utcnow()

        # Get active fixtures
        fixtures = self.get_active_fixtures()
        if not fixtures:
            logger.warning("No active fixtures found, skipping ingestion")
            return {"status": "no_fixtures"}

        # Extract team names
        team_names = self.extract_team_names_from_fixtures(fixtures)
        logger.info(f"Monitoring {len(team_names)} teams: {team_names[:5]}...")

        # Scrape all sources
        max_per_source = limit or 50
        all_posts = self.scrape_all_sources(team_names, max_per_source)

        if not all_posts:
            logger.warning("No posts scraped")
            return {"status": "no_posts"}

        # Link posts to fixtures
        linked_posts = batch_link_posts(all_posts, fixtures)
        linked_count = sum(1 for p in linked_posts if p.get("match_id"))

        # Save to database
        saved_count = self.save_posts_to_db(linked_posts)

        # Aggregate sentiment
        aggregated_count = aggregate_all_matches(fixtures)

        # Calculate duration
        duration = (datetime.utcnow() - start_time).total_seconds()

        stats = {
            "status": "completed",
            "duration_seconds": round(duration, 2),
            "fixtures_count": len(fixtures),
            "teams_monitored": len(team_names),
            "posts_scraped": len(all_posts),
            "posts_linked": linked_count,
            "posts_saved": saved_count,
            "matches_aggregated": aggregated_count,
        }

        logger.info(f"Ingestion completed: {stats}")
        return stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Social signals ingestion")
    parser.add_argument("--sandbox", action="store_true", help="Use sandbox mode with mock data")
    parser.add_argument("--limit", type=int, help="Limit posts per source (for testing)")
    
    args = parser.parse_args()
    
    ingestor = SocialIngestor(sandbox_mode=args.sandbox)
    stats = ingestor.run_ingestion(limit=args.limit)
    
    print(f"Ingestion stats: {stats}")


if __name__ == "__main__":
    main()
