"""Paper trading system - track virtual bets without risking real money."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from src.adapters.theodds_api import TheOddsAPIAdapter
    from src.config import settings
    from src.data_fetcher import DataFetcher
    from src.feature import build_features, select_features
    from src.model import ModelWrapper
    from src.paths import PAPER_TRADING_DIR, PAPER_TRADING_FILE
    from src.strategy import apply_bet_filters, find_value_bets
    from src.logging_config import get_logger
except ModuleNotFoundError:  # pragma: no cover - fallback for direct script execution
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from src.adapters.theodds_api import TheOddsAPIAdapter
    from src.config import settings
    from src.data_fetcher import DataFetcher
    from src.feature import build_features, select_features
    from src.model import ModelWrapper
    from src.paths import PAPER_TRADING_DIR, PAPER_TRADING_FILE
    from src.strategy import apply_bet_filters, find_value_bets
    from src.logging_config import get_logger

logger = get_logger(__name__)


class PaperTradingSystem:
    """Paper trading system for tracking virtual bets."""

    def __init__(self, bankroll: float = 10000.0, model_path: str = "models/model.pkl"):
        """Initialize paper trading system.

        Args:
            bankroll: Initial bankroll for the paper trading session.
            model_path: Path to the trained model artifact.
        """

        self.initial_bankroll = bankroll
        self.bankroll = bankroll
        self.model_path = Path(model_path)

        self.results = []
        self.bets = []
        self.paper_dir = PAPER_TRADING_DIR
        self.paper_dir.mkdir(parents=True, exist_ok=True)
        self.load_bets()

        # Load model
        self.model = ModelWrapper(self.model_path)
        try:
            self.model.load(self.model_path)
            logger.info(f"Loaded model from {self.model_path}")
        except Exception as e:  # pragma: no cover - runtime diagnostic
            logger.warning(f"Could not load model: {e}")
            self.model = None

        # Initialize data fetcher
        self.fetcher = DataFetcher(source=TheOddsAPIAdapter(api_key=settings.THEODDS_API_KEY))

    def fetch_opportunities(self):
        """Fetch current betting opportunities."""
        print("\n📥 Fetching current odds...")

        fixtures = self.fetcher.get_fixtures()
        odds = self.fetcher.get_odds(list(fixtures["market_id"]))

        print(f"   ✅ Found {len(fixtures)} upcoming matches")
        print(f"   ✅ {len(odds)} odds entries")

        return fixtures, odds

    def analyze_opportunities(self, fixtures, odds):
        """Analyze opportunities and find value bets."""
        print("\n🔍 Analyzing opportunities...")

        # Build features
        features = build_features(fixtures, odds)

        if self.model is None:
            print("   ⚠️  No model loaded - using default probabilities")
            features["p_win"] = 0.50
        else:
            # Prepare features for prediction
            X = features.drop(columns=["market_id", "result"], errors="ignore")
            X_selected = select_features(X)

            # Make predictions
            predictions = self.model.predict_proba(X_selected.values)[:, 1]
            features["p_win"] = predictions

        # Prepare for value bet detection
        features["odds"] = features.get("home", 2.0)  # Use home odds
        features["selection"] = "home"

        # Find value bets
        value_bets = find_value_bets(
            features,
            proba_col="p_win",
            odds_col="odds",
            bank=self.bankroll,
            min_ev=0.01,  # 1% minimum edge
        )

        # Apply filters
        filtered_bets = apply_bet_filters(
            value_bets, min_ev=0.01, min_confidence=0.55, max_total=10
        )

        print(f"   ✅ Found {len(value_bets)} potential value bets")
        print(f"   ✅ {len(filtered_bets)} bets after filtering")

        return filtered_bets

    def place_paper_bet(self, bet):
        """Record a paper bet."""
        bet_record = {
            "bet_id": len(self.bets) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market_id": bet["market_id"],
            "selection": bet["selection"],
            "home": bet.get("home", "Unknown"),
            "away": bet.get("away", "Unknown"),
            "odds": bet["odds"],
            "stake": bet["stake"],
            "predicted_prob": bet["p"],
            "expected_value": bet["ev"],
            "expected_profit": bet["expected_profit"],
            "status": "pending",
        }

        self.bets.append(bet_record)
        self.save_bets()

        return bet_record

    def save_bets(self):
        """Save bets to JSON file."""
        with open(PAPER_TRADING_FILE, "w") as f:
            json.dump(self.bets, f, indent=2, default=str)

    def load_bets(self):
        """Load bets from JSON file."""
        filepath = PAPER_TRADING_FILE
        if filepath.exists():
            with open(filepath, "r") as f:
                self.bets = json.load(f)

    def settle_bet(self, bet_id, result):
        """Settle a completed bet.

        Args:
            bet_id: ID of the bet to settle
            result: 'win' or 'loss'
        """
        for bet in self.bets:
            if bet["bet_id"] == bet_id and bet["status"] == "pending":
                if result == "win":
                    profit = bet["stake"] * (bet["odds"] - 1)
                else:
                    profit = -bet["stake"]

                bet["status"] = "settled"
                bet["result"] = result
                bet["profit"] = profit
                bet["settled_at"] = datetime.now(timezone.utc).isoformat()

                self.bankroll += profit

                self.results.append(
                    {
                        "bet_id": bet_id,
                        "result": result,
                        "profit": profit,
                        "bankroll_after": self.bankroll,
                    }
                )

                self.save_bets()
                return True

        return False

    def get_stats(self):
        """Get paper trading statistics."""
        if not self.bets:
            return {
                "total_bets": 0,
                "pending": 0,
                "settled": 0,
                "wins": 0,
                "losses": 0,
                "total_staked": 0,
                "total_profit": 0,
                "win_rate": 0,
                "roi": 0,
                "current_bankroll": self.bankroll,
            }

        settled = [b for b in self.bets if b["status"] == "settled"]
        pending = [b for b in self.bets if b["status"] == "pending"]
        wins = [b for b in settled if b["result"] == "win"]
        losses = [b for b in settled if b["result"] == "loss"]

        total_staked = sum(b["stake"] for b in settled)
        total_profit = sum(b["profit"] for b in settled)

        return {
            "total_bets": len(self.bets),
            "pending": len(pending),
            "settled": len(settled),
            "wins": len(wins),
            "losses": len(losses),
            "total_staked": total_staked,
            "total_profit": total_profit,
            "win_rate": len(wins) / len(settled) if settled else 0,
            "roi": (total_profit / total_staked * 100) if total_staked > 0 else 0,
            "current_bankroll": self.bankroll,
            "bankroll_change": self.bankroll - self.initial_bankroll,
            "bankroll_change_pct": (self.bankroll - self.initial_bankroll)
            / self.initial_bankroll
            * 100,
        }

    def display_opportunities(self, bets):
        """Display current betting opportunities."""
        if not bets:
            print("\n❌ No value bets found at this time")
            return

        print("\n" + "=" * 80)
        print("  💎 VALUE BETTING OPPORTUNITIES")
        print("=" * 80)
        print(f"\n🏦 Current Bankroll: ${self.bankroll:,.2f}\n")

        print(f"{'ID':<4} {'Match':<40} {'Odds':<7} {'Prob':<7} {'Edge':<7} {'Stake':<10}")
        print("-" * 80)

        for i, bet in enumerate(bets, 1):
            match = f"{bet.get('home', 'TBD')} vs {bet.get('away', 'TBD')}"
            if len(match) > 38:
                match = match[:35] + "..."

            print(
                f"{i:<4} {match:<40} {bet['odds']:<7.2f} {bet['p']:<7.1%} "
                f"{bet['ev']:<7.1%} ${bet['stake']:<9.2f}"
            )

        total_stake = sum(b["stake"] for b in bets)
        print("-" * 80)
        print(f"{'TOTAL':<52} ${total_stake:,.2f} ({total_stake/self.bankroll:.1%} of bankroll)")
        print("=" * 80 + "\n")

    def run_interactive(self):
        """Run interactive paper trading session."""
        print("\n" + "=" * 80)
        print("  📊 PAPER TRADING SYSTEM")
        print("=" * 80)

        # Load existing bets
        self.load_bets()

        # Fetch opportunities
        fixtures, odds = self.fetch_opportunities()

        # Analyze
        opportunities = self.analyze_opportunities(fixtures, odds)

        # Display
        self.display_opportunities(opportunities)

        if not opportunities:
            return

        # Ask user what to do
        print("Options:")
        print("  [1-N] Place specific bet")
        print("  [A]   Place all bets")
        print("  [S]   Skip")
        print("  [Q]   Quit")

        choice = input("\nYour choice: ").strip().upper()

        if choice == "Q":
            return
        elif choice == "S":
            print("Skipping opportunities...")
            return
        elif choice == "A":
            for bet in opportunities:
                record = self.place_paper_bet(bet)
                print(
                    f"✅ Placed paper bet #{record['bet_id']}: "
                    f"{record['home']} @ {record['odds']} for ${record['stake']:.2f}"
                )
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(opportunities):
                bet = opportunities[idx]
                record = self.place_paper_bet(bet)
                print(
                    f"✅ Placed paper bet #{record['bet_id']}: "
                    f"{record['home']} @ {record['odds']} for ${record['stake']:.2f}"
                )
            else:
                print("Invalid bet number")

        # Show stats
        self.show_stats()

    def show_stats(self):
        """Display statistics."""
        stats = self.get_stats()

        print("\n" + "=" * 80)
        print("  📈 PAPER TRADING STATISTICS")
        print("=" * 80 + "\n")

        print(
            f"💰 Bankroll: ${stats['current_bankroll']:,.2f} "
            f"({stats['bankroll_change']:+.2f}, {stats['bankroll_change_pct']:+.1f}%)"
        )
        print(
            f"📊 Total Bets: {stats['total_bets']} "
            f"(Pending: {stats['pending']}, Settled: {stats['settled']})"
        )

        if stats["settled"] > 0:
            print(f"🏆 Wins: {stats['wins']} | ❌ Losses: {stats['losses']}")
            print(f"📈 Win Rate: {stats['win_rate']:.1%}")
            print(f"💵 Total Staked: ${stats['total_staked']:,.2f}")
            print(f"💰 Total Profit: ${stats['total_profit']:+,.2f}")
            print(f"📊 ROI: {stats['roi']:+.2f}%")

        print("=" * 80 + "\n")


def main():
    """Run paper trading system."""
    import argparse

    parser = argparse.ArgumentParser(description="Paper Trading System")
    parser.add_argument("--bankroll", type=float, default=10000.0, help="Initial bankroll")
    parser.add_argument("--model", type=str, default="models/model.pkl", help="Path to model")
    args = parser.parse_args()

    system = PaperTradingSystem(bankroll=args.bankroll, model_path=args.model)

    system.run_interactive()


if __name__ == "__main__":
    main()
