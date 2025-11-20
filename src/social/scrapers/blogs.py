"""Blog and RSS feed scraper."""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from src.logging_config import get_logger

logger = get_logger(__name__)


class BlogScraper:
    """Blog and RSS feed scraper with robots.txt respect."""

    def __init__(self):
        """Initialize blog scraper."""
        self.robot_parsers = {}  # Cache robots.txt parsers
        self.last_request_time = {}  # Rate limiting per domain

    def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt.

        Args:
            url: URL to check

        Returns:
            True if allowed, False otherwise
        """
        try:
            parsed = urlparse(url)
            domain = f"{parsed.scheme}://{parsed.netloc}"

            # Get or create robot parser for this domain
            if domain not in self.robot_parsers:
                rp = RobotFileParser()
                rp.set_url(f"{domain}/robots.txt")
                try:
                    rp.read()
                    self.robot_parsers[domain] = rp
                except Exception as e:
                    logger.debug(f"Could not read robots.txt for {domain}: {e}")
                    # If robots.txt not available, assume allowed
                    return True

            rp = self.robot_parsers[domain]
            user_agent = settings.REDDIT_USER_AGENT  # Reuse user agent
            return rp.can_fetch(user_agent, url)

        except Exception as e:
            logger.warning(f"Error checking robots.txt: {e}")
            return True  # Fail open

    def _rate_limit(self, domain: str, delay_seconds: float = 1.0):
        """Rate limit requests per domain.

        Args:
            domain: Domain to rate limit
            delay_seconds: Minimum seconds between requests
        """
        now = time.time()
        last_request = self.last_request_time.get(domain, 0)
        time_since_last = now - last_request

        if time_since_last < delay_seconds:
            sleep_time = delay_seconds - time_since_last
            logger.debug(f"Rate limiting {domain}: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time[domain] = time.time()

    def scrape_rss_feed(self, feed_url: str, max_entries: int = 50) -> List[Dict]:
        """Scrape RSS feed.

        Args:
            feed_url: RSS feed URL
            max_entries: Maximum entries to return

        Returns:
            List of entry dicts with keys: id, text, author, created_at, url
        """
        # Check robots.txt
        if not self._check_robots_txt(feed_url):
            logger.warning(f"Blocked by robots.txt: {feed_url}")
            return []

        try:
            import feedparser

            # Rate limit
            domain = urlparse(feed_url).netloc
            self._rate_limit(domain)

            # Parse feed
            feed = feedparser.parse(feed_url)

            entries = []
            for entry in feed.entries[:max_entries]:
                # Extract text
                text = entry.get("title", "")
                if entry.get("summary"):
                    text += f"\n{entry['summary']}"

                # Parse date
                created_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    created_at = datetime(*entry.published_parsed[:6]).isoformat() + "Z"
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    created_at = datetime(*entry.updated_parsed[:6]).isoformat() + "Z"
                else:
                    created_at = datetime.utcnow().isoformat() + "Z"

                entries.append({
                    "id": entry.get("id", entry.get("link", "")),
                    "text": text,
                    "author": entry.get("author", "unknown"),
                    "created_at": created_at,
                    "url": entry.get("link", ""),
                })

            logger.info(f"Scraped {len(entries)} entries from RSS feed: {feed_url}")
            return entries

        except ImportError:
            logger.error("feedparser not installed. Install with: pip install feedparser")
            return []
        except Exception as e:
            logger.error(f"RSS scraping error for {feed_url}: {e}")
            return []

    def scrape_blog_page(self, url: str) -> Optional[Dict]:
        """Scrape a single blog page.

        Args:
            url: Blog page URL

        Returns:
            Dict with keys: id, text, author, created_at, url
        """
        # Check robots.txt
        if not self._check_robots_txt(url):
            logger.warning(f"Blocked by robots.txt: {url}")
            return None

        try:
            import requests
            from bs4 import BeautifulSoup

            # Rate limit
            domain = urlparse(url).netloc
            self._rate_limit(domain)

            # Fetch page
            response = requests.get(url, timeout=10, headers={"User-Agent": settings.REDDIT_USER_AGENT})
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, "lxml")

            # Extract article content (common patterns)
            article = soup.find("article") or soup.find("div", class_="post-content")
            if article:
                text = article.get_text(separator="\n", strip=True)
            else:
                # Fallback: get all paragraphs
                paragraphs = soup.find_all("p")
                text = "\n".join(p.get_text(strip=True) for p in paragraphs)

            # Extract author
            author_tag = soup.find("meta", {"name": "author"}) or soup.find("span", class_="author")
            author = author_tag.get("content") if author_tag and author_tag.get("content") else "unknown"

            # Extract date
            date_tag = soup.find("time") or soup.find("meta", {"property": "article:published_time"})
            if date_tag:
                created_at = date_tag.get("datetime") or date_tag.get("content") or datetime.utcnow().isoformat() + "Z"
            else:
                created_at = datetime.utcnow().isoformat() + "Z"

            return {
                "id": url,
                "text": text[:5000],  # Limit text length
                "author": author,
                "created_at": created_at,
                "url": url,
            }

        except ImportError:
            logger.error("beautifulsoup4 or lxml not installed. Install with: pip install beautifulsoup4 lxml")
            return None
        except Exception as e:
            logger.error(f"Blog scraping error for {url}: {e}")
            return None


# Popular football RSS feeds
FOOTBALL_RSS_FEEDS = [
    "https://www.bbc.co.uk/sport/football/rss.xml",
    "https://www.theguardian.com/football/rss",
    "https://www.espn.com/espn/rss/soccer/news",
    "https://www.goal.com/feeds/en/news",
]


def scrape_football_blogs(max_entries_per_feed: int = 20) -> List[Dict]:
    """Scrape multiple football RSS feeds.

    Args:
        max_entries_per_feed: Maximum entries per feed

    Returns:
        List of blog entry dicts
    """
    scraper = BlogScraper()
    all_entries = []

    for feed_url in FOOTBALL_RSS_FEEDS:
        try:
            entries = scraper.scrape_rss_feed(feed_url, max_entries_per_feed)
            all_entries.extend(entries)
        except Exception as e:
            logger.error(f"Error scraping {feed_url}: {e}")
            continue

    logger.info(f"Scraped {len(all_entries)} total blog entries from {len(FOOTBALL_RSS_FEEDS)} feeds")
    return all_entries
