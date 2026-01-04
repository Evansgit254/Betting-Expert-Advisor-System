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

from src.adapters.theodds_api import TheOddsAPIAdapter
from src.arbitrage_detector import ArbitrageDetector
from src.config import settings
from src.data_fetcher import DataFetcher
from src.feature import build_features
from src.logging_config import get_logger
from src.social.ml_predictor import get_predictor
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
        if settings.MODE == "LIVE":
            logger.info("Initializing with real TheOddsAPIAdapter")
            self.data_fetcher = DataFetcher(source=TheOddsAPIAdapter())
        else:
            self.data_fetcher = DataFetcher()
            
        self.predictor = get_predictor()
        self.arbitrage_detector = ArbitrageDetector()
        
        # Verify model
        if self.predictor.model is not None:
            self.model_loaded = True
            logger.info("Social ML model loaded successfully")
        else:
            logger.warning("Social ML model not found - will use fallback predictions")
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
            # 1. Fetch fixtures and odds for all active sports
            if not start_date:
                start_date = datetime.now(timezone.utc)
            if not end_date:
                end_date = start_date + pd.Timedelta(hours=36)
            
            all_fixtures = []
            all_odds = []
            
            # Extract sports from settings (handle both list and comma-sep string)
            active_sports = settings.ACTIVE_SPORTS
            if isinstance(active_sports, str):
                import json
                try:
                    active_sports = json.loads(active_sports)
                except:
                    active_sports = [s.strip() for s in active_sports.split(',') if s.strip()]
            
            use_scraper = False
            for sport in active_sports:
                logger.info(f"Fetching fixtures for {sport}")
                try:
                    # In LIVE mode with TheOddsAPIAdapter, we need to pass the sport
                    if settings.MODE == "LIVE" and hasattr(self.data_fetcher.source, 'fetch_fixtures'):
                        try:
                            sport_fixtures = self.data_fetcher.source.fetch_fixtures(
                                sport=sport, 
                                start_date=start_date, 
                                end_date=end_date
                            )
                        except Exception as e:
                            # Detect quota exhaustion or 401 Unauthorized
                            if "401" in str(e) or "quota" in str(e).lower():
                                logger.warning(f"Quota hit for {sport}, switching to scraper fallback...")
                                use_scraper = True
                                break
                            raise e
                            
                        if sport_fixtures is not None and not (isinstance(sport_fixtures, pd.DataFrame) and sport_fixtures.empty):
                            fixtures_df = pd.DataFrame(sport_fixtures)
                            all_fixtures.append(fixtures_df)
                            
                            # Also fetch odds for these fixtures
                            market_ids = fixtures_df['market_id'].tolist()
                            sport_odds = self.data_fetcher.source.fetch_odds(
                                sport=sport,
                                market_ids=market_ids
                            )
                            if sport_odds is not None and not (isinstance(sport_odds, pd.DataFrame) and sport_odds.empty):
                                all_odds.append(pd.DataFrame(sport_odds))
                    else:
                        # Non-LIVE mode (e.g., DRY_RUN) or generic source
                        fixtures_df = self.data_fetcher.get_fixtures(start_date=start_date, end_date=end_date)
                        if not fixtures_df.empty:
                            all_fixtures.append(fixtures_df)
                            odds_df = self.data_fetcher.get_odds(fixtures_df['market_id'].tolist())
                            if not odds_df.empty:
                                all_odds.append(odds_df)
                except Exception as e:
                    logger.warning(f"Failed to fetch data for {sport}: {e}")
                    continue

            # Layer 4: Final Resilience Fallback - Web Scraping
            # Trigger if we found nothing OR if we specifically caught a quota error
            found_nothing = not all_fixtures or all(df.empty for df in all_fixtures)
            
            if use_scraper or (found_nothing and settings.MODE == "LIVE"):
                logger.info("RETRYING WITH REAL-DATA SCRAPER FALLBACK")
                self.data_fetcher.switch_to_scraper()
                scraped_fixtures = self.data_fetcher.get_fixtures(start_date, end_date)
                if not scraped_fixtures.empty:
                    all_fixtures = [scraped_fixtures]
                    market_ids = scraped_fixtures['market_id'].tolist()
                    scraped_odds = self.data_fetcher.get_odds(market_ids)
                    if not scraped_odds.empty:
                        all_odds = [scraped_odds]
            
            if not all_fixtures or all(df.empty for df in all_fixtures):
                logger.warning("No fixtures available for any sport after all fallback attempts")
                return self._empty_response(min_ev, min_sentiment, leagues)
            
            fixtures_df = pd.concat([df for df in all_fixtures if not df.empty], ignore_index=True)
            
            if not all_odds or all(df.empty for df in all_odds):
                logger.warning("No odds available for any sport after all fallback attempts")
                return self._empty_response(min_ev, min_sentiment, leagues)
            
            odds_df = pd.concat([df for df in all_odds if not df.empty], ignore_index=True)
            
            # 2. Build features
            features_df = build_features(fixtures_df, odds_df)
            
            # 3. Get ML predictions and calculate best outcome
            def enrich_best_prediction(row):
                market_id = row.get('market_id')
                fixture_dict = row.to_dict()
                sentiment = self._get_sentiment(market_id, fixture_dict)
                
                match_data = {
                    'sentiment_score': float(sentiment.get('score', 0.0)),
                    'positive_pct': float(sentiment.get('positive_pct', 55.0)),
                    'negative_pct': float(sentiment.get('negative_pct', 15.0)),
                    'neutral_pct': float(sentiment.get('neutral_pct', 30.0)),
                    'sample_count': max(int(sentiment.get('post_count', 0)), 10), # Baseline for stability
                    'home_odds': float(row.get('home_odds', 2.0)),
                    'away_odds': float(row.get('away_odds', 2.0)),
                    'draw_odds': float(row.get('draw_odds', 3.0)),
                }
                
                # Double check for NaNs and replace with defaults
                for k, v in match_data.items():
                    if pd.isna(v):
                        if 'odds' in k: match_data[k] = 2.0
                        elif 'pct' in k: match_data[k] = 33.0
                        else: match_data[k] = 0.0

                pred = self.predictor.predict(match_data)
                
                # Map prediction to selection and odds
                selection = pred['predicted_outcome']
                confidence = pred['confidence']
                odds_key = f"{selection}_odds"
                odds = float(row.get(odds_key, 2.0))
                
                # Calculate EV for the predicted outcome
                ev = (confidence * odds) - 1
                
                return pd.Series({
                    'ml_selection': selection,
                    'ml_probability': confidence,
                    'ml_odds': odds,
                    'ml_ev': ev,
                    'ml_confidence': confidence
                })

            prediction_results = features_df.apply(enrich_best_prediction, axis=1)
            features_df = pd.concat([features_df, prediction_results], axis=1)
            
            # 4. Find value bets (using the best ML outcome)
            # We filter by ml_ev directly since we pre-calculated it
            value_bets_mask = (features_df['ml_ev'] >= (min_ev if min_ev != 0.01 else -0.05))
            value_bets_df = features_df[value_bets_mask].copy()
            
            # Sort by EV
            value_bets_df = value_bets_df.sort_values('ml_ev', ascending=False)
            
            if value_bets_df.empty:
                logger.info("No value bets found with current filters")
                # Debug logging of top EV if empty
                if not features_df.empty:
                    top_ev = features_df['ml_ev'].max()
                    logger.warning(f"Best available EV was {top_ev:.4f}")
                return self._empty_response(min_ev, min_sentiment, leagues)
            
            # 5. Enrich with sentiment and arbitrage
            suggestions = []
            for _, row in value_bets_df.head(max_suggestions).iterrows():
                # Convert row to a format find_value_bets uses or build manually
                bet = {
                    'market_id': row['market_id'],
                    'selection': row['ml_selection'],
                    'odds': row['ml_odds'],
                    'p': row['ml_probability'],
                    'ev': row['ml_ev'],
                    'home': row['home'],
                    'away': row['away'],
                    'league': row['league'],
                    'stake': 0.0 # Will be calculated in _build_suggestion or risk module
                }
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
        """Build a single suggestion with all enrichments."""
        market_id = bet['market_id']
        
        # Get fixture details
        fixture = fixtures_df[fixtures_df['market_id'] == market_id].iloc[0] if not fixtures_df.empty else {}
        
        # Base recommendation
        recommendation = {
            "selection": bet.get('selection', 'home'),
            "odds": bet.get('odds', 0.0),
            "ml_probability": bet.get('p', 0.0),
            "expected_value": bet.get('ev', 0.0),
            "kelly_stake": bet.get('stake', 0.0),
            "confidence": bet.get('p', 0.0)
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
            "kickoff": str(fixture.get('start', '')),
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
        """Calculate composite score for ranking suggestions."""
        # Base score: ML confidence × EV
        base_score = ml_probability * expected_value
        
        # Sentiment boost (limited to 15% influence)
        sentiment_boost = sentiment_score * self.sentiment_weight
        
        # Arbitrage boost
        arbitrage_boost = 0.0
        if has_arbitrage:
            arbitrage_boost = arbitrage_profit_margin * self.arbitrage_multiplier
        
        composite_score = base_score + sentiment_boost + arbitrage_boost
        
        return round(composite_score, 4)

    def _get_sentiment(self, market_id: str, fixture: Dict) -> Dict:
        """Get sentiment data for a fixture."""
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
                    "post_count": sentiment_data.get('sample_count', sentiment_data.get('post_count', 0)),
                    "positive_pct": sentiment_data.get('positive_pct', 0.0),
                    "negative_pct": sentiment_data.get('negative_pct', 0.0),
                    "neutral_pct": sentiment_data.get('neutral_pct', 0.0),
                    "sentiment_strength": self._classify_sentiment_strength(score)
                }
            else:
                return {
                    "score": 0.0,
                    "label": "neutral",
                    "post_count": 0,
                    "positive_pct": 0.0,
                    "negative_pct": 0.0,
                    "neutral_pct": 0.0,
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
        """Classify sentiment strength from score."""
        abs_score = abs(score)
        if abs_score >= 0.6: return "strong"
        elif abs_score >= 0.3: return "moderate"
        elif abs_score >= 0.1: return "weak"
        else: return "neutral"

    def _check_arbitrage(self, market_id: str, odds_df: pd.DataFrame) -> Optional[Dict]:
        """Check if arbitrage opportunity exists for market."""
        try:
            market_odds = odds_df[odds_df['market_id'] == market_id]
            if market_odds.empty: return None
            
            opportunities = self.arbitrage_detector.detect_opportunities(market_odds)
            if opportunities:
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
        """Return empty response structure."""
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
    """Get or create singleton market intelligence engine."""
    global _engine
    if _engine is None:
        _engine = MarketIntelligenceEngine()
    return _engine
