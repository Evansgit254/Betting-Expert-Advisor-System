"""ML model wrapper for training and prediction."""
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier

from src.logging_config import get_logger

logger = get_logger(__name__)

MODEL_DIR = Path("./models")
MODEL_PATH = MODEL_DIR / "model.pkl"


class ModelWrapper:
    """Wrapper for sklearn-compatible models with persistence."""

    def __init__(self, model_path: Path = MODEL_PATH):
        """Initialize model wrapper.

        Args:
            model_path: Path to save/load model
        """
        self.model_path = model_path
        self.model: Optional[BaseEstimator] = None

        # Ensure model directory exists
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

    def train(self, X: np.ndarray, y: np.ndarray, **kwargs) -> None:
        """Train a Random Forest classifier.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target vector (n_samples,)
            **kwargs: Additional parameters for RandomForestClassifier
        """
        logger.info(f"Training model on {X.shape[0]} samples with {X.shape[1]} features")

        # Default hyperparameters
        params = {
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_split": 20,
            "min_samples_leaf": 10,
            "random_state": 42,
            "n_jobs": -1,
            **kwargs,
        }

        model = RandomForestClassifier(**params)
        model.fit(X, y)
        self.model = model

        # Save model
        self.save()
        logger.info(f"Model trained and saved to {self.model_path}")

    def save(self, path: Optional[Path] = None) -> None:
        """Save model to disk.

        Args:
            path: Path to save model (defaults to self.model_path)
        """
        if self.model is None:
            raise RuntimeError("No model to save")

        save_path = path or self.model_path
        with open(save_path, "wb") as f:
            pickle.dump(self.model, f)
        logger.info(f"Model saved to {save_path}")

    def load(self, path: Optional[Path] = None) -> None:
        """Load model from disk.

        Args:
            path: Path to load model from (defaults to self.model_path)
        """
        load_path = path or self.model_path

        if not os.path.exists(load_path):
            raise FileNotFoundError(f"Model file not found: {load_path}")

        with open(load_path, "rb") as f:
            self.model = pickle.load(f)
        logger.info(f"Model loaded from {load_path}")

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate class predictions.

        Args:
            X: Feature matrix (n_samples, n_features)

        Returns:
            Predicted classes (n_samples,)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Generate probability predictions.

        Args:
            X: Feature matrix (n_samples, n_features)

        Returns:
            Predicted probabilities (n_samples, n_classes)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        logger.debug(f"Predicting probabilities for {X.shape[0]} samples")
        return self.model.predict_proba(X)

    def get_feature_importance(self) -> Optional[np.ndarray]:
        """Get feature importances if available.

        Returns:
            Feature importance array or None
        """
        if self.model is None:
            return None

        if hasattr(self.model, "feature_importances_"):
            return self.model.feature_importances_
        return None
