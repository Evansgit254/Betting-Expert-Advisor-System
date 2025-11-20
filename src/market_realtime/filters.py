"""Market fixture filtering and querying."""
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.logging_config import get_logger

logger = get_logger(__name__)

class MarketFilters:
    """Filter and query market fixtures."""
    
    def apply_filters(
        self,
        fixtures: List[Dict[str, Any]],
        leagues: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        bookmakers: Optional[List[str]] = None,
        min_ev: Optional[float] = None,
        max_ev: Optional[float] = None,
        min_confidence: Optional[float] = None,
        max_confidence: Optional[float] = None,
        min_arbitrage: Optional[float] = None,
        kickoff_start: Optional[datetime] = None,
        kickoff_end: Optional[datetime] = None,
        risk_categories: Optional[List[str]] = None,
        sort_by: str = "ev_score",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        filtered = fixtures.copy()
        
        if leagues:
            filtered = [f for f in filtered if f.get('league') in leagues]
        
        if countries:
            filtered = [f for f in filtered if f.get('country') in countries]
        
        if bookmakers:
            filtered = [f for f in filtered if any(b in f.get('bookmakers', []) for b in bookmakers)]
        
        if min_ev is not None:
            filtered = [f for f in filtered if f.get('ev_score', 0) >= min_ev]
        
        if max_ev is not None:
            filtered = [f for f in filtered if f.get('ev_score', 0) <= max_ev]
        
        if min_confidence is not None:
            filtered = [f for f in filtered if f.get('ml_confidence', 0) >= min_confidence]
        
        if max_confidence is not None:
            filtered = [f for f in filtered if f.get('ml_confidence', 0) <= max_confidence]
        
        if min_arbitrage is not None:
            filtered = [f for f in filtered if f.get('arbitrage_profit', 0) >= min_arbitrage]
        
        if kickoff_start:
            filtered = [f for f in filtered if f.get('commence_time', datetime.min) >= kickoff_start]
        
        if kickoff_end:
            filtered = [f for f in filtered if f.get('commence_time', datetime.max) <= kickoff_end]
        
        if risk_categories:
            filtered = [f for f in filtered if f.get('risk_category') in risk_categories]
        
        filtered = self._sort_fixtures(filtered, sort_by)
        
        logger.info(f"Filtered {len(fixtures)} fixtures to {len(filtered[:limit])}")
        return filtered[:limit]
    
    def _sort_fixtures(self, fixtures: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
        sort_keys = {
            'ev_score': lambda f: f.get('ev_score', 0),
            'confidence': lambda f: f.get('ml_confidence', 0),
            'volatility': lambda f: f.get('volatility_index', 0),
            'arbitrage': lambda f: f.get('arbitrage_profit', 0),
            'kickoff': lambda f: f.get('commence_time', datetime.max)
        }
        
        key_func = sort_keys.get(sort_by, sort_keys['ev_score'])
        reverse = sort_by != 'kickoff'
        
        return sorted(fixtures, key=key_func, reverse=reverse)
