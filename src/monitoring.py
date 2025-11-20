"""Monitoring module with FastAPI metrics endpoint and WebSocket support."""
import os
import traceback
import uuid
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Request, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

from src.logging_config import get_logger
from src.data_fetcher import DataFetcher
from src.db import BetRecord, get_strategy_performance, handle_db_errors
from src.alerts import send_alert
from src.safety import SafetyManager
from sqlalchemy import text

logger = get_logger(__name__)

# Context variable for request correlation ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

app = FastAPI(title="Betting Expert Advisor Monitoring")
safety_manager = SafetyManager()


# CORS for frontend UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request validation
class BetReportRequest(BaseModel):
    """Request model for bet reporting."""
    status: str = Field(default="accepted", description="Bet status: accepted, rejected, or error")
    stake: float = Field(default=0.0, ge=0)
    ev: float = Field(default=0.0, description="Expected value")
    dry_run: bool = Field(default=True)
    bankroll: float = Field(default=None, ge=0)
    open_bets: int = Field(default=None, ge=0)
    daily_pnl: float = Field(default=None)


class ErrorReportRequest(BaseModel):
    """Request model for error reporting."""
    source: str = Field(default="other", description="Error source: theodds_api, betfair, pinnacle, other")
    message: str = Field(default="", description="Error message")


# Middleware for request correlation IDs
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Add correlation ID to each request for tracing."""
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request_id_var.set(correlation_id)
    
    # Add to request state for easy access in endpoints
    request.state.correlation_id = correlation_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = correlation_id
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with logging and alerting."""
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    
    # Log full traceback
    logger.error(
        "Unhandled exception in API (correlation_id=%s, path=%s): %s",
        correlation_id,
        request.url.path,
        str(exc),
        exc_info=True,
        extra={"correlation_id": correlation_id, "path": str(request.url.path)},
    )
    
    # Send critical alert
    send_alert(
        f"API Exception: {type(exc).__name__} at {request.url.path}\n"
        f"Correlation ID: {correlation_id}\n"
        f"Error: {str(exc)}\n"
        f"Traceback: {traceback.format_exc()[:500]}",
        level="critical",
    )
    
    # Return structured error response
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "correlation_id": correlation_id,
        },
    )

# Metrics
bets_placed_total = Counter("bets_placed_total", "Total bets placed", ["status", "dry_run"])
bets_stake_total = Counter("bets_stake_total", "Total stake amount", ["dry_run"])
bets_expected_value = Histogram(
    "bets_expected_value",
    "Expected value of bets",
    buckets=[0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0],
)
current_bankroll = Gauge("bankroll_current", "Current bankroll")
daily_pnl = Gauge("daily_pnl", "Daily profit/loss")
open_bets_count = Gauge("open_bets_count", "Number of open bets")
model_predictions = Counter("model_predictions_total", "Total model predictions")
api_errors = Counter("api_errors_total", "API errors", ["source"])


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "betting-expert-advisor"}


@app.post("/report/bet")
def report_bet(payload: BetReportRequest) -> Dict[str, bool]:
    """Report a bet placement for metrics.

    Uses Pydantic model for automatic validation.
    """
    # Update metrics
    bets_placed_total.labels(status=payload.status, dry_run=str(payload.dry_run)).inc()

    if payload.stake > 0:
        bets_stake_total.labels(dry_run=str(payload.dry_run)).inc(payload.stake)

    if payload.ev is not None:
        bets_expected_value.observe(payload.ev)

    if payload.bankroll is not None:
        current_bankroll.set(float(payload.bankroll))

    if payload.open_bets is not None:
        open_bets_count.set(int(payload.open_bets))

    if payload.daily_pnl is not None:
        daily_pnl.set(float(payload.daily_pnl))

    return {"accepted": True}


