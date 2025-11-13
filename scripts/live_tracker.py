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
from src.config import settings
from src.data_fetcher import DataFetcher
from src.executor import Executor
from src.feature import build_features, select_features
from src.logging_config import get_logger
from src.model import ModelWrapper
from src.monitoring import send_alert
from src.paths import LIVE_OPPORTUNITIES_FILE
from src.strategy import apply_bet_filters, find_value_bets

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
        timestamp = datetime.now(timezone.utc)

        print(f"\n[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Checking opportunities...")

        try:
            # CRITICAL FIX: Check for model updates
            self._check_and_reload_model()

            # Fetch data (uses cache automatically)
            fixtures = self.fetcher.get_fixtures()

            if isinstance(fixtures, list):
                fixtures = pd.DataFrame(fixtures)

            odds = self.fetcher.get_odds(list(fixtures["market_id"]) if not fixtures.empty else [])

            if isinstance(odds, list):
                odds = pd.DataFrame(odds)

            print(f"  📊 {len(fixtures)} fixtures, {len(odds)} odds")

            if len(fixtures) == 0:
                print("  ❌ No fixtures found.")
                return []

            if len(odds) == 0:
                print("  ❌ No odds found.")
                return []

            # Build features
            features = build_features(fixtures, odds)

            # Make predictions
            if self.model is None:
                print("  ⚠️  No model - using normalized implied probabilities")

                if "home_prob" not in features.columns:
                    if "home_odds" in features.columns:
                        features["home_prob"] = 1.0 / features["home_odds"]
                    else:
                        print("  ❌ Cannot calculate probabilities")
                        return []
            else:
                print("  🤖 Using ML model predictions...")

                X = features.drop(columns=["market_id", "result"], errors="ignore")
                X_selected = select_features(X)

                try:
                    predictions = self.model.predict_proba(X_selected)

                    if len(predictions.shape) > 1 and predictions.shape[1] > 1:
                        features["home_prob"] = predictions[:, 1]
                    else:
                        features["home_prob"] = predictions

                    print(f"  ✅ Predictions: mean={features['home_prob'].mean():.3f}")

                except Exception as e:
                    print(f"  ⚠️  Model failed: {e}, using implied probs")
                    logger.error(f"Model prediction error: {e}", exc_info=True)

                    if "home_odds" in features.columns:
                        features["home_prob"] = 1.0 / features["home_odds"]

            # Verify columns
            if "home_odds" not in features.columns or "home_prob" not in features.columns:
                print(f"  ❌ Missing required columns")
                print(f"  Available: {list(features.columns)}")
                return []

            # Find value bets
            print(f"  🔍 Searching for value bets...")

            value_bets = find_value_bets(
                features, proba_col="home_prob", odds_col="home_odds", bank=10000.0, min_ev=0.01
            )

            if not isinstance(value_bets, list):
                value_bets = list(value_bets)

            # Apply filters
            filtered = apply_bet_filters(
                value_bets, min_ev=0.001, min_confidence=0.50, max_total=10
            )

            if not isinstance(filtered, list):
                filtered = list(filtered)

            print(f"  ✅ {len(value_bets)} potential, {len(filtered)} after filters")

            if len(filtered) > 0:
                self.alert_opportunities(filtered)

            return filtered

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
        executor = Executor()
        exec_results = []

        for i, bet in enumerate(opportunities, 1):
            print(f"{i}. {bet.get('home', 'TBD')} vs {bet.get('away', 'TBD')}")
            print(
                f"   Odds: {bet['odds']:.2f} | Prob: {bet['p']:.1%} | "
                f"Edge: {bet['ev']:.2f} | Stake: ${bet['stake']:.2f}"
            )
            print()

            batch_msgs.append(
                f"{i}. {bet.get('home', 'TBD')} vs {bet.get('away', 'TBD')}\n"
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
