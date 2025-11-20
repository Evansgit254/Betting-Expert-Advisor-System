"""Database models for social signals and sentiment analysis."""
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.db import Base


class SocialPost(Base):
    """Social media posts and blog content."""

    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, index=True)  # twitter, reddit, blog
    external_post_id = Column(String(255), unique=True, index=True)
    author = Column(String(255))
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)  # Post creation time
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    match_id = Column(String(255), index=True)  # Linked fixture/market ID
    match_confidence = Column(Float, default=0.0)  # Confidence of match linking
    url = Column(String(512))
    post_metadata = Column(JSON)  # Additional source-specific data

    # Relationship
    sentiments = relationship("SocialSentiment", back_populates="post", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SocialPost(id={self.id}, source={self.source}, match_id={self.match_id})>"


class SocialSentiment(Base):
    """Sentiment analysis results for social posts."""

    __tablename__ = "social_sentiments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("social_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    sentiment_score = Column(Float, nullable=False)  # -1.0 to 1.0
    sentiment_label = Column(String(20), nullable=False)  # positive, negative, neutral
    model = Column(String(50), nullable=False)  # vader, hf-distilbert, etc.
    analyzed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confidence = Column(Float)  # Model confidence if available

    # Relationship
    post = relationship("SocialPost", back_populates="sentiments")

    def __repr__(self):
        return f"<SocialSentiment(post_id={self.post_id}, score={self.sentiment_score}, label={self.sentiment_label})>"


class SentimentAggregate(Base):
    """Aggregated sentiment scores per match."""

    __tablename__ = "sentiment_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String(255), nullable=False, index=True)
    aggregate_score = Column(Float, nullable=False)  # Weighted average sentiment
    positive_pct = Column(Float, nullable=False)  # % of positive posts
    negative_pct = Column(Float, nullable=False)  # % of negative posts
    neutral_pct = Column(Float, nullable=False)  # % of neutral posts
    sample_count = Column(Integer, nullable=False)  # Number of posts analyzed
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<SentimentAggregate(match_id={self.match_id}, score={self.aggregate_score}, n={self.sample_count})>"


class SuggestedBet(Base):
    """AI-suggested bets based on sentiment and odds analysis."""

    __tablename__ = "suggested_bets"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String(255), nullable=False, index=True)
    suggested_selection = Column(String(255), nullable=False)  # home, away, draw
    suggested_odds = Column(Float, nullable=False)
    ev_score = Column(Float)  # Expected value score
    sentiment_score = Column(Float)  # Sentiment contribution
    confidence = Column(Float, nullable=False)  # Overall confidence 0-1
    is_arbitrage = Column(Boolean, default=False, index=True)
    arbitrage_legs = Column(JSON)  # For arbitrage: [{bookie, selection, odds, stake}]
    reason = Column(Text)  # Human-readable explanation
    source_json = Column(JSON)  # Full source data for debugging
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime)  # When suggestion becomes stale
    is_executed = Column(Boolean, default=False)
    is_virtual = Column(Boolean, default=False)  # Virtual/paper bet flag

    def __repr__(self):
        return f"<SuggestedBet(id={self.id}, match={self.match_id}, selection={self.suggested_selection}, conf={self.confidence})>"
