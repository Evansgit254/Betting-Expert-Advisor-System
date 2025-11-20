"""API routes for real-time market data."""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime

from src.logging_config import get_logger
from src.market_realtime.realtime_ingest import RealtimeMarketIngestor
from src.market_realtime.headline_generator import HeadlineGenerator
from src.market_realtime.suggestion_engine import SuggestionEngine
from src.market_realtime.filters import MarketFilters
from src.market_realtime.schemas import (
    MarketHeadline, BettingSuggestion, ManualBetRequest, MarketFixture
)
from src.db import handle_db_errors, BetRecord

logger = get_logger(__name__)
router = APIRouter(prefix="/market", tags=["market"])

ingestor = RealtimeMarketIngestor()
headline_gen = HeadlineGenerator()
suggestion_engine = SuggestionEngine()
filters = MarketFilters()


@router.get("/headlines")
async def get_market_headlines(leagues: Optional[str] = Query(None)) -> dict:
    """Get real-time market headlines."""
    try:
        league_list = leagues.split(',') if leagues else None
        fixtures = ingestor.ingest_realtime_market(league_list)
        headlines = headline_gen.generate_headlines(fixtures)
        
        return {
            "success": True,
            "count": len(headlines),
            "headlines": [h.dict() for h in headlines],
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating headlines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def get_betting_suggestions(
    min_confidence: float = Query(0.6, ge=0.0, le=1.0),
    limit: int = Query(20, le=100),
    leagues: Optional[str] = Query(None)
) -> dict:
    """Get ML-powered betting suggestions."""
    try:
        league_list = leagues.split(',') if leagues else None
        fixtures = ingestor.ingest_realtime_market(league_list)
        suggestions = suggestion_engine.generate_suggestions(fixtures, min_confidence, limit)
        
        return {
            "success": True,
            "count": len(suggestions),
            "suggestions": [s.dict() for s in suggestions],
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error generating suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fixtures")
async def get_market_fixtures(
    leagues: Optional[str] = Query(None),
    countries: Optional[str] = Query(None),
    bookmakers: Optional[str] = Query(None),
    min_ev: Optional[float] = Query(None),
    max_ev: Optional[float] = Query(None),
    min_confidence: Optional[float] = Query(None),
    max_confidence: Optional[float] = Query(None),
    min_arbitrage: Optional[float] = Query(None),
    risk_categories: Optional[str] = Query(None),
    sort_by: str = Query("ev_score"),
    limit: int = Query(50, le=500)
) -> dict:
    """Get filtered market fixtures."""
    try:
        league_list = leagues.split(',') if leagues else None
        fixtures = ingestor.ingest_realtime_market(league_list)
        
        filtered = filters.apply_filters(
            fixtures,
            leagues=league_list,
            countries=countries.split(',') if countries else None,
            bookmakers=bookmakers.split(',') if bookmakers else None,
            min_ev=min_ev,
            max_ev=max_ev,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            min_arbitrage=min_arbitrage,
            risk_categories=risk_categories.split(',') if risk_categories else None,
            sort_by=sort_by,
            limit=limit
        )
        
        return {
            "success": True,
            "count": len(filtered),
            "fixtures": filtered,
            "filters_applied": {
                "leagues": league_list,
                "min_ev": min_ev,
                "min_confidence": min_confidence,
                "sort_by": sort_by
            },
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching fixtures: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual_bet")
async def place_manual_bet(bet: ManualBetRequest) -> dict:
    """Place a manual bet."""
    try:
        with handle_db_errors() as session:
            bet_record = BetRecord(
                market_id=bet.fixture_id,
                selection=bet.selection,
                stake=bet.stake,
                odds=bet.odds,
                is_dry_run=bet.is_virtual,
                strategy_name='manual',
                result='pending'
            )
            
            session.add(bet_record)
            session.commit()
            
            logger.info(f"Manual bet placed: {bet.fixture_id} - {bet.selection} @ {bet.odds}")
            
            return {
                "success": True,
                "bet_id": bet_record.id,
                "message": f"{'Virtual' if bet.is_virtual else 'Live'} bet placed successfully",
                "bet": {
                    "fixture_id": bet.fixture_id,
                    "selection": bet.selection,
                    "odds": bet.odds,
                    "stake": bet.stake,
                    "is_virtual": bet.is_virtual
                }
            }
    except Exception as e:
        logger.error(f"Error placing manual bet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/live_odds")
async def get_live_odds(leagues: Optional[str] = Query(None)) -> dict:
    """Get live merged odds from all providers."""
    try:
        league_list = leagues.split(',') if leagues else None
        fixtures = ingestor.fetch_live_fixtures(league_list)
        
        return {
            "success": True,
            "count": len(fixtures),
            "fixtures": fixtures,
            "sources": ["theodds"],
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching live odds: {e}")
        raise HTTPException(status_code=500, detail=str(e))
