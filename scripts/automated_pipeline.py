"""Automated training, testing, and deployment pipeline."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

try:
    from src.backtest import Backtester
    from src.db import ModelMetadata, get_session
    from src.feature import build_features
    from src.logging_config import get_logger
    from src.ml_pipeline import MLPipeline
    from src.model import ModelWrapper
    from src.paths import RESULTS_DIR
    from src.tools.synthetic_data import generate_complete_dataset
except ModuleNotFoundError:  # pragma: no cover - fallback for direct script execution
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from src.backtest import Backtester
    from src.db import ModelMetadata, get_session
    from src.feature import build_features
    from src.logging_config import get_logger
    from src.ml_pipeline import MLPipeline
    from src.model import ModelWrapper
    from src.paths import RESULTS_DIR
    from src.tools.synthetic_data import generate_complete_dataset

logger = get_logger(__name__)


class AutomatedPipeline:
    """Automated ML pipeline for continuous improvement."""

    def __init__(self):
        """Initialize automated pipeline."""
        self.results = {}
        self.output_dir = RESULTS_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def _prepare_training_data(self, n_days: int):
        """Generate synthetic data and build training features."""
        train_fixtures, train_odds, train_results = generate_complete_dataset(
            n_days=n_days, games_per_day=10
        )

        train_features = build_features(train_fixtures, train_odds)
        train_features = train_features.merge(train_results, on="market_id", how="left")
        train_features["label"] = (train_features["result"] == "home").astype(int)
        train_features_clean = train_features.dropna(subset=["label"])

        X_train = train_features_clean.drop(
            columns=["label", "market_id", "result"], errors="ignore"
        )
        X_train_numeric = X_train.select_dtypes(include=["number"]).fillna(0)
        y_train = train_features_clean["label"].values

        return train_fixtures, train_odds, train_results, X_train_numeric, y_train

    def run_tuning_only(self, n_days: int = 180, n_trials: int = 20, n_splits: int = 5):
        """Run hyperparameter tuning only, persisting Optuna study."""
        print("\n" + "=" * 70)
        print("  OPTUNA TUNING ONLY")
        print("=" * 70 + "\n")

        print("📊 STEP 1: Generating training data...")
        (
            train_fixtures,
            train_odds,
            train_results,
            X_train_numeric,
            y_train,
        ) = self._prepare_training_data(n_days)
        print(f"   ✅ Generated {len(train_fixtures)} training matches")
        print(f"   ✅ Numerical feature shape: {X_train_numeric.shape}\n")

        print("🤖 STEP 2: Running hyperparameter optimization...")
        pipeline = MLPipeline()
        pipeline.train_with_cv(
            X_train_numeric,
            y_train,
            n_splits=n_splits,
            n_trials=n_trials,
        )

        self.results["training"] = {
            "n_features": X_train_numeric.shape[1],
            "n_samples": len(y_train),
            "feature_names": list(X_train_numeric.columns),
        }
        self.results["optuna"] = {
            "best_params": pipeline.best_params,
        }

        print("   ✅ Study persisted to data/optuna.db")
        print("   ✅ Serialized study saved to models/optuna_study.pkl")
        print("\n" + "=" * 70)
        print("  TUNING SUMMARY")
        print("=" * 70 + "\n")
        print(f"✅ Trials completed: {n_trials}")
        print(f"✅ Best parameters: {pipeline.best_params}")
        print("\n" + "=" * 70 + "\n")

        return pipeline

    def run_full_pipeline(self, advanced=True, n_days=180):
        """Run complete pipeline: train -> validate -> backtest -> save."""
        print("\n" + "=" * 70)
        print("  AUTOMATED ML PIPELINE")
        print("=" * 70 + "\n")

        # Step 1: Generate data
        print("📊 STEP 1: Generating training data...")
        (
            train_fixtures,
            train_odds,
            train_results,
            X_train_numeric,
            y_train,
        ) = self._prepare_training_data(n_days)
        print(f"   ✅ Generated {len(train_fixtures)} training matches\n")

        # Step 2: Feature summary
        print("🔧 STEP 2: Feature engineering...")
        print(f"   ✅ Features: {X_train_numeric.shape[1]} numerical features")
        print(f"   ✅ Samples: {len(y_train)} training examples\n")

        # Step 3: Train model
        print("🤖 STEP 3: Training model...")
        if advanced:
            print("   Using advanced pipeline with hyperparameter optimization...")
            pipeline = MLPipeline()
            pipeline.train_with_cv(
                X_train_numeric, y_train, n_splits=5, n_trials=10  # Reduced for speed
            )
            model = pipeline.model
            print("   ✅ Advanced model trained with hyperparameter tuning")
        else:
            print("   Using standard model...")
            model = ModelWrapper()
            model.train(X_train_numeric.values, y_train)
            print("   ✅ Model trained")

        self.results["training"] = {
            "n_features": X_train_numeric.shape[1],
            "n_samples": len(y_train),
            "feature_names": list(X_train_numeric.columns),
        }
        print()

        # Step 4: Validation
        print("✅ STEP 4: Validation on hold-out set...")
        test_fixtures, test_odds, test_results = generate_complete_dataset(
            n_days=30, games_per_day=10
        )

        test_features = build_features(test_fixtures, test_odds)
        test_features = test_features.merge(test_results, on="market_id", how="left")
        test_features["label"] = (test_features["result"] == "home").astype(int)
        test_features_clean = test_features.dropna(subset=["label"])

        X_test = test_features_clean.drop(columns=["label", "market_id", "result"], errors="ignore")
        X_test_numeric = X_test.select_dtypes(include=["number"]).fillna(0)
        y_test = test_features_clean["label"].values

        # Handle both ModelWrapper and raw LightGBM Booster
        if hasattr(model, "predict_proba"):
            y_pred_proba = model.predict_proba(X_test_numeric.values)[:, 1]
        else:
            # Raw LightGBM Booster from MLPipeline
            y_pred_proba = model.predict(X_test_numeric.values)

        y_pred = (y_pred_proba > 0.5).astype(int)

        from sklearn.metrics import accuracy_score, brier_score_loss, log_loss

        accuracy = accuracy_score(y_test, y_pred)
        brier = brier_score_loss(y_test, y_pred_proba)
        logloss = log_loss(y_test, y_pred_proba)

        print(f"   📊 Accuracy: {accuracy:.2%}")
        print(f"   📊 Brier Score: {brier:.4f}")
        print(f"   📊 Log Loss: {logloss:.4f}")

        self.results["validation"] = {
            "accuracy": accuracy,
            "brier": brier,
            "log_loss": logloss,
            "n_test_samples": len(y_test),
        }
        print()

        # Step 5: Backtest
        print("📈 STEP 5: Backtesting strategy...")
        backtester = Backtester(initial_bankroll=10000.0)

        backtest_summary = backtester.run(test_fixtures, test_odds, test_results)

        print(f"   📊 Bets placed: {backtest_summary['total_bets']}")
        print(f"   📊 Win rate: {backtest_summary['win_rate']:.1%}")
        print(f"   📊 Final bankroll: ${backtest_summary['final_bankroll']:.2f}")
        print(f"   📊 ROI: {backtest_summary.get('roi', 0):.2%}")

        self.results["backtest"] = backtest_summary
        print()

        # Step 6: Feature importance
        print("🔍 STEP 6: Feature importance analysis...")

        # Get the underlying model (handle both ModelWrapper and raw Booster)
        if hasattr(model, "model"):
            actual_model = model.model
        else:
            actual_model = model

        if hasattr(actual_model, "feature_importance"):
            # LightGBM Booster
            importances = actual_model.feature_importance(importance_type="gain")
            feature_names = X_train_numeric.columns

            top_features = {}
            indices = np.argsort(importances)[::-1][:5]

            print("   Top 5 features:")
            for i, idx in enumerate(indices):
                feat_name = feature_names[idx]
                feat_imp = importances[idx]
                top_features[feat_name] = float(feat_imp)
                print(f"     {i+1}. {feat_name}: {feat_imp:.4f}")

            self.results["feature_importance"] = top_features
        elif hasattr(actual_model, "feature_importances_"):
            # Sklearn-style model
            importances = actual_model.feature_importances_
            feature_names = X_train_numeric.columns

            top_features = {}
            indices = np.argsort(importances)[::-1][:5]

            print("   Top 5 features:")
            for i, idx in enumerate(indices):
                feat_name = feature_names[idx]
                feat_imp = importances[idx]
                top_features[feat_name] = float(feat_imp)
                print(f"     {i+1}. {feat_name}: {feat_imp:.4f}")

            self.results["feature_importance"] = top_features
        else:
            print("   ⚠️  Feature importance not available for this model type")
        print()

        # Step 7: Save results
        print("💾 STEP 7: Saving results...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save model (handle both types)
        model_path = f"{self.output_dir}/model_{timestamp}.pkl"
        if hasattr(model, "save"):
            # ModelWrapper
            model.save(model_path)
        else:
            # Raw LightGBM Booster
            import pickle

            with open(model_path, "wb") as f:
                pickle.dump(model, f)
        print(f"   ✅ Model saved: {model_path}")

        # Save results JSON
        results_path = self.output_dir / f"results_{timestamp}.json"
        with open(results_path, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"   ✅ Results saved: {results_path}")

        # Save to database
        try:
            from datetime import timezone as tz

            with get_session() as session:
                metadata = ModelMetadata(
                    model_name=f"lgbm_automated_{timestamp}",
                    version=timestamp,
                    trained_at=datetime.now(tz.utc),
                    hyperparameters=self.results.get("feature_importance", {}),
                    metrics={
                        "accuracy": accuracy,
                        "brier": brier,
                        "backtest_roi": self.results["backtest"].get("roi", 0),
                        "feature_importance": self.results.get("feature_importance", {}),
                    },
                )
                session.add(metadata)
                session.commit()
            print("   ✅ Metadata saved to database")
        except Exception as e:
            print(f"   ⚠️  Could not save to database: {e}")

        print()

        # Step 8: Summary
        print("=" * 70)
        print("  PIPELINE SUMMARY")
        print("=" * 70 + "\n")

        print(f"✅ Training: {self.results['training']['n_samples']} samples")
        print(f"✅ Validation Accuracy: {accuracy:.2%}")
        print(f"✅ Backtest ROI: {self.results['backtest'].get('roi', 0):+.2%}")
        print(f"✅ Model saved: {model_path}")

        # Recommendations
        print("\n" + "=" * 70)
        print("  RECOMMENDATIONS")
        print("=" * 70 + "\n")

        if accuracy < 0.55:
            print("⚠️  Low accuracy - consider:")
            print("   • Adding more features")
            print("   • Using more training data")
            print("   • Trying different model architectures")
        elif accuracy > 0.75:
            print("✅ Excellent accuracy!")
            print("   • Model is performing well")
            print("   • Ready for live testing")
        else:
            print("✅ Good accuracy")
            print("   • Consider fine-tuning hyperparameters")
            print("   • Monitor performance on live data")

        if self.results["backtest"].get("total_bets", 0) == 0:
            print("\n⚠️  No bets placed in backtest")
            print("   • Edge thresholds may be too strict")
            print("   • Consider lowering min_edge parameter")

        print("\n" + "=" * 70 + "\n")

        return self.results


def main():
    """Run automated pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Automated ML Pipeline")
    parser.add_argument("--advanced", action="store_true", help="Use advanced training")
    parser.add_argument("--days", type=int, default=180, help="Training data days")
    parser.add_argument("--tune-only", action="store_true", help="Run hyperparameter tuning only")
    parser.add_argument(
        "--trials", type=int, default=20, help="Number of Optuna trials for tuning-only mode"
    )
    args = parser.parse_args()

    pipeline = AutomatedPipeline()

    if args.tune_only:
        pipeline.run_tuning_only(n_days=args.days, n_trials=args.trials)
        return 0

    results = pipeline.run_full_pipeline(advanced=args.advanced, n_days=args.days)

    return 0 if results["validation"]["accuracy"] > 0.50 else 1


if __name__ == "__main__":
    sys.exit(main())
