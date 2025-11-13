"""Comprehensive model analysis and feature testing."""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

try:
    from src.feature import build_features
    from src.model import ModelWrapper
    from src.tools.synthetic_data import generate_complete_dataset
except ModuleNotFoundError:  # pragma: no cover - fallback for direct script execution
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from src.feature import build_features
    from src.model import ModelWrapper
    from src.tools.synthetic_data import generate_complete_dataset


def analyze_model():
    """Comprehensive model analysis."""
    print("\n" + "=" * 70)
    print("  MODEL ANALYSIS & FEATURE IMPORTANCE")
    print("=" * 70 + "\n")

    # Load persisted Optuna study (if available)
    study_path = Path("./models/optuna_study.pkl")
    if study_path.exists():
        try:
            study = joblib.load(study_path)
            print("📁 Loaded Optuna study artifact")
            print("   • Storage: sqlite:///./data/optuna.db")
            print(f"   • Study name: {study.study_name}")
            print(f"   • Trials completed: {len(study.trials)}")

            if study.best_trial is not None:
                best_log_loss = -study.best_value
                print(f"   • Best log loss: {best_log_loss:.4f}")
                print("   • Best hyperparameters:")
                for key, value in study.best_params.items():
                    print(f"       - {key}: {value}")
            else:
                print("   ⚠️  Study has no completed trials yet")
        except Exception as exc:  # pragma: no cover - diagnostic output
            print(f"⚠️  Failed to load Optuna study: {exc}")
    else:
        print("⚠️  No Optuna study artifact found. Run the tuning pipeline first.")

    # Generate data
    print("1️⃣  Generating test data...")
    fixtures, odds, results = generate_complete_dataset(n_days=30, games_per_day=10)
    print(f"   Generated {len(fixtures)} matches\n")

    # Build features
    print("2️⃣  Building features...")
    features = build_features(fixtures, odds)
    features = features.merge(results, on="market_id", how="left")
    features["label"] = (features["result"] == "home").astype(int)
    features_clean = features.dropna(subset=["label"])
    print(f"   Features: {len(features_clean.columns)} total\n")

    # Prepare data
    X = features_clean.drop(columns=["label", "market_id", "result"], errors="ignore")
    X_numeric = X.select_dtypes(include=["number"]).fillna(0)
    y = features_clean["label"].values

    print("   Numerical features:")
    for col in X_numeric.columns:
        print(f"     • {col}")
    print()

    # Train model
    print("3️⃣  Training model...")
    model = ModelWrapper()
    model.train(X_numeric.values, y)
    print("   ✅ Model trained\n")

    # Make predictions
    print("4️⃣  Making predictions...")
    y_pred_proba = model.predict_proba(X_numeric.values)[:, 1]
    y_pred = (y_pred_proba > 0.5).astype(int)

    # Calculate metrics
    print("=" * 70)
    print("  PERFORMANCE METRICS")
    print("=" * 70 + "\n")

    accuracy = accuracy_score(y, y_pred)
    brier = brier_score_loss(y, y_pred_proba)
    logloss = log_loss(y, y_pred_proba)
    auc = roc_auc_score(y, y_pred_proba)

    print(f"📊 Accuracy: {accuracy:.2%}")
    print(f"📊 Brier Score: {brier:.4f} (lower is better)")
    print(f"📊 Log Loss: {logloss:.4f} (lower is better)")
    print(f"📊 AUC-ROC: {auc:.4f}")

    # Calibration analysis
    print("\n" + "=" * 70)
    print("  CALIBRATION ANALYSIS")
    print("=" * 70 + "\n")

    prob_true, prob_pred = calibration_curve(y, y_pred_proba, n_bins=10)

    print("Predicted vs Actual:")
    print(f"{'Predicted':<12} {'Actual':<12} {'Difference'}")
    print("-" * 40)
    for pred, true in zip(prob_pred, prob_true):
        diff = abs(pred - true)
        symbol = "✅" if diff < 0.1 else "⚠️"
        print(f"{pred:<12.2%} {true:<12.2%} {diff:>10.2%} {symbol}")

    # Feature importance
    print("\n" + "=" * 70)
    print("  FEATURE IMPORTANCE")
    print("=" * 70 + "\n")

    if hasattr(model.model, "feature_importances_"):
        importances = model.model.feature_importances_
        feature_names = X_numeric.columns

        # Sort by importance
        indices = np.argsort(importances)[::-1]

        print("Top features driving predictions:\n")
        print(f"{'Rank':<6} {'Feature':<30} {'Importance':<12} {'Bar'}")
        print("-" * 70)

        for i, idx in enumerate(indices[:10]):
            importance = importances[idx]
            bar_length = int(importance * 50)
            bar = "█" * bar_length
            print(f"{i+1:<6} {feature_names[idx]:<30} {importance:<12.4f} {bar}")

        print("\n💡 Install matplotlib to generate plots: pip install matplotlib")

    # Prediction distribution
    print("\n" + "=" * 70)
    print("  PREDICTION DISTRIBUTION")
    print("=" * 70 + "\n")

    bins = [0, 0.3, 0.4, 0.5, 0.6, 0.7, 1.0]
    labels = ["<30%", "30-40%", "40-50%", "50-60%", "60-70%", ">70%"]

    pred_bins = pd.cut(y_pred_proba, bins=bins, labels=labels)
    distribution = pred_bins.value_counts().sort_index()

    print("Model confidence distribution:")
    print(f"{'Confidence':<12} {'Count':<8} {'% of Total'}")
    print("-" * 35)
    for conf, count in distribution.items():
        pct = count / len(y_pred_proba) * 100
        bar = "█" * int(pct / 2)
        print(f"{conf:<12} {count:<8} {pct:>6.1f}% {bar}")

    # Betting performance analysis
    print("\n" + "=" * 70)
    print("  BETTING PERFORMANCE ANALYSIS")
    print("=" * 70 + "\n")

    # Simulate betting on different confidence thresholds
    thresholds = [0.50, 0.55, 0.60, 0.65, 0.70]

    print(f"{'Threshold':<12} {'Bets':<8} {'Wins':<8} {'Win Rate':<12} {'Profit'}")
    print("-" * 60)

    # Get odds from features
    home_odds_column = None
    for candidate in ("home", "home_odds"):
        if candidate in features_clean.columns:
            home_odds_column = candidate
            break

    home_odds = None
    if home_odds_column is not None:
        odds_series = pd.to_numeric(features_clean[home_odds_column], errors="coerce")
        if not odds_series.isna().all():
            home_odds = odds_series

    for threshold in thresholds:
        # Select bets above threshold
        bet_mask = y_pred_proba > threshold
        n_bets = bet_mask.sum()

        if n_bets == 0:
            continue

        # Calculate results
        actual_wins = y[bet_mask].sum()
        win_rate = actual_wins / n_bets if n_bets > 0 else 0

        # Simulate profit (assuming unit stakes)
        if home_odds is not None and not home_odds[bet_mask].isna().all():
            odds_subset = home_odds[bet_mask].fillna(2.0)
            profits = np.where(y[bet_mask] == 1, odds_subset - 1, -1)
            total_profit = profits.sum()
            roi = (total_profit / n_bets) * 100
            print(
                f"{threshold:<12.0%} {n_bets:<8} {actual_wins:<8} {win_rate:<12.1%} "
                f"${total_profit:+.2f} ({roi:+.1f}%)"
            )
        else:
            print(f"{threshold:<12.0%} {n_bets:<8} {actual_wins:<8} {win_rate:<12.1%} N/A")

    # Problem diagnosis
    print("\n" + "=" * 70)
    print("  PROBLEM DIAGNOSIS")
    print("=" * 70 + "\n")

    avg_pred = y_pred_proba.mean()
    avg_actual = y.mean()

    print(f"📊 Average predicted probability: {avg_pred:.2%}")
    print(f"📊 Actual home win rate: {avg_actual:.2%}")
    print(f"📊 Bias: {abs(avg_pred - avg_actual):.2%}")

    if abs(avg_pred - avg_actual) > 0.05:
        print("\n⚠️  WARNING: Model shows significant bias!")
        if avg_pred > avg_actual:
            print("   → Model is too optimistic about home wins")
        else:
            print("   → Model is too pessimistic about home wins")

    # Check if model is just predicting mean
    pred_variance = np.var(y_pred_proba)
    print(f"\n📊 Prediction variance: {pred_variance:.4f}")

    if pred_variance < 0.01:
        print("⚠️  WARNING: Model predictions have very low variance!")
        print("   → Model may be just predicting the mean")
        print("   → Need more discriminative features")

    # Recommendations
    print("\n" + "=" * 70)
    print("  RECOMMENDATIONS")
    print("=" * 70 + "\n")

    issues = []

    if brier > 0.25:
        issues.append("❌ High Brier score - poor calibration")
    if accuracy < 0.55:
        issues.append("❌ Low accuracy - model barely better than random")
    if pred_variance < 0.01:
        issues.append("❌ Low prediction variance - model not discriminative")
    if abs(avg_pred - avg_actual) > 0.10:
        issues.append("❌ High bias - model systematically wrong")

    if issues:
        print("Issues identified:")
        for issue in issues:
            print(f"  {issue}")

        print("\nSuggested fixes:")
        print("  1. Add more features (team form, head-to-head, etc.)")
        print("  2. Use real historical data instead of synthetic")
        print("  3. Try different model architectures")
        print("  4. Adjust edge thresholds in betting strategy")
        print("  5. Use ensemble of models")
    else:
        print("✅ Model performance looks good!")
        print("   Consider:")
        print("  • Fine-tuning hyperparameters")
        print("  • Adding domain-specific features")
        print("  • Testing on live data")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    analyze_model()
