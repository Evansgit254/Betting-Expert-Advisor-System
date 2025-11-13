"""Test model on real historical data."""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

try:
    from src.backtest import Backtester
    from src.feature import build_features
    from src.model import ModelWrapper
    from src.logging_config import get_logger
except ModuleNotFoundError:  # pragma: no cover - fallback for direct execution
    import os
    import sys

    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from src.backtest import Backtester
    from src.feature import build_features
    from src.model import ModelWrapper
    from src.logging_config import get_logger

logger = get_logger(__name__)


def load_real_data():
    """Load real historical data."""
    data_dir = Path("data/real")

    fixtures = pd.read_csv(data_dir / "fixtures.csv")
    odds = pd.read_csv(data_dir / "odds.csv")
    results = pd.read_csv(data_dir / "results.csv")

    # Parse dates
    fixtures["start"] = pd.to_datetime(fixtures["start"])
    odds["last_update"] = pd.to_datetime(odds["last_update"])

    return fixtures, odds, results


def test_on_real_data():
    """Test model on real historical data."""
    print("\n" + "=" * 70)
    print("  TESTING ON REAL HISTORICAL DATA")
    print("=" * 70 + "\n")

    # Load data
    print("📂 Loading real data...")
    fixtures, odds, results = load_real_data()
    print(f"   ✅ {len(fixtures)} matches loaded")
    print(f"   ✅ Date range: {fixtures['start'].min()} to {fixtures['start'].max()}\n")

    # Split by date (time-series split)
    split_date = pd.to_datetime("2023-08-01")  # Use last season for testing

    train_fixtures = fixtures[fixtures["start"] < split_date]
    test_fixtures = fixtures[fixtures["start"] >= split_date]

    train_ids = set(train_fixtures["market_id"])
    test_ids = set(test_fixtures["market_id"])

    train_odds = odds[odds["market_id"].isin(train_ids)]
    test_odds = odds[odds["market_id"].isin(test_ids)]

    train_results = results[results["market_id"].isin(train_ids)]
    test_results = results[results["market_id"].isin(test_ids)]

    print("📊 Train/Test Split:")
    print(f"   Training: {len(train_fixtures)} matches (before {split_date.date()})")
    print(f"   Testing: {len(test_fixtures)} matches (after {split_date.date()})\n")

    # Build features for training
    print("🔧 Building training features...")
    train_features = build_features(train_fixtures, train_odds)
    train_features = train_features.merge(train_results, on="market_id", how="left")
    train_features["label"] = (train_features["result"] == "home").astype(int)
    train_features_clean = train_features.dropna(subset=["label"])

    # CRITICAL: Remove result columns to prevent data leakage
    X_train = train_features_clean.drop(
        columns=["label", "market_id", "result", "home_score", "away_score"], errors="ignore"
    )
    X_train_numeric = X_train.select_dtypes(include=["number"]).fillna(0)
    y_train = train_features_clean["label"].values

    print(f"   ✅ {len(y_train)} training samples")
    print(f"   ✅ {X_train_numeric.shape[1]} features\n")

    # Train model
    print("🤖 Training model on real data...")
    model = ModelWrapper()
    model.train(X_train_numeric.values, y_train)
    print("   ✅ Model trained\n")

    # Build features for testing
    print("🔧 Building test features...")
    test_features = build_features(test_fixtures, test_odds)
    test_features = test_features.merge(test_results, on="market_id", how="left")
    test_features["label"] = (test_features["result"] == "home").astype(int)
    test_features_clean = test_features.dropna(subset=["label"])

    # CRITICAL: Remove result columns to prevent data leakage
    X_test = test_features_clean.drop(
        columns=["label", "market_id", "result", "home_score", "away_score"], errors="ignore"
    )
    X_test_numeric = X_test.select_dtypes(include=["number"]).fillna(0)
    y_test = test_features_clean["label"].values

    print(f"   ✅ {len(y_test)} test samples\n")

    # Make predictions
    print("🔮 Making predictions...")
    y_pred_proba = model.predict_proba(X_test_numeric.values)[:, 1]
    y_pred = (y_pred_proba > 0.5).astype(int)

    # Calculate metrics
    print("\n" + "=" * 70)
    print("  MODEL PERFORMANCE ON REAL DATA")
    print("=" * 70 + "\n")

    accuracy = accuracy_score(y_test, y_pred)
    brier = brier_score_loss(y_test, y_pred_proba)
    logloss = log_loss(y_test, y_pred_proba)
    auc = roc_auc_score(y_test, y_pred_proba)

    print(f"📊 Accuracy: {accuracy:.2%}")
    print(f"📊 Brier Score: {brier:.4f}")
    print(f"📊 Log Loss: {logloss:.4f}")
    print(f"📊 AUC-ROC: {auc:.4f}")

    # Baseline comparison
    home_win_rate = y_test.mean()
    baseline_acc = max(home_win_rate, 1 - home_win_rate)

    print(f"\n📊 Baseline (predict most frequent): {baseline_acc:.2%}")
    print(f"\n📊 Improvement over baseline: {(accuracy - baseline_acc):.2%}")

    # Confidence analysis
    print("\n" + "=" * 70)
    print("  CONFIDENCE ANALYSIS")
    print("=" * 70 + "\n")

    confidence_bins = [0.0, 0.4, 0.45, 0.5, 0.55, 0.6, 1.0]
    labels = ["<40%", "40-45%", "45-50%", "50-55%", "55-60%", ">60%"]

    test_features_clean["prediction"] = y_pred_proba
    test_features_clean["correct"] = (y_pred == y_test).astype(int)
    test_features_clean["conf_bin"] = pd.cut(y_pred_proba, bins=confidence_bins, labels=labels)

    print(f"{'Confidence':<12} {'Count':<8} {'Win Rate':<12} {'Actual Home %'}")
    print("-" * 60)

    for conf_label in labels:
        mask = test_features_clean["conf_bin"] == conf_label
        if mask.sum() > 0:
            count = mask.sum()
            pred_mean = test_features_clean.loc[mask, "prediction"].mean()
            actual_rate = test_features_clean.loc[mask, "label"].mean()
            diff = abs(pred_mean - actual_rate)

            status = "✅" if diff < 0.05 else "⚠️" if diff < 0.10 else "❌"
            print(f"{conf_label:<12} {count:<8} {pred_mean:<12.1%} {actual_rate:<12.1%} {status}")

    # Backtest on real data
    print("\n" + "=" * 70)
    print("  BACKTESTING ON REAL DATA")
    print("=" * 70 + "\n")

    backtester = Backtester(initial_bankroll=10000.0)
    backtest_summary = backtester.run(test_fixtures, test_odds, test_results)

    print(f"📊 Bets placed: {backtest_summary['total_bets']}")
    print(f"📊 Wins: {backtest_summary['wins']}")
    print(f"📊 Losses: {backtest_summary['losses']}")
    print(f"📊 Win rate: {backtest_summary['win_rate']:.1%}")
    print(f"📊 Total staked: ${backtest_summary.get('total_staked', 0):.2f}")
    print(f"📊 Final bankroll: ${backtest_summary['final_bankroll']:.2f}")
    print(f"📊 Profit/Loss: ${backtest_summary['final_bankroll'] - 10000:.2f}")
    print(f"📊 ROI: {backtest_summary.get('roi', 0):.2%}")

    # Feature importance
    print("\n" + "=" * 70)
    print("  FEATURE IMPORTANCE")
    print("=" * 70 + "\n")

    if hasattr(model.model, "feature_importances_"):
        importances = model.model.feature_importances_
        feature_names = X_train_numeric.columns

        indices = np.argsort(importances)[::-1][:10]

        print("Top 10 most important features:\n")
        for i, idx in enumerate(indices):
            importance = importances[idx]
            bar_length = int(importance * 50)
            bar = "█" * bar_length
            print(f"{i+1:>2}. {feature_names[idx]:<25} {importance:.4f} {bar}")

    # Summary and recommendations
    print("\n" + "=" * 70)
    print("  SUMMARY & RECOMMENDATIONS")
    print("=" * 70 + "\n")

    if accuracy > 0.53:
        print("✅ EXCELLENT: Model beats baseline significantly")
        print("   → Model is ready for live testing")
        print("   → Start with small stakes to validate")
    elif accuracy > 0.50:
        print("✅ GOOD: Model slightly beats baseline")
        print("   → Consider adding more features")
        print("   → Monitor performance carefully")
    else:
        print("⚠️  WARNING: Model doesn't beat baseline")
        print("   → Need more discriminative features")
        print("   → Try different model architectures")

    if backtest_summary["total_bets"] == 0:
        print("\n⚠️  No bets placed in backtest")
        print("   → Edge thresholds may be too conservative")
        print("   → Real odds are efficient - small edges expected")
        print("   → Consider lowering min_edge to 0.01 (1%)")
    elif backtest_summary.get("roi", 0) > 0:
        print(f"\n✅ PROFITABLE: +{backtest_summary.get('roi', 0):.2%} ROI")
        print("   → System shows promise on real data")
        print("   → Continue monitoring on new data")
    else:
        print(f"\n⚠️  UNPROFITABLE: {backtest_summary.get('roi', 0):.2%} ROI")
        print("   → May need tighter bet selection")
        print("   → Consider ensemble methods")

    print("\n" + "=" * 70 + "\n")

    return {"accuracy": accuracy, "brier": brier, "auc": auc, "backtest": backtest_summary}


def main():
    """Run test on real data."""
    results = test_on_real_data()

    # Exit with success if accuracy > 50%
    return 0 if results["accuracy"] > 0.50 else 1


if __name__ == "__main__":
    sys.exit(main())
