"""Database models for sentiment analysis."""
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, JSON, Index
from src.db import Base
from src.utils import utc_now


class SentimentAnalysis(Base):
    """Store sentiment analysis results from social media."""
    
    __tablename__ = "sentiment_analysis"
    
    id = Column(String, primary_key=True)  # UUID
    market_id = Column(String, index=True, nullable=False)
    team = Column(String, nullable=False)
    sentiment_score = Column(Float, nullable=False)  # -1.0 to 1.0
    sentiment_label = Column(String, nullable=False)  # positive/negative/neutral
    keywords = Column(JSON, nullable=True)  # List of extracted keywords
    source = Column(String, nullable=False)  # twitter/reddit/blog/forum
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    __table_args__ = (
        Index('idx_sentiment_market_team', 'market_id', 'team'),
        Index('idx_sentiment_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SentimentAnalysis(market={self.market_id}, team={self.team}, score={self.sentiment_score})>"


class SentimentSource(Base):
    """Track sentiment data sources and scraping status."""
    
    __tablename__ = "sentiment_sources"
    
    id = Column(String, primary_key=True)
    source_type = Column(String, nullable=False)  # twitter/reddit/blog/forum
    source_url = Column(String, nullable=True)
    last_scraped = Column(DateTime, nullable=True)
    status = Column(String, default="active")  # active/disabled/error
    error_count = Column(Float, default=0)
    source_metadata = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<SentimentSource(type={self.source_type}, status={self.status})>"
