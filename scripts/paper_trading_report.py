"""Enhanced paper trading report with detailed analytics."""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    from src.logging_config import get_logger
    from src.paths import PAPER_TRADING_FILE
except ModuleNotFoundError:  # pragma: no cover - fallback for direct execution
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from src.logging_config import get_logger
    from src.paths import PAPER_TRADING_FILE

logger = get_logger(__name__)


class PaperTradingReporter:
    """Generate detailed reports for paper trading performance."""

    def __init__(self, bets_file=None):
        """Initialize reporter."""
        self.bets_file = Path(bets_file) if bets_file else PAPER_TRADING_FILE
        self.bets = self.load_bets()

    def load_bets(self):
        """Load paper trading bets."""
        if not self.bets_file.exists():
            return []

        try:
            with open(self.bets_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading bets: {e}")
            return []

    def get_settled_bets(self):
        """Get only settled bets."""
        return [b for b in self.bets if b.get("status") == "settled"]

    def get_pending_bets(self):
        """Get only pending bets."""
        return [b for b in self.bets if b.get("status") == "pending"]

    def calculate_metrics(self):
        """Calculate performance metrics."""
        settled = self.get_settled_bets()

        if not settled:
            return None

        wins = [b for b in settled if b.get("result") == "win"]
        losses = [b for b in settled if b.get("result") == "loss"]

        total_staked = sum(b["stake"] for b in settled)
        total_profit = sum(b.get("profit", 0) for b in settled)

        # Calculate by confidence bands
        confidence_bands = defaultdict(lambda: {"count": 0, "wins": 0, "staked": 0, "profit": 0})

        for bet in settled:
            conf = bet.get("confidence", 0.5)
            band = self.get_confidence_band(conf)
            confidence_bands[band]["count"] += 1
            confidence_bands[band]["staked"] += bet["stake"]
            confidence_bands[band]["profit"] += bet.get("profit", 0)
            if bet.get("result") == "win":
                confidence_bands[band]["wins"] += 1

        # Calculate by league
        league_stats = defaultdict(lambda: {"count": 0, "wins": 0, "staked": 0, "profit": 0})

        for bet in settled:
            league = bet.get("league", "Unknown")
            league_stats[league]["count"] += 1
            league_stats[league]["staked"] += bet["stake"]
            league_stats[league]["profit"] += bet.get("profit", 0)
            if bet.get("result") == "win":
                league_stats[league]["wins"] += 1

        # Time series data
        df = pd.DataFrame(settled)
        df["placed_at"] = pd.to_datetime(df["placed_at"])
        df["cumulative_profit"] = df["profit"].cumsum()

        return {
            "total_bets": len(self.bets),
            "settled": len(settled),
            "pending": len(self.bets) - len(settled),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(settled) if settled else 0,
            "total_staked": total_staked,
            "total_profit": total_profit,
            "roi": (total_profit / total_staked * 100) if total_staked > 0 else 0,
            "avg_stake": total_staked / len(settled) if settled else 0,
            "avg_odds": sum(b["odds"] for b in settled) / len(settled) if settled else 0,
            "confidence_bands": dict(confidence_bands),
            "league_stats": dict(league_stats),
            "time_series": df[["placed_at", "cumulative_profit"]].to_dict("records")
            if not df.empty
            else [],
        }

    def get_confidence_band(self, confidence):
        """Get confidence band label."""
        if confidence < 0.55:
            return "<55%"
        elif confidence < 0.60:
            return "55-60%"
        elif confidence < 0.65:
            return "60-65%"
        elif confidence < 0.70:
            return "65-70%"
        else:
            return ">70%"

    def generate_report(self):
        """Generate comprehensive report."""
        print("\n" + "=" * 80)
        print("  📊 PAPER TRADING PERFORMANCE REPORT")
        print("=" * 80)
        print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80 + "\n")

        if not self.bets:
            print("  ℹ️  No paper trades recorded yet")
            print("\n" + "=" * 80 + "\n")
            return

        metrics = self.calculate_metrics()

        if not metrics:
            print("  ℹ️  No settled bets yet")
            print(f"  📊 Total bets placed: {len(self.bets)} (all pending)")
            print("\n" + "=" * 80 + "\n")
            return

        # Overall Stats
        print("📈 OVERALL PERFORMANCE")
        print("-" * 80)
        print(f"  Total bets: {metrics['total_bets']}")
        print(f"  Settled: {metrics['settled']} | Pending: {metrics['pending']}")
        print(f"  Wins: {metrics['wins']} | Losses: {metrics['losses']}")
        print(f"  Win Rate: {metrics['win_rate']:.1%}")
        print(f"  Total Staked: ${metrics['total_staked']:.2f}")
        print(f"  Total Profit: ${metrics['total_profit']:+.2f}")
        print(f"  ROI: {metrics['roi']:+.2f}%")
        print(f"  Avg Stake: ${metrics['avg_stake']:.2f}")
        print(f"  Avg Odds: {metrics['avg_odds']:.2f}")
        print()

        # Confidence Analysis
        print("🎯 PERFORMANCE BY CONFIDENCE")
        print("-" * 80)
        print(f"  {'Band':<12} {'Bets':<8} {'Wins':<8} {'Win %':<10} {'Profit':<12} {'ROI'}")
        print("-" * 80)

        for band in ["<55%", "55-60%", "60-65%", "65-70%", ">70%"]:
            if band in metrics["confidence_bands"]:
                stats = metrics["confidence_bands"][band]
                win_rate = stats["wins"] / stats["count"] if stats["count"] > 0 else 0
                roi = (stats["profit"] / stats["staked"] * 100) if stats["staked"] > 0 else 0

                print(
                    f"  {band:<12} {stats['count']:<8} {stats['wins']:<8} "
                    f"{win_rate:<10.1%} ${stats['profit']:<11.2f} {roi:+.1f}%"
                )
        print()

        # League Performance
        if metrics["league_stats"]:
            print("🏆 PERFORMANCE BY LEAGUE")
            print("-" * 80)
            print(f"  {'League':<30} {'Bets':<8} {'Wins':<8} {'Win %':<10} {'ROI'}")
            print("-" * 80)

            for league, stats in sorted(
                metrics["league_stats"].items(), key=lambda x: x[1]["profit"], reverse=True
            ):
                win_rate = stats["wins"] / stats["count"] if stats["count"] > 0 else 0
                roi = (stats["profit"] / stats["staked"] * 100) if stats["staked"] > 0 else 0

                print(
                    f"  {league:<30} {stats['count']:<8} {stats['wins']:<8} "
                    f"{win_rate:<10.1%} {roi:+.1f}%"
                )
            print()

        # Recent Bets
        print("📋 RECENT BETS (Last 10)")
        print("-" * 80)

        recent = sorted(self.bets, key=lambda x: x.get("placed_at", ""), reverse=True)[:10]

        for i, bet in enumerate(recent, 1):
            status = bet.get("status", "unknown")
            result = bet.get("result", "pending")
            profit = bet.get("profit", 0)

            status_icon = "⏳" if status == "pending" else ("✅" if result == "win" else "❌")

            print(
                f"  {i}. {status_icon} {bet.get('home', 'Unknown')} vs {bet.get('away', 'Unknown')}"
            )
            print(
                f"     Odds: {bet['odds']:.2f} | Stake: ${bet['stake']:.2f} | "
                f"Profit: ${profit:+.2f}"
            )

        print()

        # Recommendations
        print("💡 RECOMMENDATIONS")
        print("-" * 80)

        if metrics["settled"] < 20:
            print("  ⚠️  Need more data: Continue paper trading (target: 50+ bets)")
        elif metrics["win_rate"] < 0.52:
            print("  ❌ Win rate too low: Review strategy before live betting")
        elif metrics["roi"] < 2:
            print("  ⚠️  ROI marginal: Continue paper trading to confirm edge")
        else:
            print("  ✅ Performance looks good: Consider micro-stakes testing ($1-5)")

        if metrics["confidence_bands"].get(">70%", {}).get("count", 0) > 0:
            high_conf_roi = (
                metrics["confidence_bands"][">70%"]["profit"]
                / metrics["confidence_bands"][">70%"]["staked"]
                * 100
            )
            if high_conf_roi > 5:
                print("  💎 High confidence bets performing well: Focus on 70%+ bets")

        print()
        print("=" * 80 + "\n")

    def export_to_csv(self, filename="paper_trading_export.csv"):
        """Export bets to CSV for analysis."""
        if not self.bets:
            print("No bets to export")
            return

        df = pd.DataFrame(self.bets)
        df.to_csv(filename, index=False)
        print(f"✅ Exported {len(self.bets)} bets to {filename}")


def main():
    """Main entry point."""
    reporter = PaperTradingReporter()
    reporter.generate_report()

    # Optionally export to CSV
    if len(reporter.bets) > 0:
        export = input("\n📊 Export to CSV? (y/n): ").lower().strip()
        if export == "y":
            reporter.export_to_csv()


if __name__ == "__main__":
    main()
