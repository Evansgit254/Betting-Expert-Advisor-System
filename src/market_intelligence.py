"""Market Intelligence Engine - Fuses ML, Sentiment, and Arbitrage.

This module provides unified market intelligence by combining:
- ML predictions (probability, confidence)
- Expected Value calculations
- Sentiment analysis scores
- Arbitrage opportunities

All suggestions are ranked by composite score and mathematically derived.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from src.arbitrage_detector import ArbitrageDetector
from src.config import settings
from src.data_fetcher import DataFetcher
from src.feature import build_features
from src.logging_config import get_logger
from src.ml_pipeline import MLPipeline
from src.risk import calculate_expected_value
from src.strategy import find_value_bets

logger = get_logger(__name__)

# Try to import sentiment module (graceful degradation if not available)
try:
    from src.social.sentiment import get_analyzer
    from src.social.aggregator import get_match_sentiment
    SENTIMENT_AVAILABLE = True
except ImportError:
    logger.warning("Sentiment modules not available - suggestions will not include sentiment")
    SENTIMENT_AVAILABLE = False


class MarketIntelligenceEngine:
    """Generate ranked market intelligence suggestions."""

    def __init__(self):
        """Initialize the market intelligence engine."""
        self.data_fetcher = DataFetcher()
        self.ml_pipeline = MLPipeline()
        self.arbitrage_detector = ArbitrageDetector()
        
        # Load ML model
        try:
            self.ml_pipeline.load()
            self.model_loaded = True
            logger.info("ML model loaded successfully")
        except FileNotFoundError:
            logger.warning("ML model not found - will use odds-implied probabilities as fallback")
            self.model_loaded = False
        
        # Initialize sentiment analyzer if available
        if SENTIMENT_AVAILABLE:
            try:
                self.sentiment_analyzer = get_analyzer()
                logger.info("Sentiment analyzer initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize sentiment analyzer: {e}")
                self.sentiment_analyzer = None
        else:
            self.sentiment_analyzer = None
        
        # Configuration
        self.sentiment_weight = getattr(settings, 'COMPOSITE_SCORE_SENTIMENT_WEIGHT', 0.15)
        self.arbitrage_multiplier = getattr(settings, 'COMPOSITE_SCORE_ARBITRAGE_MULTIPLIER', 10.0)
        
        logger.info(f"MarketIntelligenceEngine initialized (sentiment_weight={self.sentiment_weight}, arbitrage_multiplier={self.arbitrage_multiplier})")

    def generate_suggestions(
        self,
        max_suggestions: int = 10,
        min_ev: float = 0.01,
        min_sentiment: float = -1.0,
        leagues: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate ranked market intelligence suggestions.
        
        Args:
            max_suggestions: Maximum number of suggestions to return
            min_ev: Minimum expected value threshold
            min_sentiment: Minimum sentiment score threshold
            leagues: List of league IDs to filter (None = all leagues)
            start_date: Filter fixtures starting from this date
            end_date: Filter fixtures up to this date
        
        Returns:
            Dict with:
                - headline: str
                - generated_at: ISO datetime
                - suggestions: List[Dict] sorted by composite_score
                - filters_applied: Dict
        """
        logger.info(f"Generating market intelligence suggestions (max={max_suggestions}, min_ev={min_ev})")
        
        try:
            # 1. Fetch fixtures and odds
            fixtures_df = self.data_fetcher.get_fixtures(start_date=start_date, end_date=end_date)
            
            if fixtures_df.empty:
                logger.warning("No fixtures available")
                return self._empty_response(min_ev, min_sentiment, leagues)
            
            market_ids = fixtures_df['market_id'].tolist()
            odds_df = self.data_fetcher.get_odds(market_ids=market_ids)
            
            if odds_df.empty:
                logger.warning("No odds available")
                return self._empty_response(min_ev, min_sentiment, leagues)
            
            # 2. Build features
            features_df = build_features(fixtures_df, odds_df)
            
            # 3. Get ML predictions
            if self.model_loaded:
                predictions = self.ml_pipeline.predict_proba(features_df)
                features_df['ml_probability'] = predictions
            else:
                # Fallback: Use implied probability from odds
                features_df['ml_probability'] = 1.0 / features_df.get('home_odds', 2.0)
            
            # 4. Find value bets
            value_bets = find_value_bets(
                features_df,
                proba_col='ml_probability',
                odds_col='home_odds',
                min_ev=min_ev
            )
            
            if not value_bets:
                logger.info("No value bets found with current filters")
                return self._empty_response(min_ev, min_sentiment, leagues)
            
            # 5. Enrich with sentiment and arbitrage
            suggestions = []
            for bet in value_bets:
                suggestion = self._build_suggestion(bet, fixtures_df, odds_df)
                
                # Apply filters
                if leagues and suggestion.get('league') not in leagues:
                    continue
                
                if suggestion.get('sentiment', {}).get('score', 0.0) < min_sentiment:
                    continue
                
                suggestions.append(suggestion)
            
            # 6. Sort by composite score (highest first)
            suggestions.sort(key=lambda x: x['composite_score'], reverse=True)
            
            # 7. Limit to max_suggestions
            suggestions = suggestions[:max_suggestions]
            
            # 8. Add rank
            for i, suggestion in enumerate(suggestions, start=1):
                suggestion['rank'] = i
            
            logger.info(f"Generated {len(suggestions)} suggestions")
            
            return {
                "headline": "🔥 Real-Time Market Highlights – Here Are Today's Top Suggested Fixtures Across All Leagues",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "suggestions": suggestions,
                "filters_applied": {
                    "min_ev": min_ev,
                    "min_sentiment": min_sentiment,
                    "leagues": leagues or "all"
                }
            }
        
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}", exc_info=True)
            return self._empty_response(min_ev, min_sentiment, leagues)

    def _build_suggestion(self, bet: Dict, fixtures_df: pd.DataFrame, odds_df: pd.DataFrame) -> Dict:
        """Build a single suggestion with all enrichments.
        
        Args:
            bet: Value bet dict from find_value_bets
            fixtures_df: Fixtures dataframe
            odds_df: Odds dataframe
        
        Returns:
            Enriched suggestion dict
        """
        market_id = bet['market_id']
        
        # Get fixture details
        fixture = fixtures_df[fixtures_df['market_id'] == market_id].iloc[0] if not fixtures_df.empty else {}
        
        # Base recommendation
        recommendation = {
            "selection": bet.get('selection', 'home'),
            "odds": bet.get('odds', 0.0),
            "ml_probability": bet.get('probability', 0.0),
            "expected_value": bet.get('ev', 0.0),
            "kelly_stake": bet.get('stake', 0.0),
            "confidence": bet.get('probability', 0.0)  # ML probability as confidence
        }
        
        # Get sentiment
        sentiment = self._get_sentiment(market_id, fixture)
        
        # Check for arbitrage
        arbitrage = self._check_arbitrage(market_id, odds_df)
        
        # Calculate composite score
        composite_score = self.calculate_composite_score(
            ml_probability=recommendation['ml_probability'],
            expected_value=recommendation['expected_value'],
            sentiment_score=sentiment.get('score', 0.0),
            has_arbitrage=arbitrage is not None,
            arbitrage_profit_margin=arbitrage.get('profit_margin', 0.0) if arbitrage else 0.0
        )
        
        # Build tags
        tags = []
        if recommendation['expected_value'] > 0.10:
            tags.append("HIGH_VALUE")
        if sentiment.get('label') == 'positive':
            tags.append("POSITIVE_SENTIMENT")
        if arbitrage:
            tags.append("ARBITRAGE")
        
        return {
            "market_id": market_id,
            "home": fixture.get('home', 'Unknown'),
            "away": fixture.get('away', 'Unknown'),
            "league": fixture.get('league', 'Unknown'),
            "kickoff": fixture.get('start_time', datetime.now(timezone.utc)).isoformat() if isinstance(fixture.get('start_time'), datetime) else str(fixture.get('start_time', '')),
            "recommendation": recommendation,
            "sentiment": sentiment,
            "arbitrage": arbitrage,
            "composite_score": composite_score,
            "tags": tags
        }

    def calculate_composite_score(
        self,
        ml_probability: float,
        expected_value: float,
        sentiment_score: float,
        has_arbitrage: bool,
        arbitrage_profit_margin: float = 0.0
    ) -> float:
        """Calculate composite score for ranking suggestions.
        
        Mathematical fusion formula:
        base_score = ml_probability × expected_value
        sentiment_boost = sentiment_score × sentiment_weight (0.15)
        arbitrage_boost = arbitrage_profit_margin × arbitrage_multiplier (10.0) if arbitrage
        
        composite_score = base_score + sentiment_boost + arbitrage_boost
        
        Args:
            ml_probability: ML predicted win probability (0-1)
            expected_value: Expected value per $1 stake
            sentiment_score: Sentiment score (-1 to 1)
            has_arbitrage: Whether arbitrage opportunity exists
            arbitrage_profit_margin: Arbitrage profit margin (0-1)
        
        Returns:
            Composite score (higher is better)
        """
        # Base score: ML confidence × EV
        base_score = ml_probability * expected_value
        
        # Sentiment boost (limited to 15% influence)
        sentiment_boost = sentiment_score * self.sentiment_weight
        
        # Arbitrage boost (ensures arbitrage opportunities rank highest)
        arbitrage_boost = 0.0
        if has_arbitrage:
            arbitrage_boost = arbitrage_profit_margin * self.arbitrage_multiplier
        
        composite_score = base_score + sentiment_boost + arbitrage_boost
        
        return round(composite_score, 4)

    def _get_sentiment(self, market_id: str, fixture: Dict) -> Dict:
        """Get sentiment data for a fixture.
        
        Args:
            market_id: Market ID
            fixture: Fixture dict with home/away teams
        
        Returns:
            Sentiment dict with score, label, post_count, sentiment_strength
        """
        if not SENTIMENT_AVAILABLE or not self.sentiment_analyzer:
            return {
                "score": 0.0,
                "label": "neutral",
                "post_count": 0,
                "sentiment_strength": "unknown"
            }
        
        try:
            # Try to get aggregated sentiment from DB
            sentiment_data = get_match_sentiment(market_id)
            
            if sentiment_data:
                score = sentiment_data.get('aggregate_score', 0.0)
                label = 'positive' if score > 0.2 else 'negative' if score < -0.2 else 'neutral'
                
                return {
                    "score": score,
                    "label": label,
                    "post_count": sentiment_data.get('post_count', 0),
                    "sentiment_strength": self._classify_sentiment_strength(score)
                }
            else:
                return {
                    "score": 0.0,
                    "label": "neutral",
                    "post_count": 0,
                    "sentiment_strength": "none"
                }
        
        except Exception as e:
            logger.warning(f"Error getting sentiment for {market_id}: {e}")
            return {
                "score": 0.0,
                "label": "neutral",
                "post_count": 0,
                "sentiment_strength": "error"
            }

    def _classify_sentiment_strength(self, score: float) -> str:
        """Classify sentiment strength from score.
        
        Args:
            score: Sentiment score (-1 to 1)
        
        Returns:
            Strength classification: strong, moderate, weak, neutral
        """
        abs_score = abs(score)
        if abs_score >= 0.6:
            return "strong"
        elif abs_score >= 0.3:
            return "moderate"
        elif abs_score >= 0.1:
            return "weak"
        else:
            return "neutral"

    def _check_arbitrage(self, market_id: str, odds_df: pd.DataFrame) -> Optional[Dict]:
        """Check if arbitrage opportunity exists for market.
        
        Args:
            market_id: Market ID
            odds_df: Odds dataframe
        
        Returns:
            Arbitrage dict if opportunity exists, else None
        """
        try:
            # Filter odds for this market
            market_odds = odds_df[odds_df['market_id'] == market_id]
            
            if market_odds.empty:
                return None
            
            # Detect arbitrage opportunities
            opportunities = self.arbitrage_detector.detect_opportunities(market_odds)
            
            if opportunities:
                # Return first opportunity for this market
                for opp in opportunities:
                    if opp['market_id'] == market_id:
                        return {
                            "profit_margin": opp['profit_margin'],
                            "guaranteed_profit": opp['guaranteed_profit'],
                            "total_stake": opp.get('total_stake', 1000.0),
                            "bookmakers": opp['bookmakers'],
                            "best_odds": opp['best_odds'],
                            "optimal_stakes": opp['optimal_stakes']
                        }
            
            return None
        
        except Exception as e:
            logger.warning(f"Error checking arbitrage for {market_id}: {e}")
            return None

    def _empty_response(self, min_ev: float, min_sentiment: float, leagues: Optional[List[str]]) -> Dict:
        """Return empty response structure.
        
        Args:
            min_ev: Minimum EV filter applied
            min_sentiment: Minimum sentiment filter applied
            leagues: Leagues filter applied
        
        Returns:
            Empty response dict
        """
        return {
            "headline": "🔥 Real-Time Market Highlights – Here Are Today's Top Suggested Fixtures Across All Leagues",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "suggestions": [],
            "filters_applied": {
                "min_ev": min_ev,
                "min_sentiment": min_sentiment,
                "leagues": leagues or "all"
            }
        }


# Singleton instance
_engine: Optional[MarketIntelligenceEngine] = None


def get_engine() -> MarketIntelligenceEngine:
    """Get or create singleton market intelligence engine.
    
    Returns:
        MarketIntelligenceEngine instance
    """
    global _engine
    if _engine is None:
        _engine = MarketIntelligenceEngine()
    return _engine
