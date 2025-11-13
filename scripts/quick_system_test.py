"""Quick system integration test to verify all components work together."""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.backtest import Backtester  # noqa: E402
from src.db import BetRecord, handle_db_errors, init_db, save_bet, update_bet_result  # noqa: E402
from src.executor import Executor  # noqa: E402
from src.risk import kelly_fraction, validate_bet  # noqa: E402


def test_complete_workflow():
    """Test complete betting workflow."""
    print("\n" + "=" * 70)
    print("  BETTING EXPERT ADVISOR - QUICK SYSTEM TEST")
    print("=" * 70 + "\n")

    results = {}

    # Test 1: Database
    print("1. Testing Database...")
    try:
        init_db()
        with handle_db_errors() as session:
            count = session.query(BetRecord).count()
        print(f"   ✅ Database working ({count} existing bets)")
        results["database"] = True
    except Exception as e:
        print(f"   ❌ Database failed: {e}")
        results["database"] = False

    # Test 2: Risk Management
    print("\n2. Testing Risk Management...")
    try:
        bankroll = 10000.0
        stake = kelly_fraction(win_prob=0.55, odds=2.0, bankroll=bankroll)
        is_valid, msg = validate_bet(win_prob=0.55, odds=2.0, stake=stake, bankroll=bankroll)
        print(f"   Kelly Stake: ${stake:.2f} ({stake/bankroll*100:.2f}% of bankroll)")
        print(f"   Validation: {msg}")
        print("   ✅ Risk management working")
        results["risk"] = True
    except Exception as e:
        print(f"   ❌ Risk management failed: {e}")
        results["risk"] = False

    # Test 3: Bet Execution
    print("\n3. Testing Bet Execution...")
    try:
        executor = Executor()
        test_bet = {
            "market_id": "quick_test_001",
            "selection": "Test Team",
            "stake": 100.0,
            "odds": 2.5,
        }
        result = executor.execute(test_bet, dry_run=True)
        print(f"   Status: {result.get('status', 'unknown')}")
        if "db_id" in result:
            print(f"   Saved to DB: ID {result['db_id']}")
        print("   ✅ Bet execution working")
        results["execution"] = True
    except Exception as e:
        print(f"   ❌ Bet execution failed: {e}")
        results["execution"] = False

    # Test 4: Database Persistence
    print("\n4. Testing Database Persistence...")
    try:
        # Save a bet
        bet_record = save_bet(
            market_id="quick_test_db_001",
            selection="DB Test",
            stake=50.0,
            odds=2.0,
            is_dry_run=True,
        )
        bet_id = bet_record.id
        print(f"   Bet saved: ID {bet_id}")

        # Update it
        success = update_bet_result(bet_id, result="win", profit_loss=50.0)
        print(f"   Bet updated: {success}")

        # Query it
        with handle_db_errors() as session:
            bet = session.query(BetRecord).filter(BetRecord.id == bet_id).first()
            if bet:
                print(f"   Retrieved: {bet.market_id} - Result: {bet.result}")

        print("   ✅ Database persistence working")
        results["persistence"] = True
    except Exception as e:
        print(f"   ❌ Database persistence failed: {e}")
        import traceback

        traceback.print_exc()
        results["persistence"] = False

    # Test 5: Backtesting
    print("\n5. Testing Backtesting Engine...")
    try:
        backtester = Backtester(initial_bankroll=10000.0)

        # Create sample historical data
        np.random.seed(42)
        n = 20

        # Fixtures
        fixtures = pd.DataFrame(
            {
                "market_id": [f"H{i}" for i in range(n)],
                "home_team": [f"Team{i}" for i in range(n)],
                "away_team": [f"Team{i+20}" for i in range(n)],
            }
        )

        # Odds - format expected by build_features
        odds_list = []
        for i in range(n):
            market_id = f"H{i}"
            home_odd = np.random.uniform(1.5, 3.5)
            away_odd = np.random.uniform(1.5, 3.5)
            odds_list.extend(
                [
                    {
                        "market_id": market_id,
                        "selection": "home",
                        "odds": home_odd,
                        "bookmaker": "test",
                    },
                    {
                        "market_id": market_id,
                        "selection": "away",
                        "odds": away_odd,
                        "bookmaker": "test",
                    },
                ]
            )
        odds_df = pd.DataFrame(odds_list)

        # Results
        results_df = pd.DataFrame(
            {"market_id": fixtures["market_id"], "result": np.random.choice(["home", "away"], n)}
        )

        # Run backtest
        summary = backtester.run(fixtures, odds_df, results_df)

        print(f"   Bets: {summary.get('total_bets', 0)}")
        print(f"   Winners: {summary.get('winners', 0)}")
        print(f"   Win Rate: {summary.get('win_rate', 0):.1%}")
        print(f"   Final Bankroll: ${summary.get('final_bankroll', 10000):.2f}")
        print(f"   ROI: {summary.get('roi', 0):.2%}")
        print("   ✅ Backtesting working")
        results["backtesting"] = True
    except Exception as e:
        print(f"   ❌ Backtesting failed: {e}")
        import traceback

        traceback.print_exc()
        results["backtesting"] = False

    # Summary
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for name, status in results.items():
        symbol = "✅" if status else "❌"
        print(f"  {symbol} {name.title()}")

    print(f"\n  Result: {passed}/{total} tests passed ({passed/total*100:.0f}%)")

    if passed == total:
        print("  🎉 ALL SYSTEMS OPERATIONAL!")
    elif passed >= total * 0.75:
        print("  ✅ SYSTEM WORKING (minor issues)")
    else:
        print("  ⚠️  SYSTEM NEEDS ATTENTION")

    print("=" * 70 + "\n")

    return passed == total


if __name__ == "__main__":
    success = test_complete_workflow()
    sys.exit(0 if success else 1)
