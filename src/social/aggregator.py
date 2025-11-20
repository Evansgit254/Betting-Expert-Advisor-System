"""Sentiment aggregation per match."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import math

from src.config import settings
from src.logging_config import get_logger
from src.social.models import SentimentAggregate, SocialPost, SocialSentiment
from src.db import handle_db_errors

logger = get_logger(__name__)


def calculate_recency_weight(post_age_hours: float, decay_factor: float = 0.1) -> float:
    """Calculate recency weight for a post.

    Args:
        post_age_hours: Age of post in hours
        decay_factor: Exponential decay factor

    Returns:
        Weight between 0 and 1 (newer posts have higher weight)
    """
    return math.exp(-decay_factor * post_age_hours)


def calculate_author_influence(author: str, post_metrics: Optional[Dict] = None) -> float:
    """Calculate author influence score.

    Args:
        author: Author username
        post_metrics: Post metrics (likes, retweets, etc.)

    Returns:
        Influence score between 0.1 and 2.0
    """
    base_influence = 1.0

    # Boost for verified/popular accounts (simplified)
    if post_metrics:
        likes = post_metrics.get("like_count", 0)
        retweets = post_metrics.get("retweet_count", 0)
        score = post_metrics.get("score", 0)  # Reddit score

        # Simple influence calculation
        engagement = likes + (retweets * 2) + (score * 0.5)
        if engagement > 100:
            base_influence = 1.5
        elif engagement > 50:
            base_influence = 1.2
        elif engagement > 10:
            base_influence = 1.1

    return min(base_influence, 2.0)  # Cap at 2x


def aggregate_match_sentiment(
    match_id: str, window_hours: int = 24, max_posts: Optional[int] = None
) -> Optional[Dict]:
    """Aggregate sentiment for a specific match.

    Args:
        match_id: Match/fixture ID
        window_hours: Time window to consider (hours before now)
        max_posts: Maximum posts to consider (None = no limit)

    Returns:
        Dict with aggregated sentiment data or None if no data
    """
    try:
        with handle_db_errors() as session:
            # Calculate time window
            window_start = datetime.utcnow() - timedelta(hours=window_hours)

            # Query posts with sentiment for this match
            query = (
                session.query(SocialPost, SocialSentiment)
                .join(SocialSentiment, SocialPost.id == SocialSentiment.post_id)
                .filter(
                    SocialPost.match_id == match_id,
                    SocialPost.created_at >= window_start,
                    SocialPost.match_confidence >= settings.MIN_MATCH_CONFIDENCE,
                )
                .order_by(SocialPost.created_at.desc())
            )

            if max_posts:
                query = query.limit(max_posts)

            results = query.all()

            if not results:
                logger.debug(f"No sentiment data found for match {match_id}")
                return None

            # Calculate weighted sentiment
            total_weight = 0.0
            weighted_sentiment = 0.0
            sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}

            now = datetime.utcnow()

            for post, sentiment in results:
                # Calculate post age
                post_age = (now - post.created_at).total_seconds() / 3600  # Hours

                # Calculate weights
                recency_weight = calculate_recency_weight(post_age)
                author_influence = calculate_author_influence(
                    post.author, post.post_metadata.get("metrics") if post.post_metadata else None
                )
                match_confidence_weight = post.match_confidence

                # Combined weight
                weight = recency_weight * author_influence * match_confidence_weight

                # Add to weighted sentiment
                weighted_sentiment += sentiment.sentiment_score * weight
                total_weight += weight

                # Count sentiment labels
                sentiment_counts[sentiment.sentiment_label] += 1

            # Calculate final aggregated sentiment
            if total_weight > 0:
                aggregate_score = weighted_sentiment / total_weight
            else:
                aggregate_score = 0.0

            # Calculate percentages
            total_posts = len(results)
            positive_pct = (sentiment_counts["positive"] / total_posts) * 100
            negative_pct = (sentiment_counts["negative"] / total_posts) * 100
            neutral_pct = (sentiment_counts["neutral"] / total_posts) * 100

            result = {
                "match_id": match_id,
                "aggregate_score": round(aggregate_score, 3),
                "positive_pct": round(positive_pct, 1),
                "negative_pct": round(negative_pct, 1),
                "neutral_pct": round(neutral_pct, 1),
                "sample_count": total_posts,
                "window_start": window_start,
                "window_end": now,
            }

            logger.info(
                f"Aggregated sentiment for {match_id}: "
                f"score={aggregate_score:.3f}, n={total_posts}, "
                f"pos={positive_pct:.1f}%, neg={negative_pct:.1f}%"
            )

            return result

    except Exception as e:
        logger.error(f"Error aggregating sentiment for {match_id}: {e}")
        return None


def save_sentiment_aggregate(aggregate_data: Dict) -> bool:
    """Save sentiment aggregate to database."""
    try:
        with handle_db_errors() as session:
            # Check if aggregate already exists for this time window
            existing = (
                session.query(SentimentAggregate)
                .filter(
                    SentimentAggregate.match_id == aggregate_data["match_id"],
                    SentimentAggregate.window_start == aggregate_data["window_start"],
                    SentimentAggregate.window_end == aggregate_data["window_end"],
                )
                .first()
            )

            if existing:
                # Update existing
                existing.aggregate_score = aggregate_data["aggregate_score"]
                existing.positive_pct = aggregate_data["positive_pct"]
                existing.negative_pct = aggregate_data["negative_pct"]
                existing.neutral_pct = aggregate_data["neutral_pct"]
                existing.sample_count = aggregate_data["sample_count"]
                logger.debug(f"Updated sentiment aggregate for {aggregate_data['match_id']}")
            else:
                # Create new
                aggregate = SentimentAggregate(
                    match_id=aggregate_data["match_id"],
                    aggregate_score=aggregate_data["aggregate_score"],
                    positive_pct=aggregate_data["positive_pct"],
                    negative_pct=aggregate_data["negative_pct"],
                    neutral_pct=aggregate_data["neutral_pct"],
                    sample_count=aggregate_data["sample_count"],
                    window_start=aggregate_data["window_start"],
                    window_end=aggregate_data["window_end"],
                )
                session.add(aggregate)
                logger.debug(f"Created sentiment aggregate for {aggregate_data['match_id']}")

            session.commit()
            return True

    except Exception as e:
        logger.error(f"Error saving sentiment aggregate: {e}")
        return False


def aggregate_all_matches(fixtures: List[Dict], window_hours: int = 24) -> int:
    """Aggregate sentiment for all active matches."""
    processed = 0

    for fixture in fixtures:
        match_id = fixture.get("id")
        if not match_id:
            continue

        # Aggregate sentiment
        aggregate_data = aggregate_match_sentiment(
            match_id, window_hours, settings.MAX_POSTS_PER_MATCH
        )

        if aggregate_data:
            # Save to database
            if save_sentiment_aggregate(aggregate_data):
                processed += 1

    logger.info(f"Processed sentiment aggregation for {processed}/{len(fixtures)} matches")
    return processed


def get_match_sentiment(match_id: str) -> Optional[Dict]:
    """Get latest sentiment aggregate for a match."""
    try:
        with handle_db_errors() as session:
            aggregate = (
                session.query(SentimentAggregate)
                .filter(SentimentAggregate.match_id == match_id)
                .order_by(SentimentAggregate.created_at.desc())
                .first()
            )

            if aggregate:
                return {
                    "match_id": aggregate.match_id,
                    "aggregate_score": aggregate.aggregate_score,
                    "positive_pct": aggregate.positive_pct,
                    "negative_pct": aggregate.negative_pct,
                    "neutral_pct": aggregate.neutral_pct,
                    "sample_count": aggregate.sample_count,
                    "created_at": aggregate.created_at.isoformat(),
                }

            return None

    except Exception as e:
        logger.error(f"Error getting match sentiment for {match_id}: {e}")
        return None
