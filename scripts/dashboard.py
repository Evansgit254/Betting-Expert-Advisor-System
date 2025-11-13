"""Simple monitoring dashboard for betting system."""
import json
import os
import sys
from datetime import datetime

try:
    from src.cache import CachedFixture, CachedOdds
    from src.db import BetRecord, ModelMetadata, handle_db_errors
    from src.logging_config import get_logger
    from src.paths import PAPER_TRADING_FILE
except ModuleNotFoundError:  # pragma: no cover - fallback for direct execution
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from src.cache import CachedFixture, CachedOdds
    from src.db import BetRecord, ModelMetadata, handle_db_errors
    from src.logging_config import get_logger
    from src.paths import PAPER_TRADING_FILE

logger = get_logger(__name__)


class Dashboard:
    """Simple text-based monitoring dashboard."""

    def __init__(self):
        """Initialize dashboard."""
        self.paper_trading_file = PAPER_TRADING_FILE

    def get_cache_stats(self):
        """Get cache statistics."""
        with handle_db_errors() as session:
            fixtures_count = session.query(CachedFixture).count()
            odds_count = session.query(CachedOdds).count()

            # Get age info
            if fixtures_count > 0:
                oldest_fixture = (
                    session.query(CachedFixture).order_by(CachedFixture.fetched_at.asc()).first()
                )
                newest_fixture = (
                    session.query(CachedFixture).order_by(CachedFixture.fetched_at.desc()).first()
                )

                fixture_age = {
                    "oldest": oldest_fixture.fetched_at if oldest_fixture else None,
                    "newest": newest_fixture.fetched_at if newest_fixture else None,
                }
            else:
                fixture_age = None

            return {"fixtures": fixtures_count, "odds": odds_count, "fixture_age": fixture_age}

    def get_betting_stats(self):
        """Get betting statistics from database."""
        with handle_db_errors() as session:
            total_bets = session.query(BetRecord).count()

            if total_bets == 0:
                return None

            # Get settled bets
            settled = session.query(BetRecord).filter(BetRecord.result.isnot(None)).all()

            wins = [b for b in settled if b.result == "win"]
            losses = [b for b in settled if b.result == "loss"]

            total_staked = sum(b.stake for b in settled)
            total_profit = sum(b.profit_loss or 0 for b in settled)

            return {
                "total": total_bets,
                "settled": len(settled),
                "pending": total_bets - len(settled),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(settled) if settled else 0,
                "total_staked": total_staked,
                "total_profit": total_profit,
                "roi": (total_profit / total_staked * 100) if total_staked > 0 else 0,
            }

    def get_paper_trading_stats(self):
        """Get paper trading statistics."""
        if not self.paper_trading_file.exists():
            return None

        try:
            with open(self.paper_trading_file, "r") as f:
                bets = json.load(f)

            if not bets:
                return None

            settled = [b for b in bets if b["status"] == "settled"]
            pending = [b for b in bets if b["status"] == "pending"]
            wins = [b for b in settled if b.get("result") == "win"]
            losses = [b for b in settled if b.get("result") == "loss"]

            total_staked = sum(b["stake"] for b in settled)
            total_profit = sum(b.get("profit", 0) for b in settled)

            return {
                "total": len(bets),
                "settled": len(settled),
                "pending": len(pending),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(settled) if settled else 0,
                "total_staked": total_staked,
                "total_profit": total_profit,
                "roi": (total_profit / total_staked * 100) if total_staked > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Error loading paper trading stats: {e}")
            return None

    def get_model_info(self):
        """Get latest model information."""
        with handle_db_errors() as session:
            latest_model = (
                session.query(ModelMetadata).order_by(ModelMetadata.trained_at.desc()).first()
            )

            if not latest_model:
                return None

            return {
                "name": latest_model.model_name,
                "version": latest_model.version,
                "trained_at": latest_model.trained_at,
                "metrics": latest_model.metrics,
            }

    def display(self):
        """Display dashboard."""
        print("\n" + "=" * 80)
        print("  📊 BETTING SYSTEM DASHBOARD")
        print("=" * 80)
        print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80 + "\n")

        # Model Info
        print("🤖 MODEL STATUS")
        print("-" * 80)
        model_info = self.get_model_info()
        if model_info:
            print(f"  Name: {model_info['name']}")
            print(f"  Version: {model_info['version']}")
            print(f"  Trained: {model_info['trained_at'].strftime('%Y-%m-%d %H:%M:%S')}")
            if model_info["metrics"]:
                metrics = model_info["metrics"]
                if "accuracy" in metrics:
                    print(f"  Accuracy: {metrics['accuracy']:.2%}")
                if "brier" in metrics:
                    print(f"  Brier Score: {metrics['brier']:.4f}")
        else:
            print("  ⚠️  No model information available")
        print()

        # Cache Stats
        print("💾 CACHE STATUS")
        print("-" * 80)
        cache_stats = self.get_cache_stats()
        print(f"  Fixtures cached: {cache_stats['fixtures']}")
        print(f"  Odds cached: {cache_stats['odds']}")
        if cache_stats["fixture_age"]:
            age = datetime.now() - cache_stats["fixture_age"]["newest"]
            print(f"  Last update: {age.seconds // 60} minutes ago")
        print()

        # Paper Trading
        print("📝 PAPER TRADING")
        print("-" * 80)
        paper_stats = self.get_paper_trading_stats()
        if paper_stats:
            print(
                f"  Total bets: {paper_stats['total']} "
                f"(Pending: {paper_stats['pending']}, Settled: {paper_stats['settled']})"
            )
            if paper_stats["settled"] > 0:
                print(f"  Wins/Losses: {paper_stats['wins']}/{paper_stats['losses']}")
                print(f"  Win rate: {paper_stats['win_rate']:.1%}")
                print(f"  Total staked: ${paper_stats['total_staked']:.2f}")
                print(f"  Total profit: ${paper_stats['total_profit']:+.2f}")
                print(f"  ROI: {paper_stats['roi']:+.2f}%")
        else:
            print("  No paper trades yet")
        print()

        # Real Betting
        print("💰 LIVE BETTING")
        print("-" * 80)
        betting_stats = self.get_betting_stats()
        if betting_stats:
            print(
                f"  Total bets: {betting_stats['total']} "
                f"(Pending: {betting_stats['pending']}, Settled: {betting_stats['settled']})"
            )
            if betting_stats["settled"] > 0:
                print(f"  Wins/Losses: {betting_stats['wins']}/{betting_stats['losses']}")
                print(f"  Win rate: {betting_stats['win_rate']:.1%}")
                print(f"  Total staked: ${betting_stats['total_staked']:.2f}")
                print(f"  Total profit: ${betting_stats['total_profit']:+.2f}")
                print(f"  ROI: {betting_stats['roi']:+.2f}%")
        else:
            print("  No live bets yet")
        print()

        # Quick Actions
        print("🚀 QUICK ACTIONS")
        print("-" * 80)
        print("  python scripts/paper_trading.py     - Paper trade")
        print("  python scripts/live_tracker.py --once - Check opportunities")
        print("  python scripts/analyze_model.py     - Analyze model")
        print("  python scripts/check_cache.py       - Cache stats")
        print()

        print("=" * 80 + "\n")


def main():
    """Run dashboard."""
    dashboard = Dashboard()
    dashboard.display()


if __name__ == "__main__":
    main()
