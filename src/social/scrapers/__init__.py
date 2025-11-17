"""Social media and blog scrapers."""
from typing import Protocol, List, Dict, Any


class ScraperProtocol(Protocol):
    """Protocol for social media scrapers."""
    
    def scrape(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Scrape posts matching query.
        
        Args:
            query: Search query (e.g., team names)
            limit: Maximum number of posts to return
        
        Returns:
            List of post dictionaries with keys:
                - external_id: str
                - author: str
                - text: str
                - created_at: datetime
                - url: str
                - metadata: dict
        """
        ...
    
    def is_available(self) -> bool:
        """Check if scraper is properly configured and available."""
        ...