# --- UI API endpoints ---
@app.get("/bets")
def list_bets(limit: int = 50) -> Dict[str, Any]:
    """List recent bets from the database."""
    limit = max(1, min(limit, 500))
    with handle_db_errors() as session:
        rows = (
            session.query(BetRecord)
            .order_by(BetRecord.placed_at.desc())
            .limit(limit)
            .all()
        )
        results = [
            {
                "id": r.id,
                "market_id": r.market_id,
                "selection": r.selection,
                "stake": r.stake,
                "odds": r.odds,
                "result": r.result,
                "profit_loss": r.profit_loss,
                "placed_at": r.placed_at,
                "settled_at": r.settled_at,
                "is_dry_run": r.is_dry_run,
                "strategy_name": r.strategy_name,
            }
            for r in rows
        ]
    return {"items": results, "count": len(results)}


@app.get("/fixtures")
def get_fixtures(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Return fixtures via DataFetcher with caching enabled."""
    # Note: Parsing start/end omitted for brevity; DataFetcher supports optional dates
    df = DataFetcher().get_fixtures()
    items = df.to_dict(orient="records") if not df.empty else []
    return {"items": items, "count": len(items)}


@app.get("/odds")
def get_odds(market_ids: Optional[str] = None) -> Dict[str, Any]:
    """Return odds for provided market IDs (comma-separated)."""
    ids: List[str] = []
    if market_ids:
        ids = [s.strip() for s in market_ids.split(",") if s.strip()]
    df = DataFetcher().get_odds(ids) if ids else DataFetcher().get_odds([])
    items = df.to_dict(orient="records") if not df.empty else []
    return {"items": items, "count": len(items)}


@app.get("/strategy/performance")
def strategy_performance(strategy_name: Optional[str] = None) -> Dict[str, Any]:
    """Return strategy performance metrics aggregated from DB."""
    items = get_strategy_performance(strategy_name=strategy_name)
    return {"items": items, "count": len(items)}


@app.post("/report/prediction")
def report_prediction() -> Dict[str, bool]:
    """Report a model prediction for metrics."""
    model_predictions.inc()
    return {"accepted": True}


@app.post("/report/error")
def report_error(payload: ErrorReportRequest) -> Dict[str, bool]:
    """Report an API error.

    Uses Pydantic model for automatic validation.
    """
    api_errors.labels(source=payload.source).inc()
    if payload.message:
        logger.warning("API error reported from %s: %s", payload.source, payload.message)
    return {"accepted": True}


from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import asyncio

# Mount static files if directory exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Import new modules
try:
    from src.sentiment.scraper import SentimentScraperService
    from src.arbitrage_detector import ArbitrageDetector
    sentiment_service = SentimentScraperService()
    arbitrage_detector = ArbitrageDetector()
except ImportError as e:
    logger.warning(f"Could not import sentiment/arbitrage modules: {e}")
    sentiment_service = None
    arbitrage_detector = None


# ===== NEW UI ENDPOINTS =====

@app.get("/ui/fixtures")
def get_ui_fixtures() -> Dict[str, Any]:
    """Get fixtures with sentiment data for UI."""
    try:
        df = DataFetcher().get_fixtures()
        fixtures = df.to_dict(orient="records") if not df.empty else []
        
        # Attach sentiment if available
        if sentiment_service:
            for fixture in fixtures:
                sentiment = sentiment_service.get_sentiment_for_match(fixture.get('id', ''))
                fixture['sentiment'] = sentiment
        
        return {"items": fixtures, "count": len(fixtures)}
    except Exception as e:
        logger.error(f"Error getting UI fixtures: {e}", exc_info=True)
        return {"items": [], "count": 0, "error": str(e)}


@app.get("/ui/odds")
def get_ui_odds(market_ids: Optional[str] = None) -> Dict[str, Any]:
    """Get odds for UI with arbitrage detection."""
    try:
        ids: List[str] = []
        if market_ids:
            ids = [s.strip() for s in market_ids.split(",") if s.strip()]
        
        df = DataFetcher().get_odds(ids) if ids else DataFetcher().get_odds([])
        
        # Detect arbitrage if enabled
        arbitrage_opps = []
        if arbitrage_detector and not df.empty:
            arbitrage_opps = arbitrage_detector.detect_opportunities(df)
        
        items = df.to_dict(orient="records") if not df.empty else []
        
        return {
            "items": items,
            "count": len(items),
            "arbitrage_opportunities": arbitrage_opps,
        }
    except Exception as e:
        logger.error(f"Error getting UI odds: {e}", exc_info=True)
        return {"items": [], "count": 0, "error": str(e)}


@app.get("/ui/sentiment")
async def get_ui_sentiment(market_id: Optional[str] = None) -> Dict[str, Any]:
    """Get sentiment data for UI."""
    try:
        if not sentiment_service:
            return {"error": "Sentiment service not available"}
        
        if market_id:
            sentiment = sentiment_service.get_sentiment_for_match(market_id)
            return {"market_id": market_id, "sentiment": sentiment}
        
        # Get recent sentiment data
        with handle_db_errors() as session:
            from src.sentiment.models import SentimentAnalysis
            recent = session.query(SentimentAnalysis).order_by(
                SentimentAnalysis.created_at.desc()
            ).limit(100).all()
            
            items = [
                {
                    'id': s.id,
                    'market_id': s.market_id,
                    'team': s.team,
                    'sentiment_score': s.sentiment_score,
                    'sentiment_label': s.sentiment_label,
                    'keywords': s.keywords,
                    'source': s.source,
                    'created_at': s.created_at.isoformat(),
                }
                for s in recent
            ]
            
            return {"items": items, "count": len(items)}
            
    except Exception as e:
        logger.error(f"Error getting sentiment: {e}", exc_info=True)
        return {"error": str(e)}


@app.get("/ui/arbitrage")
def get_ui_arbitrage(market_id: Optional[str] = None) -> Dict[str, Any]:
    """Get arbitrage opportunities for UI."""
    try:
        if not arbitrage_detector:
            return {"error": "Arbitrage detector not available"}
        
        opportunities = arbitrage_detector.get_active_opportunities(market_id)
        
        return {"items": opportunities, "count": len(opportunities)}
        
    except Exception as e:
        logger.error(f"Error getting arbitrage: {e}", exc_info=True)
        return {"error": str(e)}


@app.get("/ui/suggestions")
def get_ui_suggestions() -> Dict[str, Any]:
    """Get AI betting suggestions for UI."""
    try:
        # This would integrate with the existing strategy module
        # For now, return recent high-confidence bets
        with handle_db_errors() as session:
            recent_bets = session.query(BetRecord).filter(
                BetRecord.result == 'pending',
                BetRecord.is_dry_run == True
            ).order_by(BetRecord.placed_at.desc()).limit(20).all()
            
            suggestions = [
                {
                    'id': b.id,
                    'market_id': b.market_id,
                    'selection': b.selection,
                    'stake': b.stake,
                    'odds': b.odds,
                    'placed_at': b.placed_at.isoformat(),
                    'strategy_name': b.strategy_name,
                }
                for b in recent_bets
            ]
            
            return {"items": suggestions, "count": len(suggestions)}
            
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}", exc_info=True)
        return {"error": str(e)}


class ManualBetRequest(BaseModel):
    """Request model for manual bet placement."""
    market_id: str
    selection: str
    stake: float = Field(gt=0)
    odds: float = Field(gt=1.0)
    is_virtual: bool = Field(default=True)
    notes: Optional[str] = None


@app.post("/ui/manual_bet")
def place_manual_bet(bet: ManualBetRequest) -> Dict[str, Any]:
    """Place a manual bet (virtual or live)."""
    try:
        from src.db import save_bet
        
        # Save bet with manual flag
        meta = {
            'is_manual': True,
            'notes': bet.notes,
            'placed_via': 'ui',
        }
        
        db_bet = save_bet(
            market_id=bet.market_id,
            selection=bet.selection,
            stake=bet.stake,
            odds=bet.odds,
            is_dry_run=bet.is_virtual,
            meta=meta,
            strategy_name='manual',
        )
        
        logger.info(
            f"Manual bet placed: {bet.selection} @ {bet.odds} "
            f"(virtual={bet.is_virtual}, id={db_bet.id})"
        )
        
        return {
            "success": True,
            "bet_id": db_bet.id,
            "message": f"{'Virtual' if bet.is_virtual else 'Live'} bet placed successfully",
        }
        
    except Exception as e:
        logger.error(f"Error placing manual bet: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve monitoring dashboard."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r") as f:
            return f.read()
    return """<h1>Betting Expert Advisor</h1><p>Dashboard not found. API is running.</p>"""


@app.get("/system/status")
def system_status() -> Dict[str, Any]:
    """Get system status including circuit breakers."""
    from src.adapters._circuit import get_circuit_breaker_status
    from src.config import settings
    
    try:
        # Get circuit breaker status
        cb_status = {}
        for name in ["theodds_api", "betfair", "pinnacle"]:
            cb_status[name] = get_circuit_breaker_status(name)
        
        # Database status
        db_status = {"status": "connected"}
        try:
            with handle_db_errors() as session:
                session.execute(text("SELECT 1"))
                db_status["status"] = "connected"
        except Exception as e:
            db_status["status"] = "error"
            db_status["error"] = str(e)
        
        return {
            "status": "operational",
            "mode": settings.MODE,
            "circuit_breakers": cb_status,
            "database": db_status,
            "cache": {"status": "available"},
        }
    except Exception as e:
        logger.error("Error getting system status: %s", str(e), exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }


@app.get("/arbitrage")
def get_arbitrage_opportunities() -> Dict[str, Any]:
    """Get arbitrage betting opportunities.
    
    Returns opportunities where betting on all outcomes guarantees profit.
    """
    try:
        # Mock data for now - in production, this would scan multiple bookmakers
        opportunities = []
        
        # Example arbitrage opportunity
        opportunities.append({
            "id": "arb_001",
            "market_id": "soccer_epl_match_12345",
            "home_team": "Manchester United",
            "away_team": "Liverpool",
            "sport": "Soccer - Premier League",
            "commence_time": "2025-11-16T15:00:00Z",
            "profit_margin": 0.0234,  # 2.34% profit
            "total_stake": 1000.0,
            "legs": [
                {
                    "bookmaker": "Bet365",
                    "selection": "Manchester United",
                    "odds": 2.15,
                    "stake": 465.12,
                    "expected_return": 1000.0,
                },
                {
                    "bookmaker": "Pinnacle",
                    "selection": "Draw",
                    "odds": 3.50,
                    "stake": 285.71,
                    "expected_return": 1000.0,
                },
                {
                    "bookmaker": "Betfair",
                    "selection": "Liverpool",
                    "odds": 4.00,
                    "stake": 250.00,
                    "expected_return": 1000.0,
                },
            ],
            "detected_at": "2025-11-14T21:30:00Z",
        })
        
        return {
            "items": opportunities,
            "count": len(opportunities),
        }
    except Exception as e:
        logger.error("Error fetching arbitrage opportunities: %s", str(e), exc_info=True)
        return {
            "items": [],
            "count": 0,
            "error": str(e),
        }


# Social Signals API Endpoints
from src.config import settings
from datetime import datetime

if settings.ENABLE_SOCIAL_SIGNALS:
    try:
        from src.social.api import (
            create_manual_bet,
            find_arbitrage_opportunities,
            generate_betting_suggestions,
            get_match_details,
        )
        
        @app.get("/social/suggestions")
        def get_social_suggestions(
            since: Optional[str] = None,
            limit: int = 20,
            min_confidence: float = 0.3,
        ) -> Dict[str, Any]:
            """Get AI-suggested bets based on sentiment and odds."""
            try:
                suggestions = generate_betting_suggestions(min_confidence, limit)
                
                if since:
                    try:
                        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
                        suggestions = [
                            s for s in suggestions
                            if datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")) >= since_dt
                        ]
                    except Exception as e:
                        logger.warning(f"Invalid since parameter: {e}")
                
                return {"suggestions": suggestions, "count": len(suggestions)}
            except Exception as e:
                logger.error(f"Error getting social suggestions: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Failed to get suggestions", "detail": str(e)}
                )
        
        @app.get("/social/arbitrage")
        def get_social_arbitrage() -> Dict[str, Any]:
            """Get active arbitrage opportunities."""
            try:
                opportunities = find_arbitrage_opportunities()
                return {"opportunities": opportunities, "count": len(opportunities)}
            except Exception as e:
                logger.error(f"Error getting arbitrage opportunities: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Failed to get arbitrage opportunities", "detail": str(e)}
                )
        
        @app.get("/social/match/{match_id}")
        def get_social_match_details(match_id: str, include_posts: bool = True) -> Dict[str, Any]:
            """Get detailed sentiment and post samples for a match."""
            try:
                details = get_match_details(match_id, include_posts)
                if not details:
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Match not found or no sentiment data"}
                    )
                return details
            except Exception as e:
                logger.error(f"Error getting match details for {match_id}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Failed to get match details", "detail": str(e)}
                )
        
        @app.post("/social/manual_bet")
        def post_social_manual_bet(
            match_id: str,
            selection: str,
            stake: float,
            odds: float,
            is_virtual: bool = True,
        ) -> Dict[str, Any]:
            """Create a manual bet based on social signals."""
            try:
                result = create_manual_bet(match_id, selection, stake, odds, is_virtual)
                return result
            except Exception as e:
                logger.error(f"Error creating manual bet: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Failed to create bet", "detail": str(e)}
                )
        
        logger.info("Social signals API endpoints registered")
    except ImportError as e:
        logger.warning(f"Social signals module not available: {e}")


# Analytics API Endpoints
try:
    from src.api.analytics_routes import router as analytics_router
    app.include_router(analytics_router)
    logger.info("Analytics API endpoints registered")
except ImportError as e:
    logger.warning(f"Analytics module not available: {e}")


# Market Realtime API Endpoints
try:
    from src.api.market_routes import router as market_router
    app.include_router(market_router)
    logger.info("Market realtime API endpoints registered")
except ImportError as e:
    logger.warning(f"Market realtime module not available: {e}")


# ===== MARKET INTELLIGENCE API ENDPOINTS (NEW) =====

try:
    from src.market_intelligence import get_engine
    from datetime import datetime
    
    @app.get("/api/market-intelligence")
    async def get_market_intelligence(
        max_results: int = 10,
        min_ev: float = 0.01,
        min_sentiment: float = -1.0,
        leagues: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get real-time market intelligence suggestions.
        
        This endpoint fuses:
        - ML predictions (LightGBM model with 67.63% accuracy)
        - Expected value calculations (Kelly criterion)
        - Sentiment analysis (social signals)
        - Arbitrage opportunities (guaranteed profit)
        
        Returns suggestions ranked by composite score.
        
        Args:
            max_results: Maximum number of suggestions to return (1-50)
            min_ev: Minimum expected value threshold (default: 0.01 = 1%)
            min_sentiment: Minimum sentiment score (-1.0 to 1.0)
            leagues: Comma-separated league IDs (e.g., "soccer_epl,soccer_spain_la_liga")
        
        Returns:
            {
                "headline": str,
                "generated_at": ISO datetime,
                "suggestions": List[...],
                "filters_applied": {...}
            }
        """
        try:
            # Validate parameters
            max_results = max(1, min(max_results, 50))
            min_ev = max(-1.0, min(min_ev, 1.0))
            min_sentiment = max(-1.0, min(min_sentiment, 1.0))
            
            # Parse leagues
            league_list = None
            if leagues:
                league_list = [l.strip() for l in leagues.split(',') if l.strip()]
            
            # Get engine and generate suggestions
            engine = get_engine()
            result = engine.generate_suggestions(
                max_suggestions=max_results,
                min_ev=min_ev,
                min_sentiment=min_sentiment,
                leagues=league_list
            )
            
            logger.info(f"Market intelligence generated: {len(result.get('suggestions', []))} suggestions")
            return result
            
        except Exception as e:
            logger.error(f"Error generating market intelligence: {e}", exc_info=True)
            return {
                "headline": "🔥 Real-Time Market Highlights – Here Are Today's Top Suggested Fixtures Across All Leagues",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "suggestions": [],
                "error": str(e),
                "filters_applied": {
                    "min_ev": min_ev,
                    "min_sentiment": min_sentiment,
                    "leagues": leagues or "all"
                }
            }
    
    
    @app.get("/api/fixtures/browse")
    async def browse_fixtures(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        leagues: Optional[str] = None,
        market_type: str = "h2h",
        min_confidence: float = 0.0,
        max_hours_to_kickoff: Optional[int] = None
    ) -> Dict[str, Any]:
        """Browse fixtures with filters for manual betting.
        
        Returns enriched fixture list with:
        - ML predictions and confidence
        - Odds from multiple bookmakers
        - Expected value calculations
        - Sentiment data
        - Arbitrage flags
        
        Args:
            start_date: Filter fixtures from this date (ISO format)
            end_date: Filter fixtures up to this date (ISO format)
            leagues: Comma-separated league IDs
            market_type: Market type (h2h, totals, spreads) - default: h2h
            min_confidence: Minimum ML confidence threshold (0.0 to 1.0)
            max_hours_to_kickoff: Maximum hours until kickoff (e.g., 24 for next 24h)
        
        Returns:
            {
                "fixtures": List[{fixture with ML, odds, sentiment, arbitrage}],
                "count": int,
                "filters_applied": {...}
            }
        """
        try:
            # Parse dates
            start_dt = None
            end_dt = None
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"Invalid start_date format: {start_date}")
            
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"Invalid end_date format: {end_date}")
            
            # Parse leagues
            league_list = None
            if leagues:
                league_list = [l.strip() for l in leagues.split(',') if l.strip()]
            
            # Get fixtures with all enrichments
            engine = get_engine()
            result = engine.generate_suggestions(
                max_suggestions=100,  # Get more for browsing
                min_ev=-1.0,  # No EV filter for browsing
                min_sentiment=-1.0,  # No sentiment filter
                leagues=league_list,
                start_date=start_dt,
                end_date=end_dt
            )
            
            fixtures = result.get('suggestions', [])
            
            # Apply confidence filter
            if min_confidence > 0.0:
                fixtures = [f for f in fixtures if f.get('recommendation', {}).get('confidence', 0.0) >= min_confidence]
            
            # Apply hours to kickoff filter
            if max_hours_to_kickoff is not None:
                now = datetime.now(timezone.utc)
                max_hours = max_hours_to_kickoff
                filtered = []
                for f in fixtures:
                    try:
                        kickoff = datetime.fromisoformat(f.get('kickoff', '').replace('Z', '+00:00'))
                        hours_diff = (kickoff - now).total_seconds() / 3600
                        if 0 <= hours_diff <= max_hours:
                            filtered.append(f)
                    except:
                        continue
                fixtures = filtered
            
            logger.info(f"Browse fixtures returned {len(fixtures)} results")
            
            return {
                "fixtures": fixtures,
                "count": len(fixtures),
                "filters_applied": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "leagues": leagues or "all",
                    "market_type": market_type,
                    "min_confidence": min_confidence,
                    "max_hours_to_kickoff": max_hours_to_kickoff
                }
            }
            
        except Exception as e:
            logger.error(f"Error browsing fixtures: {e}", exc_info=True)
            return {
                "fixtures": [],
                "count": 0,
                "error": str(e),
                "filters_applied": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "leagues": leagues or "all",
                    "market_type": market_type,
                    "min_confidence": min_confidence,
                    "max_hours_to_kickoff": max_hours_to_kickoff
                }
            }
    
    
    class EnhancedManualBetRequest(BaseModel):
        """Enhanced request model for manual bet placement with ML validation."""
        market_id: str
        selection: str
        stake: float = Field(gt=0)
        odds: float = Field(gt=1.0)
        is_virtual: bool = Field(default=True)
        notes: Optional[str] = None
        override_risk_checks: bool = Field(default=False)
    
    
    @app.post("/api/manual-bet")
    async def place_enhanced_manual_bet(bet: EnhancedManualBetRequest) -> Dict[str, Any]:
        """Place a manual bet with ML validation and risk warnings.
        
        This endpoint:
        - Validates bet parameters
        - Gets ML probability for reference
        - Runs risk checks (bankroll, daily loss, position limits)
        - Executes bet via BetExecutor
        - Stores in manual_bets table
        - Returns ML prediction and risk warnings
        
        Args:
            market_id: Market/fixture ID
            selection: home, away, or draw
            stake: Bet stake amount
            odds: Decimal odds
            is_virtual: True for paper trading, False for live
            notes: Optional user notes
            override_risk_checks: Admin flag to bypass risk limits (use with caution)
        
        Returns:
            {
                "success": bool,
                "bet_id": str,
                "status": str,
                "ml_probability": float,
                "ev_estimate": float,
                "risk_warning": Optional[str],
                "confirmation": {...}
            }
        """
        try:
            from src.executor import BetExecutor
            from src.risk import check_risk_limits, calculate_expected_value, validate_bet_parameters
            from src.db import get_current_bankroll, get_daily_loss, get_open_bets_count
            
            # Validate bet parameters
            validation = validate_bet_parameters(
                market_id=bet.market_id,
                selection=bet.selection,
                stake=bet.stake,
                odds=bet.odds
            )
            
            if not validation['valid']:
                return {
                    "success": False,
                    "error": "Invalid bet parameters",
                    "validation_errors": validation['errors']
                }
            
            # Get ML probability for this market/selection (for reference)
            ml_probability = None
            ev_estimate = None
            try:
                engine = get_engine()
                # Try to get prediction from recent suggestions
                # Simplified: Use odds-implied probability as fallback
                ml_probability = 1.0 / bet.odds  # Implied probability
                ev_estimate = calculate_expected_value(ml_probability, bet.odds, bet.stake)
            except Exception as e:
                logger.warning(f"Could not get ML probability: {e}")
            
            # Run risk checks (unless overridden)
            risk_warning = None
            if not bet.override_risk_checks:
                bankroll = get_current_bankroll()
                daily_loss = get_daily_loss()
                open_bets = get_open_bets_count()
                
                risk_result = check_risk_limits(
                    stake=bet.stake,
                    bankroll=bankroll,
                    open_bets_count=open_bets,
                    daily_loss=daily_loss
                )
                
                if not risk_result['allowed']:
                    risk_warning = risk_result.get('reason', 'Risk limit exceeded')
                    # For manual bets, we warn but don't block
                    logger.warning(f"Manual bet risk warning: {risk_warning}")
            
            # Execute bet via BetExecutor
            executor = BetExecutor()
            result = executor.place_bet(
                market_id=bet.market_id,
                selection=bet.selection,
                stake=bet.stake,
                odds=bet.odds,
                probability=ml_probability,
                strategy_name="manual",
                meta={
                    "is_manual": True,
                    "notes": bet.notes,
                    "placed_via": "api",
                    "ml_probability": ml_probability,
                    "ev_estimate": ev_estimate,
                    "risk_warning": risk_warning
                }
            )
            
            logger.info(
                f"Enhanced manual bet placed: {bet.selection} @ {bet.odds} "
                f"(virtual={bet.is_virtual}, id={result.get('bet_id')})"
            )
            
            potential_profit = (bet.odds - 1.0) * bet.stake
            
            return {
                "success": True,
                "bet_id": result.get('bet_id', ''),
                "status": result.get('status', 'unknown'),
                "ml_probability": ml_probability,
                "ev_estimate": ev_estimate,
                "risk_warning": risk_warning,
                "confirmation": {
                    "market_id": bet.market_id,
                    "selection": bet.selection,
                    "stake": bet.stake,
                    "odds": bet.odds,
                    "potential_profit": round(potential_profit, 2),
                    "is_virtual": bet.is_virtual
                }
            }
            
        except Exception as e:
            logger.error(f"Error placing enhanced manual bet: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    logger.info("Market Intelligence API endpoints registered successfully")
    
except ImportError as e:
    logger.warning(f"Market Intelligence module not available: {e}")
    logger.info("Market Intelligence endpoints will not be available")



@app.get("/")
def root() -> Dict[str, Any]:
    """API information endpoint."""
    endpoints = {
        "health": "/health",
        "system_status": "/system/status",
        "metrics": "/metrics",
        "bets": "/bets",
        "fixtures": "/fixtures",
        "odds": "/odds",
        "arbitrage": "/arbitrage",
        "strategy_performance": "/strategy/performance",
        "report_bet": "/report/bet",
        "report_prediction": "/report/prediction",
        "report_error": "/report/error",
        "dashboard": "/dashboard",
        # NEW Market Intelligence endpoints
        "market_intelligence": "/api/market-intelligence",
        "browse_fixtures": "/api/fixtures/browse",
        "manual_bet": "/api/manual-bet",
    }
    
    if settings.ENABLE_SOCIAL_SIGNALS:
        endpoints.update({
            "social_suggestions": "/social/suggestions",
            "social_arbitrage": "/social/arbitrage",
            "social_match_details": "/social/match/{match_id}",
            "social_manual_bet": "/social/manual_bet",
        })
    
    return {
        "service": "Betting Expert Advisor",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": endpoints,
    }


@app.get("/api/info")
def api_info() -> Dict[str, Any]:
    """API information endpoint."""
    return {
        "service": "Betting Expert Advisor",
        "version": "1.0.0",
        "endpoints": {
            "metrics": "/metrics",
            "health": "/health",
            "report_bet": "/report/bet",
            "report_prediction": "/report/prediction",
            "report_error": "/report/error",
        },
    }


def update_metrics(bet_result: Dict[str, Any], bankroll: float, open_bets: int, daily_pl: float):
    """Helper function to update metrics from bet execution.

    Args:
        bet_result: Result dictionary from executor
        bankroll: Current bankroll
        open_bets: Current open bets count
        daily_pl: Daily profit/loss
    """
    status = bet_result.get("status", "unknown")
    dry_run = bet_result.get("dry_run", True)

    bets_placed_total.labels(status=status, dry_run=str(dry_run)).inc()
    current_bankroll.set(bankroll)
    open_bets_count.set(open_bets)
    daily_pnl.set(daily_pl)

# --- Admin / Safety Endpoints ---

@app.post("/api/admin/kill")
async def kill_switch():
    """Emergency kill switch to stop all betting activities."""
    success = safety_manager.activate_kill_switch(reason="API Request")
    if success:
        return {"status": "killed", "message": "System halted successfully"}
    return JSONResponse(status_code=500, content={"error": "Failed to activate kill switch"})


@app.post("/api/admin/resume")
async def resume_switch():
    """Resume betting activities."""
    success = safety_manager.deactivate_kill_switch(reason="API Request")
    if success:
        return {"status": "active", "message": "System resumed successfully"}
    return JSONResponse(status_code=500, content={"error": "Failed to deactivate kill switch"})


@app.get("/api/admin/status")
async def admin_status():
    """Get current system safety status."""
    is_killed = safety_manager.is_kill_switch_active()
    return {
        "kill_switch_active": is_killed,
        "status": "halted" if is_killed else "running"
    }

# --- WebSocket Support ---

import asyncio
import json
from typing import List
from pathlib import Path

class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        if not self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    
    try:
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Betting Expert Advisor"
        })
        
        # Keep connection alive and listen for client messages
        while True:
            try:
                # Wait for message with timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Echo back (for ping/pong)
                await websocket.send_json({"type": "pong", "data": data})
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def broadcast_update(update_type: str, data: dict):
    """Helper to broadcast updates to all WebSocket clients."""
    await manager.broadcast({
        "type": update_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# Background task to periodically broadcast live opportunities
from datetime import datetime, timezone

@app.on_event("startup")
async def startup_event():
    """Start background tasks."""
    asyncio.create_task(broadcast_live_data())

async def broadcast_live_data():
    """Periodically broadcast live opportunities and metrics."""
    while True:
        try:
            await asyncio.sleep(3)  # Broadcast every 3 seconds
            
            if not manager.active_connections:
                continue
            
            # Read live opportunities file
            opps_file = Path("/app/live_opportunities.json")
            if opps_file.exists():
                try:
                    with open(opps_file, "r") as f:
                        opportunities = json.load(f)
                    await broadcast_update("opportunities", opportunities)
                except Exception as e:
                    logger.error(f"Error reading opportunities: {e}")
            
            # Broadcast system metrics
            metrics = {
                "bankroll": current_bankroll._value.get() if hasattr(current_bankroll, '_value') else 0,
                "open_bets": open_bets_count._value.get() if hasattr(open_bets_count, '_value') else 0,
                "daily_pnl": daily_pnl._value.get() if hasattr(daily_pnl, '_value') else 0,
                "kill_switch_active": safety_manager.is_kill_switch_active()
            }
            await broadcast_update("metrics", metrics)
            
        except Exception as e:
            logger.error(f"Error in broadcast loop: {e}")
            await asyncio.sleep(5)
