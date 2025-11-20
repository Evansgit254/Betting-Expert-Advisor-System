"""Real-time market alerts and ML-powered suggestions module."""
from .realtime_ingest import RealtimeMarketIngestor
from .headline_generator import HeadlineGenerator
from .suggestion_engine import SuggestionEngine
from .filters import MarketFilters

__all__ = [
    'RealtimeMarketIngestor',
    'HeadlineGenerator',
    'SuggestionEngine',
    'MarketFilters',
]
