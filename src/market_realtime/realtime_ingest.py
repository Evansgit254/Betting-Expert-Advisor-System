"""Real-time market data ingestion from all bookmaker APIs."""
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import redis

from src.logging_config import get_logger
from src.data_fetcher import DataFetcher
from src.adapters.theodds_api import TheOddsAPIAdapter
from src.config import settings
from src.social.ml_predictor import get_predictor
from src.social.aggregator import get_match_sentiment
from src.arbitrage_detector import ArbitrageDetector

logger = get_logger(__name__)

# Simple Redis cache helpers
def cache_get(key: str) -> Optional[Any]:
    """Get value from Redis cache."""
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, decode_responses=True)
        value = r.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.warning(f"Cache get error: {e}")
        return None

def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """Set value in Redis cache with TTL."""
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, decode_responses=True)
        r.setex(key, ttl, json.dumps(value))
    except Exception as e:
        logger.warning(f"Cache set error: {e}")


class RealtimeMarketIngestor:
    """Ingests live market data from all configured bookmaker APIs."""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.ml_predictor = get_predictor()
        self.arb_detector = ArbitrageDetector()
        
        # Supported leagues
        self.leagues = [
            'soccer_epl',
            'soccer_spain_la_liga',
            'soccer_germany_bundesliga',
            'soccer_italy_serie_a',
            'soccer_france_ligue_one',
            'soccer_uefa_champs_league',
            'soccer_uefa_europa_league',
        ]
    
    def fetch_live_fixtures(self, leagues: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch live fixtures from all bookmakers.
        
        Args:
            leagues: Optional list of leagues to filter
            
        Returns:
            List of fixture dictionaries with live odds
        """
        target_leagues = leagues or self.leagues
        
        # Check cache first
        cache_key = f"live_fixtures:{','.join(sorted(target_leagues))}"
        cached = cache_get(cache_key)
        if cached:
            logger.info(f"Returning {len(cached)} cached live fixtures")
            return cached
        
        fixtures = []
        
        # Fetch from TheOddsAPI
        if settings.THEODDS_API_KEY:
            try:
                adapter = TheOddsAPIAdapter(api_key=settings.THEODDS_API_KEY)
                
                for league in target_leagues:
                    try:
                        df = adapter.get_fixtures(sport=league)
                        if not df.empty:
                            league_fixtures = df.to_dict('records')
                            for fixture in league_fixtures:
                                fixture['league'] = league
                                fixture['source'] = 'theodds'
                            fixtures.extend(league_fixtures)
                            logger.info(f"Fetched {len(league_fixtures)} fixtures from {league}")
                    except Exception as e:
                        logger.warning(f"Error fetching {league}: {e}")
                        
            except Exception as e:
                logger.error(f"Error initializing TheOddsAPI: {e}")
        
        # Cache for 2 minutes
        if fixtures:
            cache_set(cache_key, fixtures, ttl=120)
        
        logger.info(f"Fetched {len(fixtures)} total live fixtures")
        return fixtures
    
    def enrich_with_ml_predictions(self, fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich fixtures with ML predictions.
        
        Args:
            fixtures: List of fixture dictionaries
            
        Returns:
            Enriched fixtures with ML predictions
        """
        enriched = []
        
        for fixture in fixtures:
            try:
                # Extract odds
                home_odds = fixture.get('home_odds', 2.0)
                away_odds = fixture.get('away_odds', 2.0)
                draw_odds = fixture.get('draw_odds', 3.0)
                
                # Get sentiment if available
                sentiment = get_match_sentiment(fixture.get('id', ''))
                sentiment_score = sentiment.get('aggregate_score', 0.0) if sentiment else 0.0
                
                # Prepare ML input
                ml_input = {
                    'sentiment_score': sentiment_score,
                    'positive_pct': sentiment.get('positive_pct', 33.0) if sentiment else 33.0,
                    'negative_pct': sentiment.get('negative_pct', 33.0) if sentiment else 33.0,
                    'neutral_pct': sentiment.get('neutral_pct', 34.0) if sentiment else 34.0,
                    'sample_count': sentiment.get('sample_count', 0) if sentiment else 0,
                    'home_odds': home_odds,
                    'away_odds': away_odds,
                    'draw_odds': draw_odds,
                }
                
                # Get ML prediction
                prediction = self.ml_predictor.predict(ml_input)
                
                # Add ML data to fixture
                fixture['ml_home_prob'] = prediction['probabilities'].get('home', 0.33)
                fixture['ml_away_prob'] = prediction['probabilities'].get('away', 0.33)
                fixture['ml_draw_prob'] = prediction['probabilities'].get('draw', 0.34)
                fixture['ml_confidence'] = prediction['confidence']
                fixture['predicted_outcome'] = prediction['predicted_outcome']
                
                # Calculate EV
                predicted_prob = prediction['probabilities'][prediction['predicted_outcome']]
                if prediction['predicted_outcome'] == 'home':
                    odds = home_odds
                elif prediction['predicted_outcome'] == 'away':
                    odds = away_odds
                else:
                    odds = draw_odds
                
                fixture['ev_score'] = (predicted_prob * odds) - 1
                fixture['sentiment_score'] = sentiment_score
                fixture['sentiment_sample_count'] = sentiment.get('sample_count', 0) if sentiment else 0
                
                enriched.append(fixture)
                
            except Exception as e:
                logger.error(f"Error enriching fixture {fixture.get('id')}: {e}")
                continue
        
        logger.info(f"Enriched {len(enriched)} fixtures with ML predictions")
        return enriched
    
    def detect_arbitrage(self, fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect arbitrage opportunities in fixtures.
        
        Args:
            fixtures: List of enriched fixtures
            
        Returns:
            Fixtures with arbitrage data
        """
        for fixture in fixtures:
            try:
                # Check for arbitrage
                home_odds = fixture.get('home_odds', 2.0)
                away_odds = fixture.get('away_odds', 2.0)
                draw_odds = fixture.get('draw_odds', 3.0)
                
                # Calculate arbitrage
                implied_prob = (1/home_odds) + (1/away_odds) + (1/draw_odds if draw_odds else 0)
                
                if implied_prob < 1.0:
                    fixture['arbitrage_opportunity'] = True
                    fixture['arbitrage_profit'] = (1.0 - implied_prob) * 100
                else:
                    fixture['arbitrage_opportunity'] = False
                    fixture['arbitrage_profit'] = 0.0
                    
            except Exception as e:
                logger.error(f"Error detecting arbitrage for {fixture.get('id')}: {e}")
                fixture['arbitrage_opportunity'] = False
                fixture['arbitrage_profit'] = 0.0
        
        return fixtures
    
    def calculate_risk_metrics(self, fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculate risk metrics for fixtures.
        
        Args:
            fixtures: List of enriched fixtures
            
        Returns:
            Fixtures with risk metrics
        """
        for fixture in fixtures:
            try:
                confidence = fixture.get('ml_confidence', 0.5)
                ev_score = fixture.get('ev_score', 0.0)
                
                # Calculate volatility (inverse of confidence)
                fixture['volatility_index'] = 1.0 - confidence
                
                # Determine risk category
                if confidence >= 0.8 and ev_score >= 0.1:
                    fixture['risk_category'] = 'low'
                elif confidence >= 0.6 and ev_score >= 0.0:
                    fixture['risk_category'] = 'medium'
                else:
                    fixture['risk_category'] = 'high'
                
                # Odds drift (placeholder - would need historical data)
                fixture['odds_drift'] = 0.0
                
                # Sharp money indicator (placeholder)
                fixture['sharp_money_indicator'] = ev_score > 0.15
                
                # Market efficiency
                fixture['market_efficiency'] = min(confidence, 1.0)
                
            except Exception as e:
                logger.error(f"Error calculating risk for {fixture.get('id')}: {e}")
                fixture['risk_category'] = 'high'
                fixture['volatility_index'] = 1.0
        
        return fixtures
    
    def ingest_realtime_market(self, leagues: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Full ingestion pipeline for real-time market data.
        
        Args:
            leagues: Optional list of leagues to filter
            
        Returns:
            Fully enriched market fixtures
        """
        logger.info("Starting real-time market ingestion")
        
        # Fetch live fixtures
        fixtures = self.fetch_live_fixtures(leagues)
        
        if not fixtures:
            logger.warning("No fixtures fetched")
            return []
        
        # Enrich with ML
        fixtures = self.enrich_with_ml_predictions(fixtures)
        
        # Detect arbitrage
        fixtures = self.detect_arbitrage(fixtures)
        
        # Calculate risk
        fixtures = self.calculate_risk_metrics(fixtures)
        
        logger.info(f"Completed ingestion of {len(fixtures)} fixtures")
        return fixtures
