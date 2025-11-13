"""Monitoring module with FastAPI metrics endpoint."""
import os
from typing import Any, Dict

import requests
from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from src.logging_config import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Betting Expert Advisor Monitoring")

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
def report_bet(payload: Dict[str, Any]) -> Dict[str, bool]:
    """Report a bet placement for metrics.

    Expected payload:
    {
        "status": "accepted|rejected|error",
        "stake": 100.0,
        "ev": 0.05,
        "dry_run": true,
        "bankroll": 10000.0
    }
    """
    status = payload.get("status", "unknown")
    dry_run = payload.get("dry_run", True)
    stake = payload.get("stake", 0.0)
    ev = payload.get("ev", 0.0)

    # Update metrics
    bets_placed_total.labels(status=status, dry_run=str(dry_run)).inc()

    if stake > 0:
        bets_stake_total.labels(dry_run=str(dry_run)).inc(stake)

    if ev is not None:
        bets_expected_value.observe(ev)

    if "bankroll" in payload:
        current_bankroll.set(float(payload["bankroll"]))

    if "open_bets" in payload:
        open_bets_count.set(int(payload["open_bets"]))

    if "daily_pnl" in payload:
        daily_pnl.set(float(payload["daily_pnl"]))

    return {"accepted": True}


@app.post("/report/prediction")
def report_prediction() -> Dict[str, bool]:
    """Report a model prediction for metrics."""
    model_predictions.inc()
    return {"accepted": True}


@app.post("/report/error")
def report_error(payload: Dict[str, Any]) -> Dict[str, bool]:
    """Report an API error.

    Expected payload:
    {
        "source": "theodds_api|betfair|pinnacle|other"
    }
    """
    source = payload.get("source", "other")
    api_errors.labels(source=source).inc()
    return {"accepted": True}


@app.get("/")
def root() -> Dict[str, Any]:
    """Root endpoint with service information."""
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
