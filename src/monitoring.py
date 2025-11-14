"""Monitoring module with FastAPI metrics endpoint."""
import os
import traceback
import uuid
from contextvars import ContextVar
from typing import Any, Dict

import requests
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

from src.logging_config import get_logger

logger = get_logger(__name__)

# Context variable for request correlation ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

app = FastAPI(title="Betting Expert Advisor Monitoring")


# Pydantic models for request validation
class BetReportRequest(BaseModel):
    """Request model for bet reporting."""
    status: str = Field(..., description="Bet status: accepted, rejected, or error")
    stake: float = Field(default=0.0, ge=0)
    ev: float = Field(default=0.0, description="Expected value")
    dry_run: bool = Field(default=True)
    bankroll: float = Field(default=None, ge=0)
    open_bets: int = Field(default=None, ge=0)
    daily_pnl: float = Field(default=None)


class ErrorReportRequest(BaseModel):
    """Request model for error reporting."""
    source: str = Field(..., description="Error source: theodds_api, betfair, pinnacle, other")
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


def send_alert(message: str, level: str = "warning"):
    """Send alert to operator (supports Telegram, logs as fallback)."""
    import logging

    logging.warning(f"ALERT ({level}): {message}")
    # Telegram config via env
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        try:
            telegram_api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": f"[BettingExpert][{level.upper()}]\n{message}"}
            resp = requests.post(telegram_api, data=payload, timeout=10)
            if not resp.ok:
                logging.warning(f"Telegram alert failed: {resp.text}")
        except Exception as e:
            logging.warning(f"Telegram alert exception: {e}")


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

# Mount static files if directory exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve monitoring dashboard."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r") as f:
            return f.read()
    return """<h1>Betting Expert Advisor</h1><p>Dashboard not found. API is running.</p>"""


@app.get("/api/info")
def root() -> Dict[str, Any]:
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
