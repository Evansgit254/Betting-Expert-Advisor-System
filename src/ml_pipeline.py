"""Advanced ML pipeline with cross-validation and hyperparameter tuning."""
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

from src.logging_config import get_logger

logger = get_logger(__name__)

MODEL_DIR = Path("./models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

OPTUNA_STORAGE_PATH = DATA_DIR / "optuna.db"
OPTUNA_STORAGE_URL = f"sqlite:///{OPTUNA_STORAGE_PATH}"
OPTUNA_STUDY_NAME = "model_tuning"


class MLPipeline:
    """Advanced ML pipeline with time-series cross-validation and hyperparameter tuning."""

    def __init__(self, model_path: Path = MODEL_DIR / "lgbm.pkl"):
        """Initialize ML pipeline.

        Args:
            model_path: Path to save/load trained model
        """
        self.model_path = model_path
        self.model: Optional[lgb.Booster] = None
        self.best_params: Optional[Dict[str, Any]] = None

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for modeling.

        Args:
            df: Raw feature DataFrame

        Returns:
            Processed feature DataFrame
        """
        # Keep only numeric features
        X = df.select_dtypes(include=[np.number]).copy()

        # Fill missing values
        X = X.fillna(0)

        # Remove any inf values
        X = X.replace([np.inf, -np.inf], 0)

        logger.info(f"Prepared {X.shape[0]} samples with {X.shape[1]} features")
        return X

    def train_with_cv(
        self, df: pd.DataFrame, labels: np.ndarray, n_splits: int = 5, n_trials: int = 40
    ) -> lgb.Booster:
        """Train model with time-series cross-validation and hyperparameter tuning.

        Args:
            df: Feature DataFrame
            labels: Target labels
            n_splits: Number of cross-validation splits
            n_trials: Number of Optuna trials

        Returns:
            Trained LightGBM model
        """
        X = self._prepare(df)

        logger.info(f"Starting hyperparameter tuning with {n_trials} trials")

        def objective(trial: optuna.Trial) -> float:
            """Optuna objective function."""
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "verbosity": -1,
                "boosting_type": "gbdt",
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                "num_leaves": trial.suggest_int("num_leaves", 16, 256),
                "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 5, 50),
                "feature_fraction": trial.suggest_float("feature_fraction", 0.6, 1.0),
                "bagging_fraction": trial.suggest_float("bagging_fraction", 0.6, 1.0),
                "bagging_freq": trial.suggest_int("bagging_freq", 1, 7),
                "lambda_l1": trial.suggest_float("lambda_l1", 1e-8, 10.0, log=True),
                "lambda_l2": trial.suggest_float("lambda_l2", 1e-8, 10.0, log=True),
            }

            # Time-series cross-validation
            tscv = TimeSeriesSplit(n_splits=n_splits)
            losses = []

            for train_idx, val_idx in tscv.split(X):
                X_train = X.iloc[train_idx]
                y_train = labels[train_idx]
                X_val = X.iloc[val_idx]
                y_val = labels[val_idx]

                dtrain = lgb.Dataset(X_train, label=y_train)
                dval = lgb.Dataset(X_val, label=y_val)

                bst = lgb.train(
                    params,
                    dtrain,
                    valid_sets=[dval],
                    callbacks=[
                        lgb.early_stopping(stopping_rounds=50),
                        lgb.log_evaluation(period=0),
                    ],
                )

                preds = bst.predict(X_val)
                loss = log_loss(y_val, preds)
                losses.append(loss)

            # Optuna study is configured to maximize, so negate the loss
            return -np.mean(losses)

        # Run Optuna optimization with persistent storage to accumulate trials over time
        study = optuna.create_study(
            study_name=OPTUNA_STUDY_NAME,
            direction="maximize",
            storage=OPTUNA_STORAGE_URL,
            load_if_exists=True,
        )
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        self.best_params = study.best_params
        best_loss = -study.best_value
        logger.info(f"Best hyperparameters: {self.best_params}")
        logger.info(f"Best CV score (log loss): {best_loss:.4f}")

        # Train final model on all data with best parameters
        final_params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "verbosity": -1,
            "boosting_type": "gbdt",
            **self.best_params,
        }

        dtrain = lgb.Dataset(X, label=labels)
        final_model = lgb.train(
            final_params, dtrain, num_boost_round=1000, callbacks=[lgb.log_evaluation(period=100)]
        )

        self.model = final_model

        # Save model and study
        joblib.dump(final_model, self.model_path)
        joblib.dump(study, MODEL_DIR / "optuna_study.pkl")

        logger.info(f"Final model trained and saved to {self.model_path}")
        return final_model

    def train_simple(self, df: pd.DataFrame, labels: np.ndarray, **params) -> lgb.Booster:
        """Train model without hyperparameter tuning (faster).

        Args:
            df: Feature DataFrame
            labels: Target labels
            **params: LightGBM parameters

        Returns:
            Trained model
        """
        X = self._prepare(df)

        default_params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "verbosity": -1,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "min_data_in_leaf": 20,
            **params,
        }

        dtrain = lgb.Dataset(X, label=labels)
        model = lgb.train(
            default_params, dtrain, num_boost_round=500, callbacks=[lgb.log_evaluation(period=100)]
        )

        self.model = model
        joblib.dump(model, self.model_path)

        logger.info(f"Model trained and saved to {self.model_path}")
        return model

    def load(self, path: Optional[Path] = None) -> None:
        """Load trained model from disk.

        Args:
            path: Path to model file (defaults to self.model_path)
        """
        load_path = path or self.model_path

        if not load_path.exists():
            raise FileNotFoundError(f"Model not found: {load_path}")

        self.model = joblib.load(load_path)
        logger.info(f"Model loaded from {load_path}")

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Generate probability predictions.

        Args:
            df: Feature DataFrame

        Returns:
            Predicted probabilities for positive class
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        X = self._prepare(df)
        preds = self.model.predict(X)

        logger.debug(f"Generated predictions for {len(preds)} samples")
        return preds

    def evaluate(self, df: pd.DataFrame, labels: np.ndarray) -> Dict[str, float]:
        """Evaluate model performance.

        Args:
            df: Feature DataFrame
            labels: True labels

        Returns:
            Dictionary of metrics
        """
        probas = self.predict_proba(df)
        preds = (probas > 0.5).astype(int)

        metrics = {
            "log_loss": log_loss(labels, probas),
            "roc_auc": roc_auc_score(labels, probas),
            "accuracy": accuracy_score(labels, preds),
        }

        logger.info(f"Evaluation metrics: {metrics}")
        return metrics
