"""Complete ML betting pipeline demonstration."""
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from src.db import BetRecord, handle_db_errors, init_db
from src.executor import Executor
from src.feature import build_features
from src.logging_config import get_logger
from src.model import ModelWrapper
from src.risk import kelly_fraction
from src.strategy import find_value_bets
from src.tools.synthetic_data import generate_complete_dataset

logger = get_logger(__name__)


def ml_betting_demo():
    """Demonstrate complete ML-powered betting system."""
    print("\n" + "=" * 70)
    print("  ML-POWERED BETTING SYSTEM - COMPLETE DEMO")
    print("=" * 70 + "\n")

    # Initialize
    init_db()
    bankroll = 10000.0

    # Step 1: Generate training data
    print("1️⃣  Generating synthetic training data...")
    print("   Period: 180 days")
    print("   Games: ~10 per day\n")

    fixtures, odds, results = generate_complete_dataset(n_days=180, games_per_day=10)
    print(f"   ✅ Generated {len(fixtures)} matches")
    print(f"   ✅ Generated {len(odds)} odds entries")
    print(f"   ✅ Generated {len(results)} results\n")

    # Step 2: Build features
    print("2️⃣  Engineering features...")
    features = build_features(fixtures, odds)
    features = features.merge(results, on="market_id", how="left")
    print(f"   ✅ Created {len(features.columns)} features")
    print(
        f"   Features: {', '.join([c for c in features.columns if c.startswith('implied_') or c.startswith('odds_')])}\n"
    )

    # Step 3: Train model
    print("3️⃣  Training ML model...")
    features["label"] = (features["result"] == "home").astype(int)
    features_clean = features.dropna(subset=["label"])

    model = ModelWrapper()
    labels = features_clean["label"].values
    features_only = features_clean.drop(columns=["label", "market_id", "result"], errors="ignore")
    X = features_only.select_dtypes(include=["number"]).fillna(0).values

    print(f"   Training samples: {len(X)}")
    print(f"   Features used: {X.shape[1]}")

    model.train(X, labels)
    print(f"   ✅ Model trained and saved\n")

    # Step 4: Generate test data (new unseen matches)
    print("4️⃣  Generating test data (new matches)...")
    test_fixtures, test_odds, test_results = generate_complete_dataset(n_days=7, games_per_day=10)
    print(f"   ✅ Generated {len(test_fixtures)} test matches\n")

    # Step 5: Build features for test data
    print("5️⃣  Engineering test features...")
    test_features = build_features(test_fixtures, test_odds)
    test_X = test_features.drop(columns=["market_id"], errors="ignore")
    test_X = test_X.select_dtypes(include=["number"]).fillna(0).values
    print(f"   ✅ Test features ready\n")

    # Step 6: Make predictions
    print("6️⃣  Making predictions...")
    predictions = model.predict_proba(test_X)
    test_features["p_home_win"] = predictions[:, 1]

    # Get actual odds for home selection
    home_odds = test_odds[test_odds["selection"] == "home"].copy()
    home_odds = home_odds.drop_duplicates(subset=["market_id"], keep="first")

    test_features = test_features.merge(
        home_odds[["market_id", "odds"]], on="market_id", how="left"
    )
    test_features = test_features.rename(columns={"odds": "home_odds"})

    print(f"   ✅ Predictions made for {len(test_features)} matches")
    print(f"   Average predicted probability: {test_features['p_home_win'].mean():.2%}\n")

    # Step 7: Find value bets
    print("7️⃣  Identifying value bets...")

    # Calculate expected value
    test_features["expected_value"] = test_features["p_home_win"] * test_features["home_odds"] - 1.0
    test_features["edge"] = test_features["expected_value"]

    # Filter for value (EV > 3%)
    value_bets = test_features[test_features["edge"] > 0.03].copy()

    if len(value_bets) == 0:
        print("   No strong value bets found. Lowering threshold to 0%...")
        value_bets = test_features[test_features["edge"] > 0.0].copy()

    value_bets = value_bets.head(10)  # Top 10
    print(f"   ✅ Found {len(value_bets)} value betting opportunities\n")

    # Step 8: Calculate stakes
    print("8️⃣  Calculating optimal stakes (Kelly Criterion)...")
    print(f"   Bankroll: ${bankroll:,.2f}\n")

    print(f"   {'Match ID':<15} {'Odds':<8} {'Model Prob':<12} {'Edge':<8} {'Stake'}")
    print("   " + "-" * 65)

    stakes = []
    for _, bet in value_bets.iterrows():
        stake = kelly_fraction(win_prob=bet["p_home_win"], odds=bet["home_odds"], bankroll=bankroll)
        stakes.append(stake)
        print(
            f"   {bet['market_id']:<15} {bet['home_odds']:<8.2f} {bet['p_home_win']:<12.2%} {bet['edge']:<8.2%} ${stake:.2f}"
        )

    value_bets["stake"] = stakes
    total_staked = sum(stakes)
    print(
        f"\n   Total to stake: ${total_staked:.2f} ({total_staked/bankroll*100:.2f}% of bankroll)\n"
    )

    # Step 9: Execute bets (dry run)
    print("9️⃣  Executing bets (DRY RUN)...")
    executor = Executor()
    executed_bets = []

    for _, bet in value_bets.iterrows():
        bet_data = {
            "market_id": bet["market_id"],
            "selection": "home",
            "stake": bet["stake"],
            "odds": bet["home_odds"],
            "confidence": bet["p_home_win"],
            "edge": bet["edge"],
        }

        result = executor.execute(bet_data, dry_run=True)
        if result.get("status") in ["accepted", "simulated", "dry_run"]:
            executed_bets.append(
                {
                    "db_id": result.get("db_id"),
                    "market_id": bet["market_id"],
                    "stake": bet["stake"],
                    "odds": bet["home_odds"],
                    "p_win": bet["p_home_win"],
                }
            )

    print(f"   ✅ Executed {len(executed_bets)} bets\n")

    # Step 10: Simulate outcomes
    print("🔟  Simulating outcomes...")
    test_features_with_results = test_features.merge(test_results, on="market_id", how="left")

    total_profit = 0.0
    wins = 0
    losses = 0

    print(f"\n   {'Match ID':<15} {'Stake':<10} {'Odds':<8} {'Result':<10} {'P&L'}")
    print("   " + "-" * 60)

    for bet in executed_bets:
        actual_result = (
            test_features_with_results[test_features_with_results["market_id"] == bet["market_id"]][
                "result"
            ].iloc[0]
            if len(
                test_features_with_results[
                    test_features_with_results["market_id"] == bet["market_id"]
                ]
            )
            > 0
            else None
        )

        if actual_result == "home":
            profit = bet["stake"] * (bet["odds"] - 1)
            result_str = "WIN ✅"
            wins += 1
        else:
            profit = -bet["stake"]
            result_str = "LOSS ❌"
            losses += 1

        total_profit += profit
        print(
            f"   {bet['market_id']:<15} ${bet['stake']:<9.2f} {bet['odds']:<8.2f} {result_str:<10} ${profit:+.2f}"
        )

    # Final summary
    win_rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
    roi = total_profit / total_staked * 100 if total_staked > 0 else 0
    final_bankroll = bankroll + total_profit

    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    print(f"  📊 Matches Analyzed: {len(test_features)}")
    print(f"  🎯 Value Bets Found: {len(value_bets)}")
    print(f"  ✅ Bets Executed: {len(executed_bets)}")
    print(f"  💵 Total Staked: ${total_staked:.2f}")
    print(f"  🏆 Wins: {wins}")
    print(f"  ❌ Losses: {losses}")
    print(f"  📈 Win Rate: {win_rate:.1f}%")
    print(f"  💰 Total Profit/Loss: ${total_profit:+.2f}")
    print(f"  📊 ROI: {roi:+.2f}%")
    print(f"  💰 Starting Bankroll: ${bankroll:,.2f}")
    print(f"  💰 Final Bankroll: ${final_bankroll:,.2f}")
    print(f"  📈 Bankroll Change: {(final_bankroll - bankroll) / bankroll * 100:+.2f}%")
    print("=" * 70 + "\n")

    # Model evaluation
    print("🔬 MODEL EVALUATION")
    print("-" * 70)
    actual_outcomes = []
    predicted_probs = []

    for bet in executed_bets:
        actual = (
            test_features_with_results[test_features_with_results["market_id"] == bet["market_id"]][
                "result"
            ].iloc[0]
            == "home"
            if len(
                test_features_with_results[
                    test_features_with_results["market_id"] == bet["market_id"]
                ]
            )
            > 0
            else False
        )

        actual_outcomes.append(1 if actual else 0)
        predicted_probs.append(bet["p_win"])

    if actual_outcomes:
        # Brier score (lower is better, 0 = perfect, 0.25 = random)
        brier = sum((p - a) ** 2 for p, a in zip(predicted_probs, actual_outcomes)) / len(
            actual_outcomes
        )

        # Log loss
        log_loss = -sum(
            a * np.log(max(p, 1e-15)) + (1 - a) * np.log(max(1 - p, 1e-15))
            for a, p in zip(actual_outcomes, predicted_probs)
        ) / len(actual_outcomes)

        accuracy = (
            sum(1 for p, a in zip(predicted_probs, actual_outcomes) if (p > 0.5) == a)
            / len(actual_outcomes)
            * 100
        )

        print(f"  Brier Score: {brier:.4f} (lower is better)")
        print(f"  Log Loss: {log_loss:.4f} (lower is better)")
        print(f"  Accuracy: {accuracy:.1f}%")
        print(f"  Calibration: {'Good ✅' if brier < 0.25 else 'Needs improvement ⚠️'}")

    print("\n✅ Demo complete!")
    print("\n💡 Next steps:")
    print("   • Train on real historical data")
    print("   • Integrate with live odds API")
    print("   • Monitor model performance")
    print("   • Retrain periodically with new data")


if __name__ == "__main__":
    try:
        ml_betting_demo()
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
