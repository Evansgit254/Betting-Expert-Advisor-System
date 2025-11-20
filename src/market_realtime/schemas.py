"""Pydantic schemas for real-time market data."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class LiveOdds(BaseModel):
    """Live odds from a bookmaker."""
    bookmaker: str
    home_odds: float
    away_odds: float
    draw_odds: Optional[float] = None
    timestamp: datetime


class MarketFixture(BaseModel):
    """Market fixture with ML analysis."""
    fixture_id: str
    home_team: str
    away_team: str
    league: str
    country: str
    commence_time: datetime
    
    # Odds data
    best_home_odds: float
    best_away_odds: float
    best_draw_odds: Optional[float] = None
    bookmakers: List[str]
    
    # ML predictions
    ml_home_prob: float
    ml_away_prob: float
    ml_draw_prob: float
    ml_confidence: float
    predicted_outcome: str
    
    # Value metrics
    ev_score: float
    arbitrage_opportunity: bool
    arbitrage_profit: Optional[float] = None
    
    # Sentiment
    sentiment_score: Optional[float] = None
    sentiment_sample_count: Optional[int] = None
    
    # Risk
    risk_category: str  # low, medium, high
    volatility_index: float
    
    # Market indicators
    odds_drift: float  # percentage change in odds
    sharp_money_indicator: bool
    market_efficiency: float


class MarketHeadline(BaseModel):
    """Real-time market headline alert."""
    timestamp: datetime
    headline: str
    confidence: float = Field(ge=0.0, le=1.0)
    drivers: List[str]  # sentiment, sharp_money, arb_window, etc.
    fixtures: List[str]  # fixture IDs
    priority: str = "normal"  # low, normal, high, critical


class BettingSuggestion(BaseModel):
    """ML-powered betting suggestion."""
    fixture_id: str
    home_team: str
    away_team: str
    league: str
    commence_time: datetime
    
    # Recommendation
    suggested_selection: str  # home, away, draw
    suggested_odds: float
    suggested_stake: Optional[float] = None
    
    # ML metrics
    ml_confidence: float
    ml_probabilities: Dict[str, float]
    ev_score: float
    
    # Supporting data
    sentiment_score: Optional[float] = None
    arbitrage_index: float
    risk_score: float
    strategy_alignment: float
    
    # Reasoning
    reason: str
    confidence_factors: List[str]
    risk_factors: List[str]


class ManualBetRequest(BaseModel):
    """Request to place a manual bet."""
    fixture_id: str
    selection: str  # home, away, draw
    odds: float = Field(gt=1.0)
    stake: float = Field(gt=0)
    is_virtual: bool = True
    notes: Optional[str] = None


class MarketFiltersRequest(BaseModel):
    """Filters for market fixtures query."""
    leagues: Optional[List[str]] = None
    countries: Optional[List[str]] = None
    bookmakers: Optional[List[str]] = None
    min_ev: Optional[float] = None
    max_ev: Optional[float] = None
    min_confidence: Optional[float] = None
    max_confidence: Optional[float] = None
    min_arbitrage: Optional[float] = None
    kickoff_start: Optional[datetime] = None
    kickoff_end: Optional[datetime] = None
    risk_categories: Optional[List[str]] = None
    sort_by: str = "ev_score"  # ev_score, confidence, volatility, arbitrage, kickoff
    limit: int = Field(default=50, le=500)
