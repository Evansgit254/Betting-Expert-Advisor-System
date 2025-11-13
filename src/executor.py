"""Bet execution engine with critical fixes applied.

CRITICAL FIXES:
1. Transaction atomicity (two-phase commit)
2. Rate limiting on bet placement
3. Enhanced error handling
4. State machine for bet lifecycle
"""
import hashlib
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from src.config import settings
from src.db import BetRecord, get_daily_loss, get_open_bets_count, handle_db_errors, init_db, save_bet
from src.logging_config import get_logger
from src.monitoring import send_alert
from src.risk import check_risk_limits, validate_bet_parameters

logger = get_logger(__name__)


class BetStatus(Enum):
    """Bet lifecycle states."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REJECTED = "rejected"


class MockBookie:
    """Simple bookmaker client used for testing and dry-run mode."""

    def place_bet(
        self,
        market_id: str,
        selection: str,
        stake: float,
        odds: float,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        ticket_id = uuid.uuid4().hex[:12]
        return {
            "status": "accepted",
            "bet_id": ticket_id,
            "market_id": market_id,
            "selection": selection,
            "stake": stake,
            "odds": odds,
            "idempotency_key": idempotency_key,
            "placed_at": datetime.now(timezone.utc).isoformat(),
        }


class Executor:
    """Execute bets with full risk management and safety checks.

    CRITICAL FIXES:
    - Two-phase commit for atomicity
    - Rate limiting (max 10 bets/minute)
    - Proper state tracking
    """

    def __init__(self, client=None):
        """Initialize executor.

        Args:
            client: Bookmaker API client (optional, for LIVE mode)
        """
        self.client = client or MockBookie()
        self.mode = settings.MODE

        # CRITICAL FIX: Rate limiting
        self._bet_timestamps = deque(maxlen=100)
        self._rate_limit_per_minute = 10
        self._rate_limit_lock = False

        logger.info(f"Executor initialized in {self.mode} mode")

    def _check_rate_limit(self) -> bool:
        """Ensure we don't exceed bet placement rate.

        CRITICAL FIX: Prevents accidental bet flooding.

        Returns:
            True if rate limit check passed
        """
        now = time.time()

        # Remove timestamps older than 1 minute
        while self._bet_timestamps and now - self._bet_timestamps[0] > 60:
            self._bet_timestamps.popleft()

        if len(self._bet_timestamps) >= self._rate_limit_per_minute:
            wait_time = 60 - (now - self._bet_timestamps[0])

            if wait_time > 0:
                logger.warning(
                    f"Rate limit reached ({self._rate_limit_per_minute}/min), "
                    f"waiting {wait_time:.1f}s"
                )
                send_alert(
                    f"⚠️ Rate limit protection: pausing for {wait_time:.1f}s", level="warning"
                )
                time.sleep(wait_time + 0.1)  # Add small buffer
                self._bet_timestamps.clear()

        self._bet_timestamps.append(now)
        return True

    def _generate_idempotency_key(self, bet: Dict[str, Any]) -> str:
        """Generate idempotency key from bet parameters.

        Args:
            bet: Bet dictionary

        Returns:
            Unique idempotency key
        """
        key_parts = [
            str(bet.get("market_id", "")),
            str(bet.get("selection", "")),
            str(bet.get("odds", "")),
            str(bet.get("stake", "")),
            datetime.now(timezone.utc).isoformat(),
        ]

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def _validate_bet(self, bet: Dict[str, Any]) -> bool:
        """Validate bet dictionary has required fields.

        Args:
            bet: Bet dictionary

        Returns:
            True if valid
        """
        required_fields = ["market_id", "selection", "stake", "odds"]

        for field in required_fields:
            if field not in bet:
                logger.error(f"Missing required field: {field}")
                return False

        # Validate parameters
        validation = validate_bet_parameters(
            market_id=bet["market_id"],
            selection=bet["selection"],
            stake=bet["stake"],
            odds=bet["odds"],
            probability=bet.get("p"),
        )

        if not validation["valid"]:
            logger.error(f"Invalid bet parameters: {validation['errors']}")
            return False

        return True

    def execute(self, bet: Dict[str, Any], dry_run: Optional[bool] = None) -> Dict[str, Any]:
        """Execute bet with two-phase commit pattern.

        CRITICAL FIX: Implements atomicity to prevent DB/API inconsistency.

        Phase 1: Validate and prepare
        Phase 2: Save to DB as PENDING
        Phase 3: Call bookmaker API (if LIVE)
        Phase 4: Update status to CONFIRMED/FAILED

        Args:
            bet: Bet dictionary with market_id, selection, stake, odds
            dry_run: Override mode (None = use settings.MODE)

        Returns:
            Dict with execution result
        """

        # Determine execution mode
        if dry_run is None:
            dry_run = settings.MODE != "LIVE"

        if not dry_run and settings.MODE != "LIVE":
            return {
                "status": "rejected",
                "message": "LIVE mode not enabled. Set MODE=LIVE to place real bets.",
                "dry_run": False,
                "db_error": "LIVE mode not enabled",
            }

        start_time = time.time()
        init_db()

        # Phase 1: Validate
        if not self._validate_bet(bet):
            return {
                "status": "rejected",
                "reason": "Invalid bet parameters",
                "message": "Invalid bet parameters",
                "dry_run": dry_run,
            }

        # Check rate limit
        self._check_rate_limit()

        # Generate idempotency key
        idempotency_key = self._generate_idempotency_key(bet)

        # Get current state for risk checks
        with handle_db_errors() as session:
            open_bets = get_open_bets_count(exclude_dry_run=True)
            daily_loss = get_daily_loss()
            bankroll = bet.get("bankroll", 10000.0)

        # Check risk limits
        risk_meta = dict(bet)
        risk_meta["dry_run"] = dry_run
        risk_check = check_risk_limits(
            stake=bet["stake"],
            bankroll=bankroll,
            open_bets_count=open_bets,
            daily_loss=daily_loss,
            bet_meta=risk_meta,
        )

        if not risk_check["allowed"]:
            logger.warning(f"Bet rejected by risk management: {risk_check['reason']}")
            return {
                "status": "rejected",
                "reason": risk_check["reason"],
                "message": risk_check["reason"],
                "dry_run": dry_run,
            }

        # Phase 2: Save to DB as PENDING
        try:
            with handle_db_errors() as session:
                try:
                    meta_payload = {
                        "status": BetStatus.PENDING.value,
                        "submitted_at": datetime.now(timezone.utc).isoformat(),
                    }
                    meta_payload.update({k: v for k, v in bet.items() if k != "meta"})
                    if bet.get("meta"):
                        meta_payload.update(bet.get("meta", {}))

                    db_bet = save_bet(
                        market_id=bet["market_id"],
                        selection=bet["selection"],
                        stake=bet["stake"],
                        odds=bet["odds"],
                        idempotency_key=idempotency_key,
                        is_dry_run=dry_run,
                        meta=meta_payload,
                        strategy_name=bet.get("strategy_name"),
                        strategy_params=bet.get("strategy_params"),
                    )
                except Exception as exc:
                    logger.error(f"Failed to persist bet: {exc}", exc_info=True)
                    return {
                        "status": "error",
                        "db_error": str(exc),
                        "dry_run": dry_run,
                    }

                db_id = db_bet.id
                logger.info(
                    f"Bet saved to DB with ID {db_id} (dry_run={dry_run}, "
                    f"idempotency_key={idempotency_key})"
                )

                # Phase 3: Execute (if not dry_run)
                if not dry_run:
                    if not self.client:
                        # No client configured - fail safely
                        session.query(BetRecord).filter_by(id=db_id).update(
                            {
                                "meta": {
                                    "status": BetStatus.FAILED.value,
                                    "error": "No bookmaker client configured",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                            }
                        )
                        session.commit()

                        send_alert(
                            "⚠️ Bet execution failed: No bookmaker client configured", level="error"
                        )

                        return {
                            "status": "error",
                            "message": "No bookmaker client configured",
                            "db_id": db_id,
                            "dry_run": dry_run,
                        }

                    # Phase 3b: Call bookmaker API
                    try:
                        logger.info(f"Placing LIVE bet {db_id} via bookmaker API...")

                        api_result = self.client.place_bet(
                            market_id=bet["market_id"],
                            selection=bet["selection"],
                            stake=bet["stake"],
                            odds=bet["odds"],
                            idempotency_key=idempotency_key,
                        )

                        # Phase 4: Update to CONFIRMED
                        session.query(BetRecord).filter_by(id=db_id).update(
                            {
                                "meta": {
                                    "status": BetStatus.CONFIRMED.value,
                                    "api_ref": api_result.get("bet_id"),
                                    "confirmed_at": datetime.now(timezone.utc).isoformat(),
                                    "api_response": api_result,
                                }
                            }
                        )
                        session.commit()

                        execution_time = time.time() - start_time

                        logger.info(
                            f"✅ LIVE bet {db_id} placed successfully "
                            f"(API ref: {api_result.get('bet_id')}, time: {execution_time:.2f}s)"
                        )

                        send_alert(
                            f"✅ LIVE BET PLACED\n"
                            f"Market: {bet['market_id']}\n"
                            f"Selection: {bet['selection']}\n"
                            f"Stake: ${bet['stake']:.2f} @ {bet['odds']:.2f}\n"
                            f"API Ref: {api_result.get('bet_id')}",
                            level="info",
                        )

                        return {
                            "status": "accepted",
                            "db_id": db_id,
                            "api_ref": api_result.get("bet_id"),
                            "execution_time": execution_time,
                            "dry_run": False,
                        }

                    except Exception as e:
                        # Phase 4: Mark as FAILED if API call fails
                        logger.error(f"API call failed for bet {db_id}: {e}", exc_info=True)

                        session.query(BetRecord).filter_by(id=db_id).update(
                            {
                                "meta": {
                                    "status": BetStatus.FAILED.value,
                                    "error": str(e),
                                    "failed_at": datetime.now(timezone.utc).isoformat(),
                                }
                            }
                        )
                        session.commit()

                        send_alert(
                            f"🚨 Bet execution failed: {e}\n"
                            f"DB ID: {db_id}\n"
                            f"Market: {bet['market_id']}",
                            level="error",
                        )

                        return {
                            "status": "error",
                            "message": str(e),
                            "db_id": db_id,
                            "dry_run": False,
                        }

                # Dry run success
                execution_time = time.time() - start_time

                logger.info(
                    f"✅ Dry-run bet {db_id} recorded successfully " f"(time: {execution_time:.2f}s)"
                )

                return {
                    "status": "dry_run",
                    "db_id": db_id,
                    "message": "Bet recorded in database (dry-run mode)",
                    "execution_time": execution_time,
                    "dry_run": True,
                    "idempotency_key": idempotency_key,
                }

        except Exception as e:
            logger.error(f"Critical error in bet execution: {e}", exc_info=True)
            send_alert(f"🚨 CRITICAL: Bet execution crashed: {e}", level="critical")

            return {"status": "error", "message": f"Execution error: {str(e)}", "dry_run": dry_run}

    def execute_batch(
        self, bets: list[Dict[str, Any]], dry_run: Optional[bool] = None
    ) -> list[Dict[str, Any]]:
        """Execute multiple bets with rate limiting.

        Args:
            bets: List of bet dictionaries
            dry_run: Override mode

        Returns:
            List of execution results
        """
        results = []

        logger.info(f"Executing batch of {len(bets)} bets")

        for i, bet in enumerate(bets, 1):
            logger.info(f"Processing bet {i}/{len(bets)}")
            result = self.execute(bet, dry_run=dry_run)
            results.append(result)

            # Small delay between bets in batch
            if i < len(bets):
                time.sleep(0.5)

        # Summary
        statuses = [r["status"] for r in results]
        logger.info(
            f"Batch execution complete: "
            f"{statuses.count('accepted')} accepted, "
            f"{statuses.count('dry_run')} dry-run, "
            f"{statuses.count('rejected')} rejected, "
            f"{statuses.count('error')} errors"
        )

        return results

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get executor statistics.

        Returns:
            Dict with rate limiting and execution stats
        """
        return {
            "mode": self.mode,
            "rate_limit_per_minute": self._rate_limit_per_minute,
            "recent_bets_count": len(self._bet_timestamps),
            "client_configured": self.client is not None,
        }
