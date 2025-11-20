"""Social signals API service layer."""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.config import settings
from src.logging_config import get_logger
from src.social.aggregator import get_match_sentiment
from src.social.arbitrage import detect_arbitrage
from src.social.models import SocialPost, SocialSentiment, SuggestedBet, SentimentAggregate
from src.db import handle_db_errors
from src.data_fetcher import DataFetcher

logger = get_logger(__name__)


def generate_betting_suggestions(
    min_confidence: float = 0.5, limit: int = 20
) -> List[Dict]:
    """Generate ML-powered betting suggestions based on sentiment and odds.

    Args:
        min_confidence: Minimum confidence threshold
        limit: Maximum suggestions to return

    Returns:
        List of suggestion dicts with ML predictions
    """
    suggestions = []

    try:
        # Import ML predictor
        from src.social.ml_predictor import get_predictor
        predictor = get_predictor()
        
        # Query suggested bets from database
        with handle_db_errors() as session:
            query = (
                session.query(SuggestedBet, SentimentAggregate)
                .outerjoin(SentimentAggregate, SuggestedBet.match_id == SentimentAggregate.match_id)
                .order_by(SuggestedBet.created_at.desc())
                .limit(limit * 2)  # Get more to filter by ML confidence
            )
            
            for bet, aggregate in query.all():
                # Extract data
                source_data = bet.source_json or {}
                home_team = source_data.get("home_team", source_data.get("home", "Unknown"))
                away_team = source_data.get("away_team", source_data.get("away", "Unknown"))
                
                # Prepare data for ML prediction
                match_data = {
                    'sentiment_score': bet.sentiment_score or 0.0,
                    'positive_pct': aggregate.positive_pct if aggregate else 33.0,
                    'negative_pct': aggregate.negative_pct if aggregate else 33.0,
                    'neutral_pct': aggregate.neutral_pct if aggregate else 34.0,
                    'sample_count': aggregate.sample_count if aggregate else 0,
                    'home_odds': bet.suggested_odds if bet.suggested_selection == 'home' else 2.0,
                    'away_odds': bet.suggested_odds if bet.suggested_selection == 'away' else 2.0,
                    'draw_odds': bet.suggested_odds if bet.suggested_selection == 'draw' else 3.0,
                }
                
                # Get ML prediction
                ml_prediction = predictor.predict(match_data)
                ml_confidence = ml_prediction['confidence']
                ml_outcome = ml_prediction['predicted_outcome']
                
                # Only include if ML confidence meets threshold
                if ml_confidence < min_confidence:
                    continue
                
                # Use ML prediction instead of rule-based
                suggestion = {
                    "match_id": bet.match_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "commence_time": bet.expires_at.isoformat() + "Z" if bet.expires_at else None,
                    "suggested_selection": ml_outcome,  # ML prediction
                    "suggested_odds": bet.suggested_odds,
                    "sentiment_score": bet.sentiment_score or 0.0,
                    "confidence": round(ml_confidence, 2),  # ML confidence
                    "ml_probabilities": ml_prediction['probabilities'],
                    "sample_count": match_data['sample_count'],
                    "reason": f"ML model ({ml_prediction['model']}) predicts {ml_outcome} with {ml_confidence:.0%} confidence. {bet.reason or ''}",
                    "created_at": bet.created_at.isoformat() + "Z" if bet.created_at else None,
                    "ml_powered": True,
                }
                suggestions.append(suggestion)
                
                if len(suggestions) >= limit:
                    break
        
        logger.info(f"Generated {len(suggestions)} ML-powered betting suggestions")
        return suggestions

    except Exception as e:
        logger.error(f"Error generating ML betting suggestions: {e}")
        # Fallback to database query without ML
        return _generate_suggestions_fallback(min_confidence, limit)


def _generate_suggestions_fallback(min_confidence: float, limit: int) -> List[Dict]:
    """Fallback to non-ML suggestions if ML fails."""
    suggestions = []
    try:
        with handle_db_errors() as session:
            query = (
                session.query(SuggestedBet)
                .filter(SuggestedBet.confidence >= min_confidence)
                .order_by(SuggestedBet.confidence.desc())
                .limit(limit)
            )
            
            for bet in query.all():
                source_data = bet.source_json or {}
                suggestion = {
                    "match_id": bet.match_id,
                    "home_team": source_data.get("home_team", "Unknown"),
                    "away_team": source_data.get("away_team", "Unknown"),
                    "commence_time": bet.expires_at.isoformat() + "Z" if bet.expires_at else None,
                    "suggested_selection": bet.suggested_selection,
                    "suggested_odds": bet.suggested_odds,
                    "sentiment_score": bet.sentiment_score or 0.0,
                    "confidence": round(bet.confidence, 2),
                    "sample_count": source_data.get("sample_count", 0),
                    "reason": bet.reason or "Rule-based prediction",
                    "created_at": bet.created_at.isoformat() + "Z" if bet.created_at else None,
                    "ml_powered": False,
                }
                suggestions.append(suggestion)
        
        logger.warning(f"Using fallback suggestions (ML unavailable): {len(suggestions)} suggestions")
        return suggestions
    except Exception as e:
        logger.error(f"Error in fallback suggestions: {e}")
        return []


