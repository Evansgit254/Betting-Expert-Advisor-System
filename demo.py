"""Simple demo of the Betting Expert Advisor system."""
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add to path
from src.db import init_db, save_bet, get_session, BetRecord
from src.risk import kelly_fraction, validate_bet
from src.executor import Executor
from src.utils import setup_logging
from src.logging_config import get_logger

setup_logging()
logger = get_logger(__name__)


def demo_complete_workflow():
    """Demonstrate complete betting workflow."""
    print("\n" + "=" * 70)
    print("  BETTING EXPERT ADVISOR - INTERACTIVE DEMO")
    print("=" * 70 + "\n")

    # Initialize database
    print("1️⃣  Initializing database...")
    init_db()
    print("   ✅ Database ready\n")

    # Create sample betting opportunities
    print("2️⃣  Analyzing betting opportunities...")
    opportunities = pd.DataFrame(
        {
            "match": ["Liverpool vs Chelsea", "Man City vs Arsenal", "Spurs vs Man Utd"],
            "market": ["home", "home", "away"],
            "odds": [2.10, 1.75, 2.80],
            "model_prob": [0.52, 0.60, 0.40],  # Model's probability estimate
        }
    )

    # Calculate expected value
    opportunities["expected_value"] = opportunities["model_prob"] * opportunities["odds"] - 1.0
    opportunities["edge"] = opportunities["expected_value"]

    print(f"   Found {len(opportunities)} opportunities:")
    print(opportunities[["match", "odds", "model_prob", "edge"]].to_string(index=False))
    print()

    # Filter for value bets
    print("3️⃣  Identifying value bets (edge > 3%)...")
    value_bets = opportunities[opportunities["edge"] > 0.03].copy()
    print(f"   Found {len(value_bets)} value bets\n")

    if len(value_bets) == 0:
        print("   ⚠️  No value bets found. Lowering threshold...\n")
        value_bets = opportunities[opportunities["edge"] > 0.0].copy()

    # Calculate stakes using Kelly Criterion
    print("4️⃣  Calculating optimal stakes (Kelly Criterion)...")
    bankroll = 10000.0
    print(f"   Bankroll: ${bankroll:,.2f}\n")

    stakes = []
    for _, bet in value_bets.iterrows():
        stake = kelly_fraction(win_prob=bet["model_prob"], odds=bet["odds"], bankroll=bankroll)
        stakes.append(stake)

    value_bets["stake"] = stakes

    print("   Recommended stakes:")
    print(f"   {'Match':<30} {'Odds':<8} {'Stake':<12} {'% of BR'}")
    print("   " + "-" * 60)
    for _, bet in value_bets.iterrows():
        pct = (bet["stake"] / bankroll) * 100
        print(f"   {bet['match']:<30} {bet['odds']:<8.2f} ${bet['stake']:<11.2f} {pct:.2f}%")
    print()

    # Validate bets
    print("5️⃣  Validating bets...")
    validated_bets = []
    for _, bet in value_bets.iterrows():
        is_valid, reason = validate_bet(
            win_prob=bet["model_prob"], odds=bet["odds"], stake=bet["stake"], bankroll=bankroll
        )
        if is_valid:
            validated_bets.append(bet)
            print(f"   ✅ {bet['match']}: {reason}")
        else:
            print(f"   ❌ {bet['match']}: {reason}")
    print()

    # Execute bets (dry run)
    print("6️⃣  Executing bets (DRY RUN MODE)...")
    executor = Executor()
    executed_count = 0
    bet_ids = []

    for bet in validated_bets:
        bet_data = {
            "market_id": f"demo_{bet['match'].replace(' ', '_')}",
            "selection": f"{bet['match']} - {bet['market']}",
            "stake": bet["stake"],
            "odds": bet["odds"],
            "confidence": bet["model_prob"],
            "edge": bet["edge"],
        }

        result = executor.execute(bet_data, dry_run=True)
        if result.get("status") in ["accepted", "simulated", "dry_run"]:
            executed_count += 1
            if "db_id" in result:
                bet_ids.append(result["db_id"])
            print(f"   ✅ {bet['match']}: ${bet['stake']:.2f} @ {bet['odds']}")

    total_staked = sum(bet["stake"] for bet in validated_bets)
    print(f"\n   Total bets: {executed_count}")
    print(f"   Total staked: ${total_staked:.2f}\n")

    # Query database
    print("7️⃣  Checking database...")
    with get_session() as session:
        recent_bets = session.query(BetRecord).filter(BetRecord.market_id.like("demo_%")).all()
        print(f"   Found {len(recent_bets)} demo bets in database")

        if recent_bets:
            print("\n   Recent bets:")
            print(f"   {'ID':<5} {'Market':<30} {'Stake':<12} {'Odds':<8} {'Result'}")
            print("   " + "-" * 70)
            for bet in recent_bets[:5]:
                result_str = bet.result if bet.result else "pending"
                print(
                    f"   {bet.id:<5} {bet.market_id:<30} ${bet.stake:<11.2f} {bet.odds:<8.2f} {result_str}"
                )
    print()

    # Simulate results (for demo)
    print("8️⃣  Simulating bet results...")
    np.random.seed(42)
    total_profit = 0.0

    with get_session() as session:
        for bet_id in bet_ids:
            bet = session.query(BetRecord).filter(BetRecord.id == bet_id).first()
            if bet and not bet.result:
                # Simulate outcome based on probability
                win = np.random.random() < 0.55  # Slight advantage

                if win:
                    profit = bet.stake * (bet.odds - 1)
                    result = "win"
                else:
                    profit = -bet.stake
                    result = "loss"

                total_profit += profit

                # Update in database
                bet.result = result
                bet.profit_loss = profit
                bet.settled_at = datetime.utcnow()
                session.commit()

                status_icon = "🎉" if win else "❌"
                print(f"   {status_icon} {bet.market_id}: {result.upper()} - P&L: ${profit:+.2f}")

    print(f"\n   Total P&L: ${total_profit:+.2f}")
    roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
    print(f"   ROI: {roi:+.2f}%\n")

    # Final summary
    print("=" * 70)
    print("  DEMO SUMMARY")
    print("=" * 70)
    print(f"  💰 Starting Bankroll: ${bankroll:,.2f}")
    print(f"  📊 Opportunities Analyzed: {len(opportunities)}")
    print(f"  ✅ Value Bets Found: {len(value_bets)}")
    print(f"  🎯 Bets Executed: {executed_count}")
    print(f"  💵 Total Staked: ${total_staked:.2f}")
    print(f"  📈 Total Profit/Loss: ${total_profit:+.2f}")
    print(f"  📊 ROI: {roi:+.2f}%")
    print(f"  💰 Final Bankroll: ${bankroll + total_profit:,.2f}")
    print("=" * 70 + "\n")

    print("✅ Demo complete! Check the database:")
    print("   python scripts/verify_db.py")
    print("\n🎯 Your system is ready to use!")


if __name__ == "__main__":
    try:
        demo_complete_workflow()
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
