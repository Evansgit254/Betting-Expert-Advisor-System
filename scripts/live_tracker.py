"""Live odds tracker with critical fixes applied.

CRITICAL FIXES:
1. Memory management for long-running processes
2. Automatic model reload detection
3. Enhanced error handling
4. Graceful degradation
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gc
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.adapters.theodds_api import TheOddsAPIAdapter
from src.adapters.betfair import BetfairAdapter
from src.config import settings
from src.data_fetcher import DataFetcher
from src.executor import Executor
from src.feature import build_features, select_features
from src.logging_config import get_logger
from src.model import ModelWrapper
from src.monitoring import send_alert
from src.paths import LIVE_OPPORTUNITIES_FILE
from src.strategy import apply_bet_filters, find_value_bets
from src.safety import SafetyManager
from src.bot import TelegramBot

logger = get_logger(__name__)


class LiveOddsTracker:
    """Track live odds with memory management and auto-reload.

    CRITICAL FIXES:
    - Periodic garbage collection
    - Model reload detection
    - Memory leak prevention
    - Graceful error recovery
    """

    def __init__(self, check_interval: int = 3600, model_check_interval: int = 3600):
        """Initialize tracker.

        Args:
            check_interval: Seconds between odds checks (default: 1 hour)
            model_check_interval: Seconds between model reload checks (default: 1 hour)
        """
        self.check_interval = check_interval
        self.model_check_interval = model_check_interval
        self.opportunities_file = LIVE_OPPORTUNITIES_FILE

        # CRITICAL FIX: Track iterations for memory management
        self._check_count = 0
        self._max_checks_before_gc = 10  # GC every 10 checks
        self._max_checks_before_restart_warning = 100  # Warn at 100 checks

        # CRITICAL FIX: Model reload tracking
        self.last_model_check = datetime.now(timezone.utc)
        self.model_mtime = self._get_model_mtime()

        # Load model
        self.model = ModelWrapper()
        try:
            self.model.load("models/model.pkl")
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load model: {e}")
            self.model = None

        # Initialize data fetcher with caching
        self.fetcher = DataFetcher(source=TheOddsAPIAdapter(api_key=settings.THEODDS_API_KEY))
        
        # Initialize Safety Manager and Telegram Bot
        self.safety_manager = SafetyManager()
        self.bot = TelegramBot()

    def _get_model_mtime(self) -> float:
        """Get model file modification time.

        Returns:
            Modification timestamp, or 0 if file doesn't exist
        """
        model_path = Path("models/model.pkl")
        return model_path.stat().st_mtime if model_path.exists() else 0.0

    def _check_and_reload_model(self):
        """Reload model if file has changed.

        CRITICAL FIX: Automatic model updates without restart.
        """
        now = datetime.now(timezone.utc)

        # Only check periodically
        if (now - self.last_model_check).total_seconds() < self.model_check_interval:
            return

        self.last_model_check = now
        current_mtime = self._get_model_mtime()

        if current_mtime > self.model_mtime:
            logger.info("Detected new model file, reloading...")

            try:
                self.model = ModelWrapper()
                self.model.load("models/model.pkl")
                self.model_mtime = current_mtime

                logger.info("✅ Model reloaded successfully")
                send_alert("✅ Model reloaded successfully", level="info")

            except Exception as e:
                logger.error(f"Failed to reload model: {e}", exc_info=True)
                send_alert(f"⚠️ Model reload failed: {e}", level="warning")
                # Keep using old model

    def _perform_memory_cleanup(self):
        """Perform periodic memory cleanup.

        CRITICAL FIX: Prevents memory leaks in long-running processes.
        """
        if self._check_count % self._max_checks_before_gc == 0:
            logger.info(f"Performing memory cleanup after {self._check_count} checks")

            # Force garbage collection
            collected = gc.collect()

            logger.debug(f"Garbage collector freed {collected} objects")

            # Optional: Log memory usage
            try:
                import psutil

                process = psutil.Process()
                mem_info = process.memory_info()
                logger.info(
                    f"Memory usage: RSS={mem_info.rss / 1024 / 1024:.1f}MB, "
                    f"VMS={mem_info.vms / 1024 / 1024:.1f}MB"
                )
            except ImportError:
                pass  # psutil not available

    def check_opportunities(self):
        """Check for current betting opportunities with error handling."""
        # CRITICAL: Check Kill Switch
        if self.safety_manager.is_kill_switch_active():
            logger.warning("🚨 KILL SWITCH ACTIVE - Skipping analysis loop")
            return []

        timestamp = datetime.now(timezone.utc)

        print(f"\n[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Checking opportunities...")

        try:
            # CRITICAL FIX: Check for model updates
            self._check_and_reload_model()

            all_opportunities = []
            
            # Iterate through all active sports
            for sport in settings.ACTIVE_SPORTS:
                try:
                    logger.info(f"Fetching data for {sport}...")
                    
                    # Update fetcher sport
                    if hasattr(self.fetcher.source, 'default_sport'):
                        self.fetcher.source.default_sport = sport
                    
                    # Fetch data
                    fixtures_list = self.fetcher.source.fetch_fixtures(
                        start_date=datetime.now(timezone.utc),
                        end_date=datetime.now(timezone.utc) + timedelta(days=7),
                    )
                    fixtures = pd.DataFrame(fixtures_list)

                    if fixtures.empty:
                        continue

                    market_ids = fixtures["market_id"].tolist()
                    if not market_ids:
                        continue

                    odds_list = self.fetcher.source.fetch_odds(market_ids)
                    odds = pd.DataFrame(odds_list)
                    
                    if odds.empty:
                        continue

                    features = build_features(fixtures, odds)
                    
                    # Prediction logic
                    if self.model is None:
                        features["prob_home"] = features["implied_prob_home"]
                    else:
                        try:
                            X = features.drop(columns=["market_id", "result"], errors="ignore")
                            X_selected = select_features(X)
                            probs = self.model.predict_proba(X_selected)
                            
                            # Handle different prediction output formats
                            if hasattr(probs, "shape") and len(probs.shape) > 1 and probs.shape[1] > 1:
                                features["prob_home"] = probs[:, 1]
                            else:
                                features["prob_home"] = probs
                        except Exception as e:
                            logger.error(f"Prediction error for {sport}: {e}")
                            # Fallback to implied probability
                            if "implied_prob_home" in features.columns:
                                features["prob_home"] = features["implied_prob_home"]
                            elif "home_odds" in features.columns:
                                features["prob_home"] = 1.0 / features["home_odds"]
                            else:
                                logger.warning(f"Could not calculate probability for {sport}")
                                continue

                    # Find value bets
                    bets = find_value_bets(
                        features,
                        proba_col="prob_home",
                        odds_col="home_odds",
                        min_ev=settings.MIN_EV,
                        bank=10000,
                    )
                    
                    if bets:
                        logger.info(f"Found {len(bets)} value bets for {sport}")
                        all_opportunities.extend(bets)
                        
                except Exception as e:
                    logger.error(f"Error processing {sport}: {e}", exc_info=True)
                    continue

            if not all_opportunities:
                logger.info("No value bets found across all sports")
                return []
            # Sort and filter
            all_opportunities.sort(key=lambda x: x["ev"], reverse=True)
            
            # Apply filters
            opportunities = apply_bet_filters(
                all_opportunities, 
                min_ev=settings.MIN_EV, 
                min_confidence=settings.MIN_CONFIDENCE, 
                max_total=10
            )
            
            if opportunities:
                self.alert_opportunities(opportunities)
                
            return opportunities

        except Exception as e:
            logger.error(f"Error checking opportunities: {e}", exc_info=True)
            print(f"  ❌ Error: {e}")

            # Send critical alert if this is a repeated error
            if self._check_count > 0:
                send_alert(
                    f"⚠️ Error in live tracker (check #{self._check_count}): {e}", level="warning"
                )

            return []

    def alert_opportunities(self, opportunities):
        """Alert user and execute paper bets automatically."""
        print("\n" + "=" * 70)
        print("  🚨 VALUE BET ALERT!")
        print("=" * 70 + "\n")

        batch_msgs = []
        exec_results = []
        exec_results = []

        for i, bet in enumerate(opportunities, 1):
            print(f"{i}. {bet.get('home', 'TBD')} vs {bet.get('away', 'TBD')}")
            print(f"   👉 BET: {bet.get('selection', 'UNKNOWN').upper()}")
            print(
                f"   Odds: {bet['odds']:.2f} | Prob: {bet['p']:.1%} | "
                f"Edge: {bet['ev']:.2f} | Stake: ${bet['stake']:.2f}"
            )
            print()

            batch_msgs.append(
                f"{i}. {bet.get('home', 'TBD')} vs {bet.get('away', 'TBD')}\n"
                f"   👉 BET: {bet.get('selection', 'UNKNOWN').upper()}\n"
                f"   Odds: {bet['odds']:.2f} | Prob: {bet['p']:.1%} | "
                f"Edge: {bet['ev']:.2f} | Stake: ${bet['stake']:.2f}"
            )

            # Place paper bet automatically
            try:
                result = executor.execute(bet, dry_run=True)
                exec_results.append(result)
            except Exception as e:
                logger.error(f"Error executing paper bet: {e}", exc_info=True)
                exec_results.append({"status": "error", "message": str(e)})

        # Send batched alert
        if batch_msgs:
            msg = "🚨 VALUE BET ALERTS (Batch)\n" + "\n".join(batch_msgs)
            send_alert(msg, level="info")

        print("=" * 70 + "\n")

        # Show execution results
        if exec_results:
            print("Paper bets automatically placed:")
            for r in exec_results:
                status = r.get("status", "unknown")
                db_id = r.get("db_id", "N/A")
                print(f"  - {status} (DB ID: {db_id})")

        # Save to file
        import json

        with open(self.opportunities_file, "w") as f:
            json.dump(opportunities, f, indent=2, default=str)

    def run_continuous(self):
        """Run continuous monitoring with memory management."""
        print("\n" + "=" * 70)
        print("  📊 LIVE ODDS TRACKER")
        print("=" * 70)
        print(f"\n⏱️  Checking every {self.check_interval} seconds")
        print(f"📊 Model: {'Loaded ✅' if self.model else 'Not loaded ⚠️'}")
        print(f"📝 Alerts: Console + {self.opportunities_file}")
        print(f"💾 Memory cleanup every {self._max_checks_before_gc} checks")
        print("\nPress Ctrl+C to stop\n")

        # Start Telegram Bot
        self.bot.start()

        try:
            while True:
                self.check_opportunities()

                self._check_count += 1

                # CRITICAL FIX: Periodic memory cleanup
                self._perform_memory_cleanup()

                # CRITICAL FIX: Restart recommendation
                if self._check_count >= self._max_checks_before_restart_warning:
                    logger.warning(
                        f"Tracker has run {self._check_count} checks. "
                        f"Consider restarting for optimal memory usage."
                    )

                    send_alert(
                        f"📊 Tracker has run {self._check_count} checks. "
                        "Recommend restart for memory hygiene.",
                        level="info",
                    )

                    # Reset counter
                    self._check_count = 0

                next_check = datetime.now(timezone.utc) + timedelta(seconds=self.check_interval)
                print(
                    f"  ⏰ Next check: {next_check.strftime('%H:%M:%S')} "
                    f"(check #{self._check_count + 1})"
                )

                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            print("\n\n👋 Stopping tracker...")
            logger.info("Tracker stopped by user")

        except Exception as e:
            logger.error(f"Fatal error in tracker: {e}", exc_info=True)
            send_alert(f"🚨 Tracker crashed: {e}", level="critical")
            raise

        finally:
            self.bot.stop()

    def run_once(self):
        """Run single check."""
        print("\n" + "=" * 70)
        print("  📊 SINGLE ODDS CHECK")
        print("=" * 70 + "\n")

        opportunities = self.check_opportunities()

        if not opportunities:
            print("\n✅ No value bets found at this time")

        print("\n" + "=" * 70 + "\n")

        return opportunities


def main():
    """Run live tracker."""
    import argparse

    parser = argparse.ArgumentParser(description="Live Odds Tracker")
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Check interval in seconds (default: 3600 = 1 hour)",
    )
    parser.add_argument("--once", action="store_true", help="Run once instead of continuously")
    parser.add_argument(
        "--model-check-interval",
        type=int,
        default=3600,
        help="Model reload check interval in seconds (default: 3600)",
    )

    args = parser.parse_args()

    tracker = LiveOddsTracker(
        check_interval=args.interval, model_check_interval=args.model_check_interval
    )

    if args.once:
        tracker.run_once()
    else:
        tracker.run_continuous()


if __name__ == "__main__":
    main()
