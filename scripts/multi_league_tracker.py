"""Multi-league live odds tracker with expanded market coverage + systemd integration."""

import os
import signal
import sys
import time
from datetime import datetime, timezone

# Ensure src module is importable regardless of run location
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.adapters.theodds_api import TheOddsAPIAdapter  # noqa: E402
from src.config import settings  # noqa: E402
from src.data_fetcher import DataFetcher  # noqa: E402
from src.feature import build_features, select_features  # noqa: E402
from src.logging_config import get_logger  # noqa: E402
from src.model import ModelWrapper  # noqa: E402
from src.paths import MULTI_LEAGUE_OPPORTUNITIES_FILE  # noqa: E402
from src.strategy import apply_bet_filters, find_value_bets  # noqa: E402

# --- Optional: systemd watchdog support
try:
    from systemd import daemon

    SYSTEMD_AVAILABLE = True
except ImportError:
    SYSTEMD_AVAILABLE = False

logger = get_logger(__name__)

# Supported leagues
LEAGUES = {
    "soccer_epl": "Premier League (England)",
    "soccer_spain_la_liga": "La Liga (Spain)",
    "soccer_germany_bundesliga": "Bundesliga (Germany)",
    "soccer_italy_serie_a": "Serie A (Italy)",
    "soccer_france_ligue_one": "Ligue 1 (France)",
    "soccer_uefa_champs_league": "Champions League",
    "soccer_uefa_europa_league": "Europa League",
}

stop_flag = False


def handle_sigterm(signum, frame):
    """Handle system signals for graceful shutdown."""
    global stop_flag
    stop_flag = True
    logger.info("🛑 Received stop signal, shutting down gracefully...")
    print("\n🛑 Received stop signal, shutting down gracefully...")


signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


class MultiLeagueTracker:
    """Track odds across multiple leagues and competitions."""

    def __init__(self, leagues=None, check_interval=3600):
        self.leagues = leagues or list(LEAGUES.keys())
        self.check_interval = check_interval
        self.opportunities_file = MULTI_LEAGUE_OPPORTUNITIES_FILE

        # Load ML model
        self.model = ModelWrapper()
        try:
            self.model.load("models/model.pkl")
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load model: {e}")
            self.model = None

    def check_league(self, league_key):
        """Check opportunities in a specific league."""
        try:
            logger.info(f"Checking {LEAGUES.get(league_key, league_key)}...")

            fetcher = DataFetcher(
                source=TheOddsAPIAdapter(
                    api_key=settings.THEODDS_API_KEY, sport=league_key, region="uk"
                )
            )

            fixtures = fetcher.get_fixtures()
            if fixtures.empty:
                logger.info(f"No fixtures available for {league_key}")
                return []

            odds = fetcher.get_odds(list(fixtures["market_id"]))
            if odds.empty:
                logger.info(f"No odds available for {league_key}")
                return []

            features = build_features(fixtures, odds)

            # Predict win probabilities
            if self.model is None:
                features["p_win"] = 0.50
            else:
                X = features.drop(columns=["market_id", "result"], errors="ignore")
                X_selected = select_features(X)
                preds = self.model.predict_proba(X_selected.values)[:, 1]
                features["p_win"] = preds

            features["odds"] = features.get("home", 2.0)
            features["selection"] = "home"
            features["league_name"] = LEAGUES.get(league_key, league_key)

            # Find value bets
            value_bets = find_value_bets(
                features, proba_col="p_win", odds_col="odds", bank=10000.0, min_ev=0.01
            )

            filtered = apply_bet_filters(value_bets, min_ev=0.01, min_confidence=0.55, max_total=10)

            if filtered:
                logger.info(f"🎯 Found {len(filtered)} opportunities in {league_key}")
                return filtered
            else:
                logger.info(f"No value bets found for {league_key}")
                return []

        except Exception as e:
            logger.error(f"Error checking {league_key}: {e}")
            return []

    def check_all_leagues(self):
        """Check all configured leagues."""
        timestamp = datetime.now(timezone.utc)
        print("\n" + "=" * 80)
        print("  🌍 MULTI-LEAGUE ODDS CHECK")
        print("=" * 80)
        print(f"  Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Leagues: {len(self.leagues)}")
        print("=" * 80 + "\n")

        all_opportunities = []

        for league_key in self.leagues:
            league_name = LEAGUES.get(league_key, league_key)
            print(f"🏆 {league_name}")
            opportunities = self.check_league(league_key)
            all_opportunities.extend(opportunities)
            print()

        # Summary
        print("=" * 80)
        print("  📊 SUMMARY")
        print("=" * 80)
        print(f"  Total opportunities found: {len(all_opportunities)}")

        if all_opportunities:
            self.display_opportunities(all_opportunities)
            self.save_opportunities(all_opportunities, timestamp)
        else:
            print("  ✅ No value bets found at this time")

        print("=" * 80 + "\n")

        return all_opportunities

    def display_opportunities(self, opportunities):
        """Display found opportunities."""
        if not opportunities:
            return

        print("\n  🎯 VALUE BETS FOUND:\n")

        for i, opp in enumerate(opportunities[:10], 1):
            league = opp.get("league_name", "Unknown")
            home = opp.get("home", "Unknown")
            away = opp.get("away", "Unknown")
            odds = opp.get("odds", 0)
            ev = opp.get("ev", 0)
            conf = opp.get("p_win", 0)
            stake = opp.get("stake", 0)

            print(f"  {i}. {league}")
            print(f"     {home} vs {away}")
            print(f"     Odds: {odds:.2f} | EV: {ev:.2%} | Confidence: {conf:.1%}")
            print(f"     Recommended stake: ${stake:.2f}")
            print()

    def save_opportunities(self, opportunities, timestamp):
        """Save opportunities to file."""
        import json

        try:
            existing = []
            if self.opportunities_file.exists():
                with open(self.opportunities_file, "r") as f:
                    existing = json.load(f)

            for opp in opportunities:
                opp["found_at"] = timestamp.isoformat()
                existing.append(opp)

            with open(self.opportunities_file, "w") as f:
                json.dump(existing, f, indent=2, default=str)

            logger.info(f"Saved opportunities to {self.opportunities_file}")

        except Exception as e:
            logger.error(f"Error saving opportunities: {e}")

    def run_continuous(self):
        """Run continuous monitoring with systemd watchdog support."""
        print("\n🔄 Starting continuous monitoring...")
        print(f"   Checking {len(self.leagues)} leagues every {self.check_interval // 60} minutes")
        print("   Press Ctrl+C to stop\n")

        while not stop_flag:
            try:
                self.check_all_leagues()

                # Notify systemd watchdog (heartbeat)
                if SYSTEMD_AVAILABLE:
                    daemon.notify("WATCHDOG=1")

                print(f"⏰ Next check in {self.check_interval // 60} minutes...\n")
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(60)  # brief pause before retry

        logger.info("🛑 Tracker stopped cleanly.")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Multi-league odds tracker")
    parser.add_argument("--once", action="store_true", help="Run once instead of continuously")
    parser.add_argument(
        "--leagues", nargs="+", choices=list(LEAGUES.keys()), help="Specific leagues to track"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Check interval in seconds (default: 3600 = 1 hour)",
    )
    args = parser.parse_args()

    tracker = MultiLeagueTracker(leagues=args.leagues, check_interval=args.interval)

    if args.once:
        tracker.check_all_leagues()
    else:
        tracker.run_continuous()


if __name__ == "__main__":
    main()