def _generate_suggestion_reason(sentiment_score: float, selection: str, sample_count: int) -> str:
    """Generate human-readable reason for suggestion."""
    if sentiment_score > 0.4:
        sentiment_desc = "very positive"
    elif sentiment_score > 0.2:
        sentiment_desc = "positive"
    elif sentiment_score < -0.4:
        sentiment_desc = "very negative"
    elif sentiment_score < -0.2:
        sentiment_desc = "negative"
    else:
        sentiment_desc = "neutral"

    return f"{sentiment_desc.title()} sentiment ({sentiment_score:+.2f}) from {sample_count} posts suggests {selection} outcome"


def find_arbitrage_opportunities() -> List[Dict]:
    """Find arbitrage opportunities across bookmakers."""
    opportunities = []

    try:
        # Get odds data from multiple bookmakers
        data_fetcher = DataFetcher()
        odds_df = data_fetcher.get_odds()
        
        if odds_df.empty:
            return opportunities

        # Group by fixture
        for fixture_id in odds_df["fixture_id"].unique():
            fixture_odds = odds_df[odds_df["fixture_id"] == fixture_id]
            
            # Convert to format expected by arbitrage detector
            odds_data = []
            for _, row in fixture_odds.iterrows():
                odds_data.extend([
                    {
                        "bookmaker": row["bookmaker"],
                        "selection": "home",
                        "odds": row.get("home_odds", 0),
                    },
                    {
                        "bookmaker": row["bookmaker"],
                        "selection": "away",
                        "odds": row.get("away_odds", 0),
                    },
                ])
                
                if row.get("draw_odds"):
                    odds_data.append({
                        "bookmaker": row["bookmaker"],
                        "selection": "draw",
                        "odds": row["draw_odds"],
                    })

            # Detect arbitrage
            arbitrage_result = detect_arbitrage(odds_data)
            
            if arbitrage_result and arbitrage_result["is_arbitrage"]:
                # Get fixture details
                fixture_info = fixture_odds.iloc[0]
                
                opportunity = {
                    "match_id": fixture_id,
                    "home_team": fixture_info.get("home_team", "Unknown"),
                    "away_team": fixture_info.get("away_team", "Unknown"),
                    "profit_margin": arbitrage_result["profit_margin"],
                    "commission_adjusted_profit": arbitrage_result["commission_adjusted_profit"],
                    "total_stake": arbitrage_result["total_stake"],
                    "legs": arbitrage_result["legs"],
                    "commission_rate": arbitrage_result["commission_rate"],
                    "created_at": datetime.utcnow().isoformat() + "Z",
                }
                
                opportunities.append(opportunity)

        logger.info(f"Found {len(opportunities)} arbitrage opportunities")
        return opportunities

    except Exception as e:
        logger.error(f"Error finding arbitrage opportunities: {e}")
        return []


def get_match_details(match_id: str, include_posts: bool = True, max_posts: int = 10) -> Optional[Dict]:
    """Get detailed sentiment and posts for a match."""
    try:
        # Get sentiment aggregate
        sentiment_data = get_match_sentiment(match_id)
        if not sentiment_data:
            return None

        result = {
            "match_id": match_id,
            "aggregate": sentiment_data,
        }

        if include_posts:
            # Get recent posts
            with handle_db_errors() as session:
                posts_query = (
                    session.query(SocialPost, SocialSentiment)
                    .join(SocialSentiment, SocialPost.id == SocialSentiment.post_id)
                    .filter(
                        SocialPost.match_id == match_id,
                        SocialPost.match_confidence >= settings.MIN_MATCH_CONFIDENCE,
                    )
                    .order_by(SocialPost.created_at.desc())
                    .limit(max_posts)
                )

                posts = []
                for post, sentiment in posts_query.all():
                    posts.append({
                        "source": post.source,
                        "author": post.author,
                        "text": post.text[:200] + "..." if len(post.text) > 200 else post.text,
                        "sentiment_score": sentiment.sentiment_score,
                        "sentiment_label": sentiment.sentiment_label,
                        "created_at": post.created_at.isoformat() + "Z",
                        "url": post.url,
                    })

                result["recent_posts"] = posts

        return result

    except Exception as e:
        logger.error(f"Error getting match details for {match_id}: {e}")
        return None


def create_manual_bet(
    match_id: str,
    selection: str,
    stake: float,
    odds: float,
    is_virtual: bool = True,
    auto_execute: bool = False,
) -> Dict[str, Any]:
    """Create a manual bet record."""
    try:
        with handle_db_errors() as session:
            # Create suggested bet record
            suggested_bet = SuggestedBet(
                match_id=match_id,
                suggested_selection=selection,
                suggested_odds=odds,
                confidence=0.8,  # Manual bets get high confidence
                is_virtual=is_virtual,
                reason=f"Manual bet: {selection} @ {odds}",
                source_json={
                    "type": "manual",
                    "stake": stake,
                    "auto_execute": auto_execute,
                },
            )

            session.add(suggested_bet)
            session.commit()

            logger.info(
                f"Created {'virtual' if is_virtual else 'real'} manual bet: "
                f"{match_id} {selection} @ {odds} for ${stake}"
            )

            return {
                "bet_id": suggested_bet.id,
                "status": "created",
                "is_virtual": is_virtual,
                "message": f"{'Virtual' if is_virtual else 'Real'} bet created successfully",
            }

    except Exception as e:
        logger.error(f"Error creating manual bet: {e}")
        return {
            "bet_id": None,
            "status": "error",
            "message": str(e),
        }
